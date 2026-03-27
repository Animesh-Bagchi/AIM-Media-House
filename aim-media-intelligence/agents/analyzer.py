"""
Agent 3 – Analysis Agent
Performs entity extraction, topic classification, sentiment analysis,
trend detection, and relationship mapping using Gemini.

Batches 5 videos per LLM call to stay within free-tier rate limits.
"""
import json
import logging
import time
from tqdm import tqdm

from agents.base_agent import BaseAgent
from database import manager as db
from config import TOPIC_CATEGORIES, ANALYSIS_BATCH_SIZE
from utils.helpers import truncate_to_words

logger = logging.getLogger(__name__)

ANALYSIS_PROMPT = """You are analyzing YouTube video transcripts from AIM Media House, an Indian AI/ML media channel.

Analyze the following {n} videos and return a JSON array with one object per video.

{videos_block}

For each video return:
{{
  "video_id": "<id>",
  "entities": [
    {{"name": "...", "type": "person|company|tool|technology", "relevance": 1-10}}
  ],
  "topics": ["PrimaryTopic", "SecondaryTopic"],
  "sentiment": {{"overall": "positive|neutral|critical", "score": 0.0-1.0, "reasoning": "..."}},
  "relationships": [
    {{"entity1": "...", "entity2": "...", "context": "brief description of connection"}}
  ]
}}

topics must come from: {categories}
Return ONLY valid JSON array, no markdown.
"""

VIDEO_BLOCK_TEMPLATE = """--- Video {i} ---
ID: {video_id}
Title: {title}
Published: {published_at}
Views: {view_count}
Transcript:
{transcript}
"""


class AnalysisAgent(BaseAgent):
    name = "AnalysisAgent"

    def run(self, limit: int = 5000):
        self.logger.info("[AnalysisAgent] Starting analysis")
        pending = db.get_unanalyzed_videos(limit=limit)
        self.logger.info(f"Videos to analyze: {len(pending)}")

        batches = [pending[i:i + ANALYSIS_BATCH_SIZE] for i in range(0, len(pending), ANALYSIS_BATCH_SIZE)]
        failed = 0
        for batch in tqdm(batches, desc="Analyzing videos"):
            ok = self._analyze_batch(batch)
            if not ok:
                failed += len(batch)

        self.logger.info(f"[AnalysisAgent] Done. Failed: {failed}/{len(pending)}")

    def _analyze_batch(self, videos: list[dict]) -> bool:
        videos_block = ""
        for i, v in enumerate(videos, 1):
            transcript = truncate_to_words(v.get("transcript_clean") or "", 2500)
            videos_block += VIDEO_BLOCK_TEMPLATE.format(
                i=i,
                video_id=v["video_id"],
                title=v.get("title", ""),
                published_at=v.get("published_at", ""),
                view_count=v.get("view_count", 0),
                transcript=transcript
            )

        prompt = ANALYSIS_PROMPT.format(
            n=len(videos),
            videos_block=videos_block,
            categories=", ".join(TOPIC_CATEGORIES)
        )

        result = self.llm_json(prompt)
        if not result or not isinstance(result, list):
            self.logger.warning(f"Bad response for batch of {len(videos)} videos")
            return False

        result_map = {r.get("video_id"): r for r in result if isinstance(r, dict)}

        for v in videos:
            vid = v["video_id"]
            year = v.get("year") or (int(v.get("published_at", "2000")[:4]) if v.get("published_at") else None)
            data = result_map.get(vid, {})

            if not data:
                # mark as analyzed with empty data so we don't retry endlessly
                self.logger.debug(f"No analysis data for {vid}, marking done")
                db.store_analysis(vid, year, [], [], {"overall": "neutral", "score": 0.5, "reasoning": ""}, [])
                continue

            entities = data.get("entities") or []
            topics = data.get("topics") or []
            sentiment = data.get("sentiment") or {"overall": "neutral", "score": 0.5, "reasoning": ""}
            relationships = data.get("relationships") or []

            # validate entity types
            valid_types = {"person", "company", "tool", "technology"}
            entities = [e for e in entities if isinstance(e, dict) and e.get("type", "").lower() in valid_types]

            db.store_analysis(vid, year, entities, topics, sentiment, relationships)
        return True
