import logging
import time
from google import genai
from config import GEMINI_API_KEY, LLM_RPM
from utils.rate_limiter import RateLimiter
from utils.helpers import safe_json_parse

logger = logging.getLogger(__name__)

# Model rotation pool — cycles to next when one hits daily quota
_MODEL_POOL = [
    "gemini-2.5-flash-lite",
    "gemini-3-flash-preview",
    "gemini-3.1-flash-lite-preview",
    "gemini-flash-lite-latest",
    "gemini-2.5-flash",
]
_model_index = 0
_exhausted: set = set()

_rate_limiter = RateLimiter(LLM_RPM)
_client = None


def _get_client():
    global _client
    if _client is None:
        _client = genai.Client(api_key=GEMINI_API_KEY)
    return _client


def _current_model() -> str:
    available = [m for m in _MODEL_POOL if m not in _exhausted]
    if not available:
        raise RuntimeError("All Gemini models have hit their daily quota. Try again tomorrow.")
    return available[0]


def _mark_exhausted(model: str):
    global _exhausted
    _exhausted.add(model)
    available = [m for m in _MODEL_POOL if m not in _exhausted]
    if available:
        logger.warning(f"Model '{model}' quota exhausted. Switching to '{available[0]}'")
    else:
        logger.error("All models exhausted.")


class BaseAgent:
    name = "BaseAgent"

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    def llm_call(self, prompt: str, retries: int = 3) -> str:
        client = _get_client()
        for attempt in range(retries):
            model = _current_model()
            try:
                _rate_limiter.acquire()
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                )
                return response.text
            except Exception as e:
                err = str(e)
                if "429" in err or "RESOURCE_EXHAUSTED" in err:
                    if "limit: 0" in err or "GenerateRequestsPerDay" in err:
                        # daily quota hit — blacklist this model and retry immediately
                        _mark_exhausted(model)
                        continue
                    else:
                        # per-minute rate limit — short wait and retry
                        wait = 15
                        self.logger.warning(f"Rate limit hit, waiting {wait}s...")
                        time.sleep(wait)
                        continue
                wait = 2 ** attempt * 3
                self.logger.warning(f"LLM call failed (attempt {attempt+1}): {e}. Retrying in {wait}s")
                time.sleep(wait)
        return ""

    def llm_json(self, prompt: str) -> dict | list | None:
        raw = self.llm_call(prompt)
        return safe_json_parse(raw)

    def run(self, *args, **kwargs):
        raise NotImplementedError
