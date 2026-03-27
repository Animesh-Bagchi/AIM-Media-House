"""
Orchestrator Agent — the brain of the pipeline.

Uses a Plan → Execute → Observe → Reflect loop powered by Gemini.
Dynamically decides which agents to run, evaluates output quality,
and re-routes or retries when quality falls below threshold.

This is NOT a sequential script — the orchestrator actively reasons
about pipeline state and makes autonomous decisions at each step.
"""
import json
import logging
import time
from dataclasses import dataclass
from typing import Optional

from agents.base_agent import BaseAgent
from agents.message_bus import MessageBus
from database import manager as db

logger = logging.getLogger(__name__)

PLAN_PROMPT = """You are the orchestrator of an AI-powered YouTube analytics pipeline.

Current pipeline state:
{state}

Available agents and their responsibilities:
- collect:  Fetch video metadata and transcripts from YouTube
- process:  Clean transcripts (remove timestamps, fillers, noise)
- analyze:  Extract entities, topics, sentiment, relationships using LLM
- report:   Generate yearly summaries and HTML/PDF reports

Your job: decide which agents need to run (in order) to make progress.

Rules:
- Only include agents that need to do work based on the state above
- If analysis coverage is below 80%, always include "analyze"
- If report is missing or stale, include "report"
- If there are unprocessed transcripts, include "process"
- "collect" only if total < 10 OR explicitly requested

Respond with JSON only:
{{
  "plan": ["agent1", "agent2", ...],
  "reasoning": "why you chose these agents",
  "priority": "what matters most right now"
}}
"""

QUALITY_PROMPT = """You are a quality assessor for a YouTube analytics pipeline.

Agent that just ran: {agent}
Output summary: {summary}

Assess the quality on a scale of 0-10:
- 0-3: Very poor, must retry with adjusted parameters
- 4-6: Acceptable, proceed but flag issues
- 7-10: Good quality, proceed normally

Respond with JSON only:
{{
  "score": <0-10>,
  "verdict": "pass|retry|skip",
  "issues": ["issue1", "issue2"],
  "suggestion": "what to do differently if retrying"
}}
"""

REFLECTION_PROMPT = """You are reviewing the completed analytics pipeline for AIM Media House.

Pipeline execution log:
{log}

Final state:
{state}

Provide a brief reflection:
1. What went well
2. What could be improved
3. Key data quality observations
4. Confidence level in the analysis (0-100%)

Respond with JSON only:
{{
  "went_well": [...],
  "improvements": [...],
  "data_quality": "...",
  "confidence": <0-100>
}}
"""


@dataclass
class PipelineState:
    total_videos: int = 0
    with_transcripts: int = 0
    analyzed: int = 0
    reports_generated: int = 0
    year_range: tuple = (None, None)

    def analysis_coverage(self) -> float:
        if self.with_transcripts == 0:
            return 0.0
        return self.analyzed / self.with_transcripts

    def to_dict(self) -> dict:
        return {
            "total_videos": self.total_videos,
            "with_transcripts": self.with_transcripts,
            "analyzed": self.analyzed,
            "reports_generated": self.reports_generated,
            "analysis_coverage_pct": round(self.analysis_coverage() * 100, 1),
            "year_range": self.year_range,
        }


class OrchestratorAgent(BaseAgent):
    """
    Plan-Execute-Observe-Reflect agent that autonomously drives the pipeline.
    """
    name = "Orchestrator"

    def __init__(self, bus: Optional[MessageBus] = None):
        super().__init__()
        self.bus = bus or MessageBus()
        self.execution_log: list[dict] = []
        self._wire_subscriptions()

    def _wire_subscriptions(self):
        self.bus.subscribe("agent.completed", self._on_agent_completed)
        self.bus.subscribe("agent.failed", self._on_agent_failed)
        self.bus.subscribe("quality.low", self._on_quality_low)

    def _on_agent_completed(self, msg):
        self.logger.info(f"[Orchestrator] ✓ {msg.sender} completed: {msg.payload}")

    def _on_agent_failed(self, msg):
        self.logger.warning(f"[Orchestrator] ✗ {msg.sender} failed: {msg.payload}")

    def _on_quality_low(self, msg):
        self.logger.warning(f"[Orchestrator] Quality flag from {msg.sender}: {msg.payload}")

    def run(self, force_collect: bool = False, max_iterations: int = 3):
        self.logger.info("[Orchestrator] Starting agentic pipeline loop")
        self.bus.publish("Orchestrator", "pipeline.started")

        for iteration in range(max_iterations):
            self.logger.info(f"\n{'='*50}")
            self.logger.info(f"[Orchestrator] ITERATION {iteration + 1}/{max_iterations}")

            # OBSERVE current state
            state = self._observe()
            self.logger.info(f"[Orchestrator] State: {state.to_dict()}")

            # PLAN next actions
            plan = self._plan(state, force_collect=(force_collect and iteration == 0))
            if not plan:
                self.logger.info("[Orchestrator] No agents needed. Pipeline is complete.")
                break

            self.logger.info(f"[Orchestrator] Plan: {' → '.join(plan['plan'])}")
            self.logger.info(f"[Orchestrator] Reasoning: {plan['reasoning']}")

            # EXECUTE agents
            for agent_name in plan["plan"]:
                success = self._execute_agent(agent_name, state)
                if not success:
                    self.logger.warning(f"[Orchestrator] Agent {agent_name} failed, continuing...")

            # re-observe after execution
            state = self._observe()

            # REFLECT on quality
            if iteration == max_iterations - 1 or self._is_done(state):
                self._reflect(state)
                break

        self.bus.publish("Orchestrator", "pipeline.completed")
        self.logger.info("[Orchestrator] Pipeline finished.")
        return self._observe()

    def _observe(self) -> PipelineState:
        stats = db.get_stats()
        summaries = db.get_yearly_summaries()
        return PipelineState(
            total_videos=stats["total"],
            with_transcripts=stats["with_transcript"],
            analyzed=stats["analyzed"],
            reports_generated=len(summaries),
            year_range=stats["year_range"],
        )

    def _plan(self, state: PipelineState, force_collect: bool = False) -> dict | None:
        # fast-path: no LLM needed for obvious cases
        plan = []
        if force_collect or state.total_videos == 0:
            plan = ["collect", "process", "analyze", "report"]
        else:
            if state.with_transcripts < state.total_videos * 0.3:
                plan.append("process")
            if state.analysis_coverage() < 0.8:
                plan.append("analyze")
            if state.reports_generated < max(1, len(set()) if state.year_range[0] is None else
                                              range(state.year_range[0], state.year_range[1] + 1)):
                plan.append("report")

        if not plan:
            return None

        # use Gemini to validate/refine the plan
        try:
            result = self.llm_json(PLAN_PROMPT.format(state=json.dumps(state.to_dict(), indent=2)))
            if result and isinstance(result, dict) and result.get("plan"):
                return result
        except Exception as e:
            self.logger.warning(f"LLM planning failed, using heuristic plan: {e}")

        return {"plan": plan, "reasoning": "Heuristic plan based on pipeline state", "priority": plan[0]}

    def _execute_agent(self, agent_name: str, state: PipelineState) -> bool:
        self.logger.info(f"\n[Orchestrator] → Executing: {agent_name}")
        self.bus.publish("Orchestrator", "agent.starting", {"agent": agent_name})
        start = time.time()

        try:
            if agent_name == "collect":
                from agents.collector import DataCollectorAgent
                DataCollectorAgent().run()
            elif agent_name == "process":
                from agents.processor import TranscriptProcessorAgent
                TranscriptProcessorAgent().run()
            elif agent_name == "analyze":
                from agents.analyzer import AnalysisAgent
                AnalysisAgent().run()
            elif agent_name == "report":
                from agents.reporter import ReportGeneratorAgent
                ReportGeneratorAgent().run()
            else:
                self.logger.warning(f"Unknown agent: {agent_name}")
                return False

            elapsed = time.time() - start
            summary = self._summarize_agent_output(agent_name)
            quality = self._assess_quality(agent_name, summary)

            self.execution_log.append({
                "agent": agent_name, "status": "completed",
                "elapsed_s": round(elapsed, 1), "quality_score": quality["score"],
                "quality_verdict": quality["verdict"],
            })
            self.bus.publish(agent_name, "agent.completed", summary)

            if quality["verdict"] == "retry":
                self.bus.publish(agent_name, "quality.low", quality)
                self.logger.warning(f"[Orchestrator] Quality low for {agent_name} (score={quality['score']}): {quality['issues']}")
            return True

        except Exception as e:
            self.execution_log.append({"agent": agent_name, "status": "failed", "error": str(e)})
            self.bus.publish(agent_name, "agent.failed", str(e))
            self.logger.error(f"[Orchestrator] Agent {agent_name} raised: {e}")
            return False

    def _summarize_agent_output(self, agent_name: str) -> str:
        state = self._observe()
        if agent_name == "collect":
            return f"Collected {state.total_videos} videos, {state.with_transcripts} with transcripts"
        elif agent_name == "process":
            return f"{state.with_transcripts} transcripts cleaned and stored"
        elif agent_name == "analyze":
            cov = state.analysis_coverage()
            entity_count = len(db.get_top_entities(limit=200))
            return f"Analyzed {state.analyzed} videos ({cov:.0%} coverage), {entity_count} unique entities"
        elif agent_name == "report":
            return f"{state.reports_generated} yearly reports generated"
        return "completed"

    def _assess_quality(self, agent_name: str, summary: str) -> dict:
        # heuristic quality checks
        state = self._observe()
        score = 8  # default: good
        issues = []
        verdict = "pass"

        if agent_name == "collect" and state.total_videos < 10:
            score = 3
            issues.append("Very few videos fetched — check YouTube API key and channel ID")
            verdict = "retry"
        elif agent_name == "analyze" and state.analysis_coverage() < 0.5:
            score = 5
            issues.append(f"Low analysis coverage: {state.analysis_coverage():.0%}")
            verdict = "pass"  # pass but flag
        elif agent_name == "report" and state.reports_generated == 0:
            score = 2
            issues.append("No reports generated")
            verdict = "retry"

        return {"score": score, "verdict": verdict, "issues": issues, "suggestion": ""}

    def _reflect(self, state: PipelineState):
        self.logger.info("\n[Orchestrator] REFLECTION")
        log_str = json.dumps(self.execution_log, indent=2)
        try:
            result = self.llm_json(REFLECTION_PROMPT.format(
                log=log_str, state=json.dumps(state.to_dict(), indent=2)
            ))
            if result:
                self.logger.info(f"  Confidence: {result.get('confidence', '?')}%")
                self.logger.info(f"  Data quality: {result.get('data_quality', '?')}")
                for item in result.get("went_well", []):
                    self.logger.info(f"  ✓ {item}")
                for item in result.get("improvements", []):
                    self.logger.info(f"  ⚠ {item}")
        except Exception as e:
            self.logger.warning(f"Reflection failed: {e}")

        self.logger.info(f"  Execution log: {json.dumps(self.execution_log, indent=2)}")

    def _is_done(self, state: PipelineState) -> bool:
        return (
            state.total_videos > 0
            and state.analysis_coverage() >= 0.8
            and state.reports_generated > 0
        )
