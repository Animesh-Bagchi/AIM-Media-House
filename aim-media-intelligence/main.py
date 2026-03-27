"""
AIM Media House – Multi-Agent Intelligence Pipeline
Orchestrated end-to-end via the OrchestratorAgent (Plan → Execute → Observe → Reflect).

Usage:
    python main.py                   # full autonomous pipeline
    python main.py --mode collect    # only fetch data
    python main.py --mode process    # only clean transcripts
    python main.py --mode analyze    # only run LLM analysis
    python main.py --mode insights   # cross-video insight generation
    python main.py --mode report     # only generate reports
    python main.py --mode dashboard  # launch Streamlit dashboard
    python main.py --mode auto       # orchestrator decides everything
"""
import argparse
import logging
import sys
import time
from datetime import datetime

from database import manager as db
from config import YOUTUBE_API_KEY, GEMINI_API_KEY, CHANNEL_ID

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s – %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("data/pipeline.log"),
    ]
)
logger = logging.getLogger("pipeline")


def check_api_keys(require_gemini=True):
    errors = []
    if not YOUTUBE_API_KEY:
        errors.append("YOUTUBE_API_KEY is not set")
    if require_gemini and not GEMINI_API_KEY:
        errors.append("GEMINI_API_KEY is not set")
    if errors:
        logger.error("Configuration errors:\n" + "\n".join(f"  • {e}" for e in errors))
        logger.error("Please copy .env.example to .env and fill in your API keys.")
        sys.exit(1)


def banner(mode: str):
    logger.info("=" * 60)
    logger.info("  AIM Media House – Intelligence Pipeline")
    logger.info(f"  Mode     : {mode}")
    logger.info(f"  Channel  : {CHANNEL_ID}")
    logger.info(f"  Started  : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)


def run_pipeline(mode: str = "full"):
    start = time.time()
    banner(mode)
    db.initialize_db()

    if mode == "auto":
        # True agentic mode — orchestrator decides everything
        check_api_keys()
        from agents.orchestrator import OrchestratorAgent
        from agents.message_bus import MessageBus
        bus = MessageBus()
        OrchestratorAgent(bus=bus).run(force_collect=True)

    elif mode == "full":
        check_api_keys()
        logger.info("\n[1/5] Data Collection Agent")
        from agents.collector import DataCollectorAgent
        DataCollectorAgent().run()

        logger.info("\n[2/5] Transcript Processor Agent")
        from agents.processor import TranscriptProcessorAgent
        TranscriptProcessorAgent().run()

        logger.info("\n[3/5] Analysis Agent")
        from agents.analyzer import AnalysisAgent
        AnalysisAgent().run()

        logger.info("\n[4/5] Insights Agent")
        from agents.insights_agent import InsightsAgent
        InsightsAgent().run()

        logger.info("\n[5/5] Report Generator Agent")
        from agents.reporter import ReportGeneratorAgent
        ReportGeneratorAgent().run()

    elif mode == "collect":
        check_api_keys(require_gemini=False)
        from agents.collector import DataCollectorAgent
        DataCollectorAgent().run()

    elif mode == "process":
        from agents.processor import TranscriptProcessorAgent
        TranscriptProcessorAgent().run()

    elif mode == "analyze":
        check_api_keys(require_gemini=True)
        from agents.analyzer import AnalysisAgent
        AnalysisAgent().run()

    elif mode == "insights":
        check_api_keys(require_gemini=True)
        from agents.insights_agent import InsightsAgent
        InsightsAgent().run()

    elif mode == "report":
        check_api_keys(require_gemini=True)
        from agents.reporter import ReportGeneratorAgent
        ReportGeneratorAgent().run()

    elif mode == "dashboard":
        import subprocess
        subprocess.run(["streamlit", "run", "dashboard/app.py"])
        return

    elapsed = time.time() - start
    stats = db.get_stats()
    logger.info("\n" + "=" * 60)
    logger.info("Pipeline complete!")
    logger.info(f"  Videos         : {stats['total']}")
    logger.info(f"  With transcripts: {stats['with_transcript']}")
    logger.info(f"  Analyzed       : {stats['analyzed']}")
    logger.info(f"  Elapsed        : {elapsed / 60:.1f} min")
    logger.info("=" * 60)
    logger.info("\nLaunch dashboard: python main.py --mode dashboard")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="AIM Media House Intelligence Pipeline")
    parser.add_argument(
        "--mode",
        choices=["full", "auto", "collect", "process", "analyze", "insights", "report", "dashboard"],
        default="full",
        help="Pipeline stage to run (default: full | auto = orchestrator-driven)"
    )
    args = parser.parse_args()
    run_pipeline(args.mode)
