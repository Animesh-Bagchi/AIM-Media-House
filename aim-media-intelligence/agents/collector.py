"""
Agent 1 – Data Collector
Fetches video metadata and transcripts from the AIM Media House YouTube channel.
"""
import logging
import time
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from googleapiclient.discovery import build
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import NoTranscriptFound, TranscriptsDisabled

# v1.x uses instance methods
_transcript_api = YouTubeTranscriptApi()
from tqdm import tqdm

from agents.base_agent import BaseAgent
from database import manager as db
from config import YOUTUBE_API_KEY, CHANNEL_ID, MAX_VIDEOS
from utils.helpers import parse_iso_duration

logger = logging.getLogger(__name__)


class DataCollectorAgent(BaseAgent):
    name = "DataCollector"

    def __init__(self):
        super().__init__()
        if not YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY is not set. Please add it to .env")
        self.yt = build("youtube", "v3", developerKey=YOUTUBE_API_KEY)

    def run(self, channel_id: str = CHANNEL_ID):
        self.logger.info(f"[DataCollector] Starting collection for channel: {channel_id}")
        uploads_playlist = self._get_uploads_playlist(channel_id)
        if not uploads_playlist:
            self.logger.error("Could not find uploads playlist for channel.")
            return

        video_ids = self._get_all_video_ids(uploads_playlist)
        self.logger.info(f"Found {len(video_ids)} videos total")

        # fetch metadata in batches of 50 (YouTube API limit)
        self._fetch_and_store_metadata(video_ids)

        # fetch transcripts for videos not yet processed (parallel)
        pending = db.get_unprocessed_videos(limit=MAX_VIDEOS)
        self.logger.info(f"Fetching transcripts for {len(pending)} videos (parallel, 8 workers)")
        self._fetch_transcripts_parallel(pending)

        stats = db.get_stats()
        self.logger.info(
            f"[DataCollector] Done. Total: {stats['total']}, "
            f"With transcripts: {stats['with_transcript']}"
        )

    def _get_uploads_playlist(self, channel_id: str) -> str | None:
        try:
            resp = self.yt.channels().list(
                part="contentDetails,snippet",
                id=channel_id
            ).execute()
            items = resp.get("items", [])
            if not items:
                # try searching by handle
                self.logger.warning("Channel not found by ID, trying search...")
                return None
            playlist_id = items[0]["contentDetails"]["relatedPlaylists"]["uploads"]
            channel_name = items[0]["snippet"]["title"]
            self.logger.info(f"Channel: {channel_name} | Uploads playlist: {playlist_id}")
            return playlist_id
        except Exception as e:
            self.logger.error(f"Error fetching channel info: {e}")
            return None

    def _get_all_video_ids(self, playlist_id: str) -> list[str]:
        video_ids = []
        next_page = None
        while len(video_ids) < MAX_VIDEOS:
            params = dict(part="contentDetails", playlistId=playlist_id, maxResults=50)
            if next_page:
                params["pageToken"] = next_page
            try:
                resp = self.yt.playlistItems().list(**params).execute()
            except Exception as e:
                self.logger.error(f"Error paginating playlist: {e}")
                break

            for item in resp.get("items", []):
                vid = item["contentDetails"]["videoId"]
                video_ids.append(vid)

            next_page = resp.get("nextPageToken")
            if not next_page:
                break
            time.sleep(0.1)
        return video_ids[:MAX_VIDEOS]

    def _fetch_and_store_metadata(self, video_ids: list[str]):
        for i in range(0, len(video_ids), 50):
            batch = video_ids[i:i + 50]
            try:
                resp = self.yt.videos().list(
                    part="snippet,statistics,contentDetails",
                    id=",".join(batch)
                ).execute()
            except Exception as e:
                self.logger.error(f"Error fetching video details batch {i}: {e}")
                continue

            for item in resp.get("items", []):
                snippet = item.get("snippet", {})
                stats = item.get("statistics", {})
                published = snippet.get("publishedAt", "")
                year = int(published[:4]) if published else None

                db.upsert_video({
                    "video_id": item["id"],
                    "title": snippet.get("title", ""),
                    "published_at": published,
                    "year": year,
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "duration": item.get("contentDetails", {}).get("duration", ""),
                })
            time.sleep(0.1)

    def _fetch_transcripts_parallel(self, pending: list[dict], workers: int = 8):
        """Fetch transcripts in parallel using a thread pool."""
        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(self._fetch_one_transcript, v): v for v in pending}
            for future in tqdm(as_completed(futures), total=len(pending), desc="Fetching transcripts"):
                try:
                    future.result()
                except Exception as e:
                    self.logger.warning(f"Worker error: {e}")

    def _fetch_one_transcript(self, video: dict):
        vid = video["video_id"]
        from utils.helpers import clean_transcript
        try:
            # Try English first, then fall back to any available language
            fetched = _transcript_api.fetch(vid, languages=["en", "en-US", "en-GB", "en-IN"])
            raw_text = " ".join(seg.text for seg in fetched)
            db.store_transcript(vid, raw_text, clean_transcript(raw_text))
        except (NoTranscriptFound, TranscriptsDisabled):
            try:
                listing = _transcript_api.list(vid)
                # pick first available transcript (auto-generated OK)
                for t in listing:
                    fetched = t.fetch()
                    raw_text = " ".join(seg.text for seg in fetched)
                    db.store_transcript(vid, raw_text, clean_transcript(raw_text))
                    return
                db.mark_no_transcript(vid)
            except Exception:
                db.mark_no_transcript(vid)
        except Exception as e:
            self.logger.debug(f"Transcript error {vid}: {e}")
            db.mark_no_transcript(vid)

    def _fetch_transcripts(self, pending: list[dict]):
        from utils.helpers import clean_transcript
        for video in tqdm(pending, desc="Fetching transcripts"):
            vid = video["video_id"]
            try:
                fetched = _transcript_api.fetch(vid, languages=["en", "en-US", "en-GB", "en-IN"])
                raw_text = " ".join(seg.text for seg in fetched)
                db.store_transcript(vid, raw_text, clean_transcript(raw_text))
            except (NoTranscriptFound, TranscriptsDisabled):
                try:
                    listing = _transcript_api.list(vid)
                    for t in listing:
                        fetched = t.fetch()
                        raw_text = " ".join(seg.text for seg in fetched)
                        db.store_transcript(vid, raw_text, clean_transcript(raw_text))
                        break
                    else:
                        db.mark_no_transcript(vid)
                except Exception:
                    db.mark_no_transcript(vid)
            except Exception as e:
                self.logger.warning(f"Transcript error for {vid}: {e}")
                db.mark_no_transcript(vid)
            time.sleep(0.05)
