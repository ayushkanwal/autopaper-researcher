from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from .query_presets import DEFAULT_PRESET, QueryPreset, get_preset
from .utils import comma_split, load_env_file, mask_secret, parse_bool, parse_json_array

VALID_SOURCES = {"arxiv", "pubmed", "openalex"}
VALID_SUMMARIZERS = {"offline", "openai_compatible", "command"}


@dataclass
class RuntimeConfig:
    profile_name: str = "default"
    query_preset: str = DEFAULT_PRESET
    queries: List[str] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    collection_name: str = "autopaper-ingested"
    max_new: int = 2
    max_results_per_query: int = 25
    min_relevance_score: int = 8
    dry_run: bool = False
    attach_real_pdfs: bool = False
    enable_github_search: bool = True
    report_dir: str = "reports"
    state_dir: str = ".autopaper_state"
    timezone: Optional[str] = None
    schedule_cron: str = "0 9 * * *"
    run_on_start: bool = False
    boost_terms: List[str] = field(default_factory=list)
    penalty_terms: List[str] = field(default_factory=list)
    include_terms: List[str] = field(default_factory=list)
    exclude_terms: List[str] = field(default_factory=list)
    summarizer: str = "offline"
    summary_fallback: str = "offline"
    llm_base_url: Optional[str] = None
    llm_api_key: Optional[str] = None
    llm_model: Optional[str] = None
    llm_timeout_seconds: int = 60
    summary_command: Optional[str] = None
    zotero_user_id: Optional[str] = None
    zotero_api_key: Optional[str] = None
    pubmed_email: Optional[str] = None
    pubmed_api_key: Optional[str] = None
    openalex_mailto: Optional[str] = None
    github_token: Optional[str] = None

    def to_public_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        data["zotero_api_key"] = mask_secret(self.zotero_api_key)
        data["llm_api_key"] = mask_secret(self.llm_api_key)
        data["github_token"] = mask_secret(self.github_token)
        data["pubmed_api_key"] = mask_secret(self.pubmed_api_key)
        return data

    def report_path(self) -> Path:
        return Path(self.report_dir) / self.profile_name

    def state_path(self) -> Path:
        return Path(self.state_dir)


COMMON_ENV_KEYS = {
    "profile_name": "AUTOPAPER_PROFILE_NAME",
    "query_preset": "AUTOPAPER_QUERY_PRESET",
    "queries_json": "AUTOPAPER_QUERIES_JSON",
    "sources": "AUTOPAPER_SOURCES",
    "collection_name": "AUTOPAPER_COLLECTION_NAME",
    "max_new": "AUTOPAPER_MAX_NEW",
    "max_results_per_query": "AUTOPAPER_MAX_RESULTS_PER_QUERY",
    "min_relevance_score": "AUTOPAPER_MIN_RELEVANCE_SCORE",
    "report_dir": "AUTOPAPER_REPORT_DIR",
    "state_dir": "AUTOPAPER_STATE_DIR",
    "attach_real_pdfs": "AUTOPAPER_ATTACH_REAL_PDFS",
    "enable_github_search": "AUTOPAPER_ENABLE_GITHUB_SEARCH",
    "schedule_cron": "AUTOPAPER_SCHEDULE_CRON",
    "timezone": "AUTOPAPER_TIMEZONE",
    "run_on_start": "AUTOPAPER_RUN_ON_START",
    "boost_terms": "AUTOPAPER_BOOST_TERMS_JSON",
    "penalty_terms": "AUTOPAPER_PENALTY_TERMS_JSON",
    "include_terms": "AUTOPAPER_INCLUDE_TERMS_JSON",
    "exclude_terms": "AUTOPAPER_EXCLUDE_TERMS_JSON",
    "summarizer": "AUTOPAPER_SUMMARIZER",
    "summary_fallback": "AUTOPAPER_SUMMARY_FALLBACK",
    "llm_base_url": "AUTOPAPER_LLM_BASE_URL",
    "llm_api_key": "AUTOPAPER_LLM_API_KEY",
    "llm_model": "AUTOPAPER_LLM_MODEL",
    "llm_timeout_seconds": "AUTOPAPER_LLM_TIMEOUT_SECONDS",
    "summary_command": "AUTOPAPER_SUMMARY_COMMAND",
}


class ConfigError(ValueError):
    pass


def llm_base_url_is_local(llm_base_url: Optional[str]) -> bool:
    if not llm_base_url:
        return False
    host = (urlparse(llm_base_url).hostname or "").lower()
    return host in {"127.0.0.1", "localhost", "::1"}



def _cron_looks_valid(cron_expr: str) -> bool:
    return len((cron_expr or "").split()) == 5



def _merge_lists(*parts: Iterable[str]) -> List[str]:
    merged: List[str] = []
    seen: set[str] = set()
    for values in parts:
        for value in values:
            if not value or value in seen:
                continue
            seen.add(value)
            merged.append(value)
    return merged



def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ConfigError(f"{name} must be an integer") from exc



def resolve_runtime_config(args: Any) -> RuntimeConfig:
    env_file = getattr(args, "env_file", None)
    load_env_file(env_file)

    preset_name = getattr(args, "query_preset", None) or os.getenv(COMMON_ENV_KEYS["query_preset"]) or DEFAULT_PRESET
    preset: QueryPreset = get_preset(preset_name)

    env_queries = parse_json_array(os.getenv(COMMON_ENV_KEYS["queries_json"]), COMMON_ENV_KEYS["queries_json"])
    cli_queries = list(getattr(args, "queries", None) or [])

    env_sources = comma_split(os.getenv(COMMON_ENV_KEYS["sources"]))
    cli_sources = list(getattr(args, "sources", None) or [])

    profile_name = getattr(args, "profile_name", None) or os.getenv(COMMON_ENV_KEYS["profile_name"]) or "default"
    collection_name = getattr(args, "collection_name", None) or os.getenv(COMMON_ENV_KEYS["collection_name"]) or preset.collection_name
    max_new = getattr(args, "max_new", None)
    max_new = int(max_new if max_new is not None else _int_env(COMMON_ENV_KEYS["max_new"], 2))
    max_results = getattr(args, "max_results_per_query", None)
    max_results = int(max_results if max_results is not None else _int_env(COMMON_ENV_KEYS["max_results_per_query"], 25))
    min_score = getattr(args, "min_relevance_score", None)
    min_score = int(min_score if min_score is not None else _int_env(COMMON_ENV_KEYS["min_relevance_score"], preset.min_relevance_score))

    dry_run = parse_bool(getattr(args, "dry_run", None), default=False)
    attach_real_pdfs = parse_bool(
        getattr(args, "attach_real_pdfs", None),
        default=parse_bool(os.getenv(COMMON_ENV_KEYS["attach_real_pdfs"]), False),
    )

    no_github_search = parse_bool(getattr(args, "no_github_search", None), default=False)
    enable_github_search = not no_github_search
    if not no_github_search and getattr(args, "no_github_search", None) is None:
        enable_github_search = parse_bool(os.getenv(COMMON_ENV_KEYS["enable_github_search"]), True)

    report_dir = getattr(args, "report_dir", None) or os.getenv(COMMON_ENV_KEYS["report_dir"]) or "reports"
    state_dir = getattr(args, "state_dir", None) or os.getenv(COMMON_ENV_KEYS["state_dir"]) or ".autopaper_state"
    timezone = getattr(args, "timezone", None) or os.getenv(COMMON_ENV_KEYS["timezone"])
    schedule_cron = getattr(args, "schedule_cron", None) or os.getenv(COMMON_ENV_KEYS["schedule_cron"]) or "0 9 * * *"
    run_on_start = parse_bool(
        getattr(args, "run_on_start", None),
        default=parse_bool(os.getenv(COMMON_ENV_KEYS["run_on_start"]), False),
    )

    boost_terms = parse_json_array(os.getenv(COMMON_ENV_KEYS["boost_terms"]), COMMON_ENV_KEYS["boost_terms"])
    penalty_terms = parse_json_array(os.getenv(COMMON_ENV_KEYS["penalty_terms"]), COMMON_ENV_KEYS["penalty_terms"])
    include_terms = parse_json_array(os.getenv(COMMON_ENV_KEYS["include_terms"]), COMMON_ENV_KEYS["include_terms"])
    exclude_terms = parse_json_array(os.getenv(COMMON_ENV_KEYS["exclude_terms"]), COMMON_ENV_KEYS["exclude_terms"])

    summarizer = (getattr(args, "summarizer", None) or os.getenv(COMMON_ENV_KEYS["summarizer"]) or "offline").strip()
    summary_fallback = (os.getenv(COMMON_ENV_KEYS["summary_fallback"]) or "offline").strip()
    llm_base_url = os.getenv(COMMON_ENV_KEYS["llm_base_url"])
    llm_api_key = os.getenv(COMMON_ENV_KEYS["llm_api_key"])
    llm_model = os.getenv(COMMON_ENV_KEYS["llm_model"])
    llm_timeout_seconds = _int_env(COMMON_ENV_KEYS["llm_timeout_seconds"], 60)
    summary_command = os.getenv(COMMON_ENV_KEYS["summary_command"])

    sources = _merge_lists(env_sources, cli_sources) if (env_sources or cli_sources) else list(preset.sources)

    config = RuntimeConfig(
        profile_name=profile_name,
        query_preset=preset.name,
        queries=_merge_lists(preset.queries, env_queries, cli_queries),
        sources=sources,
        collection_name=collection_name,
        max_new=max_new,
        max_results_per_query=max_results,
        min_relevance_score=min_score,
        dry_run=dry_run,
        attach_real_pdfs=attach_real_pdfs,
        enable_github_search=enable_github_search,
        report_dir=report_dir,
        state_dir=state_dir,
        timezone=timezone,
        schedule_cron=schedule_cron,
        run_on_start=run_on_start,
        boost_terms=_merge_lists(preset.boost_terms, boost_terms),
        penalty_terms=_merge_lists(preset.penalty_terms, penalty_terms),
        include_terms=_merge_lists(preset.include_terms, include_terms),
        exclude_terms=_merge_lists(preset.exclude_terms, exclude_terms),
        summarizer=summarizer,
        summary_fallback=summary_fallback,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        llm_model=llm_model,
        llm_timeout_seconds=llm_timeout_seconds,
        summary_command=summary_command,
        zotero_user_id=getattr(args, "zotero_user_id", None) or os.getenv("ZOTERO_USER_ID"),
        zotero_api_key=getattr(args, "zotero_api_key", None) or os.getenv("ZOTERO_API_KEY"),
        pubmed_email=os.getenv("PUBMED_EMAIL"),
        pubmed_api_key=os.getenv("PUBMED_API_KEY"),
        openalex_mailto=os.getenv("OPENALEX_MAILTO"),
        github_token=os.getenv("GITHUB_TOKEN"),
    )
    validate_runtime_config(config, command=getattr(args, "command", "run-once"))
    return config



def validate_runtime_config(config: RuntimeConfig, command: str = "run-once") -> None:
    if not config.queries:
        raise ConfigError("At least one query is required via preset or AUTOPAPER_QUERIES_JSON or --query")
    if not config.sources:
        raise ConfigError("At least one source is required via preset or AUTOPAPER_SOURCES or --source")
    unknown_sources = [source for source in config.sources if source not in VALID_SOURCES]
    if unknown_sources:
        raise ConfigError(f"Unsupported sources: {', '.join(sorted(set(unknown_sources)))}")
    if config.summarizer not in VALID_SUMMARIZERS:
        raise ConfigError(f"Unsupported summarizer: {config.summarizer}")
    if config.summary_fallback not in VALID_SUMMARIZERS:
        raise ConfigError(f"Unsupported summary fallback: {config.summary_fallback}")
    if command in {"daemon", "validate-config"} and not config.zotero_api_key:
        raise ConfigError("Missing ZOTERO_API_KEY")
    if command == "run-once" and not config.dry_run and not config.zotero_api_key:
        raise ConfigError("Missing ZOTERO_API_KEY")
    if config.summarizer == "openai_compatible":
        missing = [
            key
            for key, value in {
                "AUTOPAPER_LLM_BASE_URL": config.llm_base_url,
                "AUTOPAPER_LLM_MODEL": config.llm_model,
            }.items()
            if not value
        ]
        if not config.llm_api_key and not llm_base_url_is_local(config.llm_base_url):
            missing.append("AUTOPAPER_LLM_API_KEY")
        if missing:
            raise ConfigError(f"Missing LLM configuration: {', '.join(missing)}")
    if config.summarizer == "command" and not config.summary_command:
        raise ConfigError("AUTOPAPER_SUMMARY_COMMAND is required when AUTOPAPER_SUMMARIZER=command")
    if not _cron_looks_valid(config.schedule_cron):
        raise ConfigError("AUTOPAPER_SCHEDULE_CRON / --schedule-cron must be a 5-field cron expression")
    Path(config.report_dir).mkdir(parents=True, exist_ok=True)
    Path(config.state_dir).mkdir(parents=True, exist_ok=True)



def config_as_json(config: RuntimeConfig) -> str:
    return json.dumps(config.to_public_dict(), indent=2, sort_keys=True)
