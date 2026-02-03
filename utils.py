import json
import logging
import random
import re
import time
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

OUTPUT_DIR = Path("output")
OUTPUT_DIR.mkdir(exist_ok=True)


def setup_logger(name: str, log_file: str) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        handler = logging.FileHandler(OUTPUT_DIR / log_file, encoding="utf-8")
        formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger


FAILED_URLS_LOGGER = setup_logger("failed_urls", "failed_urls.log")
MISSING_FIELDS_LOGGER = setup_logger("missing_fields", "missing_fields.log")


USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36",
]


def random_headers() -> Dict[str, str]:
    return {
        "User-Agent": random.choice(USER_AGENTS),
        "Accept-Language": "en-US,en;q=0.9",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Connection": "keep-alive",
    }


def random_delay(min_seconds: float = 1.0, max_seconds: float = 3.0) -> None:
    time.sleep(random.uniform(min_seconds, max_seconds))


def fetch_html(url: str, timeout: int = 20) -> Optional[str]:
    try:
        response = requests.get(url, headers=random_headers(), timeout=timeout)
        if response.status_code != 200:
            FAILED_URLS_LOGGER.info("Non-200 %s for %s", response.status_code, url)
            return None
        return response.text
    except Exception as exc:
        FAILED_URLS_LOGGER.info("Request error for %s: %s", url, exc)
        return None


def normalize_text(text: Optional[str]) -> Optional[str]:
    if not text:
        return None
    cleaned = re.sub(r"\s+", " ", text).strip()
    return cleaned or None


def safe_get_text(node, default: Optional[str] = None) -> Optional[str]:
    if not node:
        return default
    return normalize_text(node.get_text(" ", strip=True)) or default


def safe_get_attr(node, attr: str, default: Optional[str] = None) -> Optional[str]:
    if not node:
        return default
    value = node.get(attr)
    return normalize_text(value) or default


def unique_list(items: Iterable[str]) -> List[str]:
    seen = set()
    result = []
    for item in items:
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def log_missing_fields(source: str, url: str, missing_fields: List[str]) -> None:
    if not missing_fields:
        return
    MISSING_FIELDS_LOGGER.info("%s | %s | missing: %s", source, url, ", ".join(missing_fields))


def save_json(path: Path, data: Any) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def build_embed_link(query: str) -> str:
    encoded = requests.utils.quote(query)
    return f"https://www.google.com/maps?q={encoded}&output=embed"


def build_embed_link_from_place_url(place_url: Optional[str]) -> Optional[str]:
    if not place_url:
        return None
    if "output=embed" in place_url:
        return place_url
    joiner = "&" if "?" in place_url else "?"
    return f"{place_url}{joiner}output=embed"


def pick_user_agent() -> str:
    return random.choice(USER_AGENTS)


def looks_like_blocked(text: Optional[str]) -> bool:
    if not text:
        return False
    lowered = text.lower()
    return "unusual traffic" in lowered or "captcha" in lowered or "verify" in lowered


def parse_rating_reviews(text: Optional[str]) -> Tuple[Optional[str], Optional[str]]:
    if not text:
        return None, None
    match = re.search(r"([0-9.]+)\s*\((\d+)\)", text)
    if match:
        rating, reviews = match.group(1), match.group(2)
        return rating, reviews
    return None, None
