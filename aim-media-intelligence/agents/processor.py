"""
Agent 2 – Transcript Processor
Cleans raw transcripts: removes timestamps, filler words, and noise.
Stores structured, clean text ready for analysis.
"""
import re
import logging
from tqdm import tqdm
from agents.base_agent import BaseAgent
from database import manager as db
from utils.helpers import clean_transcript, word_count

logger = logging.getLogger(__name__)


class TranscriptProcessorAgent(BaseAgent):
    name = "TranscriptProcessor"

    def run(self):
        self.logger.info("[TranscriptProcessor] Starting transcript cleaning")
        # re-process any that have raw transcript but need updated cleaning
        from database.manager import get_conn
        with get_conn() as conn:
            rows = conn.execute("""
                SELECT video_id, transcript_raw FROM videos
                WHERE has_transcript=1 AND transcript_raw IS NOT NULL
            """).fetchall()

        self.logger.info(f"Processing {len(rows)} transcripts")
        for row in tqdm(rows, desc="Cleaning transcripts"):
            raw = row["transcript_raw"]
            clean = self._process(raw)
            db.store_transcript(row["video_id"], raw, clean)

        self.logger.info("[TranscriptProcessor] Done")

    def _process(self, raw: str) -> str:
        text = clean_transcript(raw)
        text = self._fix_sentence_breaks(text)
        text = self._normalize_whitespace(text)
        return text

    def _fix_sentence_breaks(self, text: str) -> str:
        # YouTube ASR often lacks punctuation — add period at potential sentence ends
        text = re.sub(r'([a-z])\s{2,}([A-Z])', r'\1. \2', text)
        return text

    def _normalize_whitespace(self, text: str) -> str:
        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'\n+', '\n', text)
        return text.strip()
