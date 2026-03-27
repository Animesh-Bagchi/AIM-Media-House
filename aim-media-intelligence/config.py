import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
DB_PATH = str(DATA_DIR / "aim_intelligence.db")
REPORTS_DIR = DATA_DIR / "outputs" / "reports"

for d in [DATA_DIR, REPORTS_DIR, DATA_DIR / "raw", DATA_DIR / "processed"]:
    d.mkdir(parents=True, exist_ok=True)

# YouTube
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")
# AIM Media House / Analytics India Magazine channel ID
CHANNEL_ID = os.getenv("CHANNEL_ID", "UCh7cV9a7zfACq8f00hJIdSg")

# Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
LLM_MODEL = "gemini-2.5-flash-lite"
# Free tier limits: 30 RPM for flash-lite
LLM_RPM = 28  # keep slightly under limit

# Processing
MAX_VIDEOS = int(os.getenv("MAX_VIDEOS", "2000"))
ANALYSIS_BATCH_SIZE = 10  # videos per Gemini call (reduces total API calls)
CHUNK_WORDS = 2500         # max words sent per transcript chunk

TOPIC_CATEGORIES = [
    "GenAI", "MLOps", "Startups", "Research", "Interviews",
    "NLP", "Computer Vision", "Data Science", "Cloud & Infrastructure",
    "Hardware & Chips", "Career & Education", "Industry News",
    "Robotics", "Regulation & Policy", "Open Source"
]
