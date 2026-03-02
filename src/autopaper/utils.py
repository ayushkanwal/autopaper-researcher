from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import re
import shlex
from pathlib import Path
from typing import Any, Iterable, List, Optional

STOPWORDS = {
    "with",
    "from",
    "using",
    "based",
    "towards",
    "about",
    "for",
    "into",
    "this",
    "that",
    "study",
    "paper",
    "time",
    "series",
}
BOOLEAN_OPERATORS = re.compile(r"\b(AND|OR|NOT)\b", flags=re.IGNORECASE)


def normalize_whitespace(value: str) -> str:
    return re.sub(r"\s+", " ", (value or "")).strip()


def adapt_query_for_source(query: str, source_name: str) -> str:
    text = normalize_whitespace(query).replace("all:", "")
    if source_name.lower() == "arxiv":
        return text
    if source_name.lower() == "pubmed":
        return normalize_whitespace(text)
    text = BOOLEAN_OPERATORS.sub(" ", text)
    text = text.replace("(", " ").replace(")", " ")
    return normalize_whitespace(text)


def normalize_title(value: str) -> str:
    value = normalize_whitespace(value).lower()
    value = re.sub(r"[^a-z0-9\s]", "", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_doi(value: str) -> str:
    doi = normalize_whitespace(value).lower()
    doi = doi.replace("https://doi.org/", "")
    doi = doi.replace("http://doi.org/", "")
    return doi


def normalize_arxiv_id(value: str) -> str:
    token = normalize_whitespace(value)
    token = token.replace("https://arxiv.org/abs/", "")
    token = token.replace("http://arxiv.org/abs/", "")
    token = token.replace("https://arxiv.org/pdf/", "")
    token = token.replace("http://arxiv.org/pdf/", "")
    token = token.replace(".pdf", "")
    return re.sub(r"v\d+$", "", token)


def parse_iso_datetime(value: str) -> dt.datetime:
    text = normalize_whitespace(value)
    if not text:
        return dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = dt.datetime.fromisoformat(text)
    except ValueError:
        return dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed


def split_sentences(text: str) -> List[str]:
    text = normalize_whitespace(text)
    if not text:
        return []
    pieces = re.split(r"(?<=[.!?])\s+(?=[A-Z0-9])", text)
    return [p.strip() for p in pieces if p.strip()]


def extract_urls(text: str) -> List[str]:
    if not text:
        return []
    candidates = re.findall(r"https?://[^\s<>'\"]+", text)
    cleaned: List[str] = []
    for url in candidates:
        u = url.rstrip(".,);]\"")
        if u:
            cleaned.append(u)
    return cleaned


def title_tokens(title: str) -> List[str]:
    tokens = re.findall(r"[a-z0-9]+", normalize_whitespace(title).lower())
    return [t for t in tokens if len(t) >= 4 and t not in STOPWORDS]


def extract_keywords(title: str, abstract: str) -> List[str]:
    lexicon = [
        "time series",
        "forecasting",
        "prediction",
        "transformer",
        "foundation model",
        "agent",
        "agentic",
        "tool-augmented",
        "retrieval",
        "rag",
        "multivariate",
        "self-supervised",
        "probabilistic",
        "state space",
        "anomaly detection",
        "livestock",
        "cattle",
        "pasture",
        "forage",
        "paddock",
        "digital twin",
        "decision support",
        "biophysical",
        "mechanistic",
        "adg",
        "dmd",
    ]
    text = f"{title} {abstract}".lower()
    tags = [term for term in lexicon if term in text]
    if not tags:
        tags = ["time series", "prediction"]
    return tags[:12]


def parse_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "y", "on"}:
        return True
    if text in {"0", "false", "no", "n", "off"}:
        return False
    return default


def parse_json_array(value: Optional[str], env_name: str) -> List[str]:
    if value is None or str(value).strip() == "":
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{env_name} must be a JSON array") from exc
    if not isinstance(parsed, list) or not all(isinstance(item, str) for item in parsed):
        raise ValueError(f"{env_name} must be a JSON array of strings")
    return [normalize_whitespace(item) for item in parsed if normalize_whitespace(item)]


def comma_split(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [normalize_whitespace(item) for item in value.split(",") if normalize_whitespace(item)]


def load_env_file(path: Optional[str]) -> None:
    if not path:
        return
    env_path = Path(path)
    if not env_path.exists():
        raise FileNotFoundError(f"Env file not found: {env_path}")
    try:
        from dotenv import load_dotenv  # type: ignore

        load_dotenv(env_path, override=False)
        return
    except Exception:
        pass

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def mask_secret(value: Optional[str]) -> Optional[str]:
    if not value:
        return value
    if len(value) <= 8:
        return "*" * len(value)
    return value[:3] + "..." + value[-3:]


def stable_fingerprint(*parts: Optional[str]) -> str:
    joined = "||".join(normalize_whitespace(part or "") for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def ensure_directory(path: str | Path) -> Path:
    target = Path(path)
    target.mkdir(parents=True, exist_ok=True)
    return target


def now_utc() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def shlex_split(command: str) -> List[str]:
    return shlex.split(command)


def compact_json(data: Any) -> str:
    return json.dumps(data, separators=(",", ":"), ensure_ascii=True)


def reconstruct_openalex_abstract(inverted_index: Optional[dict[str, list[int]]]) -> str:
    if not inverted_index:
        return ""
    slots: dict[int, str] = {}
    for token, positions in inverted_index.items():
        for position in positions:
            slots[position] = token
    return normalize_whitespace(" ".join(slots[idx] for idx in sorted(slots)))


def doi_to_arxiv_id(doi: str) -> Optional[str]:
    ndoi = normalize_doi(doi)
    if "arxiv." not in ndoi.lower():
        return None
    token = re.split(r"arxiv\.", ndoi, flags=re.IGNORECASE)[-1]
    return normalize_arxiv_id(token)


def url_to_arxiv_id(url: str) -> Optional[str]:
    value = normalize_whitespace(url)
    match = re.search(r"arxiv\.org/(abs|pdf)/([^?#]+)", value, flags=re.IGNORECASE)
    if match:
        return normalize_arxiv_id(match.group(2))
    return None


def unique_preserve_order(values: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen: set[str] = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
