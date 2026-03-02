# Auto Paper Populator

Lightweight Python tooling for researchers who want to:
- discover new papers on a schedule
- ingest them into Zotero
- attach structured summary notes
- optionally attach linked or real PDF files
- keep per-run reports and local state
- back up or clean up Zotero attachment storage

This public repo contains only the distributable package, wrapper scripts, templates, and run instructions.

## Fastest Start: Local Ollama + Zotero

If you want the shortest path to a working local setup:

```bash
git clone https://github.com/ayushkanwal/autopaper-researcher.git
cd autopaper-researcher
cp examples/ollama_local.env .env.local
```

Edit `.env.local` and set at least:

```bash
ZOTERO_USER_ID=your_zotero_user_id
ZOTERO_API_KEY=your_zotero_api_key
AUTOPAPER_COLLECTION_NAME=autopaper-ingested
AUTOPAPER_QUERIES_JSON=["all:\"multivariate time series\" AND (all:forecasting OR all:prediction)"]
AUTOPAPER_BOOST_TERMS_JSON=["multivariate","forecasting","retrieval"]
AUTOPAPER_PENALTY_TERMS_JSON=["stock price","cryptocurrency"]
```

Start Ollama:

```bash
ollama pull qwen2.5:3b-instruct
ollama serve
```

Run a dry-run first:

```bash
./scripts/bootstrap_and_run.sh --env-file .env.local --dry-run
```

Then run the real ingest:

```bash
./scripts/bootstrap_and_run.sh --env-file .env.local
```

What this does:
- searches `arXiv`, `PubMed`, and `OpenAlex`
- ranks results using your preset and keyword overrides
- summarizes selected papers with local Ollama
- adds them to Zotero with notes
- optionally imports real PDFs if `AUTOPAPER_ATTACH_REAL_PDFS=true`

## Features

Paper ingest:
- search `arXiv`, `PubMed`, and `OpenAlex`
- merge cross-source duplicates
- rank papers against configurable research presets
- deduplicate against Zotero by DOI, source ID, and title
- add papers to a chosen Zotero collection
- attach structured summary notes
- try to discover PDF links and code repositories
- optionally import real PDFs into Zotero storage
- write Markdown and JSON reports
- keep local SQLite run/state tracking

Search and summarization are separate:
- paper discovery uses the built-in source adapters: `arXiv`, `PubMed`, and `OpenAlex`
- local Ollama or other LLM providers are only used to generate summary notes after papers are found and ranked

Ranking is intentionally generic in the core package:
- researcher-specific relevance should be controlled with presets plus `AUTOPAPER_BOOST_TERMS_JSON`, `AUTOPAPER_PENALTY_TERMS_JSON`, `AUTOPAPER_INCLUDE_TERMS_JSON`, and `AUTOPAPER_EXCLUDE_TERMS_JSON`
- avoid hardcoding domain logic into the shared ranking engine

Zotero maintenance:
- back up stored Zotero attachments locally
- optionally delete backed-up remote attachments
- purge My Library file attachments and matching local Zotero storage folders

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

This installs the `autopaper` CLI and dependencies.

If you want a single command that sets up `.venv`, installs the package, validates the config, and runs the tool, use:

```bash
./scripts/bootstrap_and_run.sh --env-file .env.local --dry-run
```

## Quick Start

If you just want the shortest working path, use the `Fastest Start: Local Ollama + Zotero` section above. The rest of this README explains the same setup in more detail.

### 1. Create a config file

Use the generic template:

```bash
cp .env.example .env.local
```

Or start from the researcher template:

```bash
cp examples/researcher_template.env .env.local
```

### 2. Fill the required credentials

Minimum required:
- `ZOTERO_USER_ID`
- `ZOTERO_API_KEY`

Useful optional values:
- `OPENALEX_MAILTO`
- `PUBMED_EMAIL`
- `PUBMED_API_KEY`
- `GITHUB_TOKEN`

### 2a. Edit the search setup

The most important search controls live in `.env.local`:

- `AUTOPAPER_QUERY_PRESET`
  - choose a built-in preset such as `general_time_series_v1` or `livestock_decision_support_v2`
- `AUTOPAPER_QUERIES_JSON`
  - add your own extra search queries as a JSON array of strings
- `AUTOPAPER_SOURCES`
  - choose which search sources to use, for example `arxiv,pubmed,openalex`
- `AUTOPAPER_MIN_RELEVANCE_SCORE`
  - raise this if results are too broad, lower it if too few papers are added
- `AUTOPAPER_BOOST_TERMS_JSON`
  - terms that should increase ranking
- `AUTOPAPER_PENALTY_TERMS_JSON`
  - terms that should decrease ranking
- `AUTOPAPER_INCLUDE_TERMS_JSON`
  - terms that must appear for a paper to be considered
- `AUTOPAPER_EXCLUDE_TERMS_JSON`
  - terms that should filter papers out completely

Example:

```bash
AUTOPAPER_QUERY_PRESET=general_time_series_v1
AUTOPAPER_QUERIES_JSON=["all:\"causal time series\" AND (all:forecasting OR all:prediction)","all:\"time series\" AND (all:retrieval OR all:rag)"]
AUTOPAPER_SOURCES=arxiv,pubmed,openalex
AUTOPAPER_BOOST_TERMS_JSON=["causal","retrieval","rag","multivariate"]
AUTOPAPER_PENALTY_TERMS_JSON=["stock price","cryptocurrency"]
```

### 2b. Set the Zotero target

These variables are what make the tool usable at all:

- `ZOTERO_USER_ID`
- `ZOTERO_API_KEY`
- `AUTOPAPER_COLLECTION_NAME`

Example:

```bash
ZOTERO_USER_ID=1234567
ZOTERO_API_KEY=your_zotero_api_key
AUTOPAPER_COLLECTION_NAME=autopaper-ingested
```

The ingest pipeline writes to Zotero. Without those values, it cannot add papers or notes.

### 2c. Choose how summaries are generated

Summary generation is controlled by:

- `AUTOPAPER_SUMMARIZER`
  - `offline`
  - `openai_compatible`
  - `command`
- `AUTOPAPER_SUMMARY_FALLBACK`
- `AUTOPAPER_LLM_BASE_URL`
- `AUTOPAPER_LLM_API_KEY`
- `AUTOPAPER_LLM_MODEL`
- `AUTOPAPER_SUMMARY_COMMAND`

Offline only:

```bash
AUTOPAPER_SUMMARIZER=offline
AUTOPAPER_SUMMARY_FALLBACK=offline
```

OpenAI-compatible LLM:

```bash
AUTOPAPER_SUMMARIZER=openai_compatible
AUTOPAPER_SUMMARY_FALLBACK=offline
AUTOPAPER_LLM_BASE_URL=https://api.openai.com/v1
AUTOPAPER_LLM_API_KEY=your_api_key
AUTOPAPER_LLM_MODEL=gpt-4.1-mini
```

Local Ollama:

```bash
AUTOPAPER_SUMMARIZER=openai_compatible
AUTOPAPER_SUMMARY_FALLBACK=offline
AUTOPAPER_LLM_BASE_URL=http://127.0.0.1:11434/v1
AUTOPAPER_LLM_API_KEY=
AUTOPAPER_LLM_MODEL=qwen2.5:3b-instruct
```

This path is tested against Ollama's OpenAI-compatible endpoint. Localhost endpoints do not require an API key.

External command:

```bash
AUTOPAPER_SUMMARIZER=command
AUTOPAPER_SUMMARY_FALLBACK=offline
AUTOPAPER_SUMMARY_COMMAND=python3 my_custom_summary_pipeline.py
```

### 3. Validate config

```bash
autopaper validate-config --env-file .env.local
```

### 4. Run a dry-run ingest

```bash
autopaper run-once --env-file .env.local --dry-run
```

### 5. Run a live ingest

```bash
autopaper run-once --env-file .env.local
```

### One-command run

After `.env.local` is ready:

```bash
./scripts/bootstrap_and_run.sh --env-file .env.local
```

To start the foreground scheduler instead:

```bash
./scripts/bootstrap_and_run.sh --env-file .env.local --daemon
```

## Main Commands

### Paper Ingest

List presets:

```bash
autopaper list-presets
```

Show resolved config:

```bash
autopaper print-effective-config --env-file .env.local
```

Run one ingest pass:

```bash
autopaper run-once --env-file .env.local
```

Run the daemon in the foreground:

```bash
autopaper daemon --env-file .env.local --run-on-start
```

### macOS Scheduling

Generate a `launchd` plist:

```bash
autopaper write-launchd-plist --env-file .env.local --output ~/Library/LaunchAgents/com.autopaper.researcher.plist
```

Load it:

```bash
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.autopaper.researcher.plist
launchctl enable gui/$(id -u)/com.autopaper.researcher
launchctl kickstart -k gui/$(id -u)/com.autopaper.researcher
```

Unload it:

```bash
launchctl bootout gui/$(id -u) ~/Library/LaunchAgents/com.autopaper.researcher.plist
```

The `launchd` service keeps the daemon alive. The actual ingest schedule still comes from `AUTOPAPER_SCHEDULE_CRON`.

### Zotero Backup and Cleanup

Back up stored attachments:

```bash
autopaper backup-attachments --env-file .env.local --dry-run
```

Back up and delete the remote attachments after successful backup:

```bash
autopaper backup-attachments --env-file .env.local --delete-remote
```

Preview a purge:

```bash
autopaper purge-attachments --env-file .env.local --dry-run
```

Run a live purge of My Library file attachments:

```bash
autopaper purge-attachments --env-file .env.local --confirm-my-library
```

Important:
- `purge-attachments` is intentionally My Library only
- it deletes matching remote attachment items
- it attempts to empty My Library trash
- it removes matching local Zotero storage directories

## Presets

Built-in presets:
- `livestock_decision_support_v2`
- `livestock_decision_support_v1`
- `general_time_series_v1`

The package supports:
- preset-driven discovery
- extra custom queries
- per-researcher env files
- optional summary providers
- all current built-in presets use the full supported source set by default: `arxiv`, `pubmed`, and `openalex`

If you want to see exactly what a preset resolves to, run:

```bash
autopaper print-effective-config --env-file .env.local
```

## Summary Providers

Supported modes:
- `offline`
- `openai_compatible`
- `command`

### Offline

Default mode. Uses paper title, abstract, and metadata only.

### OpenAI-Compatible

Set:
- `AUTOPAPER_SUMMARIZER=openai_compatible`
- `AUTOPAPER_LLM_BASE_URL`
- `AUTOPAPER_LLM_API_KEY`
- `AUTOPAPER_LLM_MODEL`

### Local Ollama

Tested setup:

```bash
ollama pull qwen2.5:3b-instruct
ollama serve
```

Then use either:

```bash
cp examples/ollama_local.env .env.local
```

or set these values in your existing `.env.local`:

```bash
AUTOPAPER_SUMMARIZER=openai_compatible
AUTOPAPER_SUMMARY_FALLBACK=offline
AUTOPAPER_LLM_BASE_URL=http://127.0.0.1:11434/v1
AUTOPAPER_LLM_API_KEY=
AUTOPAPER_LLM_MODEL=qwen2.5:3b-instruct
```

Quick checks:

```bash
curl -sS http://127.0.0.1:11434/v1/models
autopaper validate-config --env-file .env.local
autopaper run-once --env-file .env.local --dry-run
```

Notes:
- Ollama is wired through the same `openai_compatible` summary provider.
- `AUTOPAPER_LLM_API_KEY` can be blank for local Ollama.
- Smaller local models are easier to run continuously. `qwen2.5:3b-instruct` is a practical starting point.
- If the local model fails or is too slow, keep `AUTOPAPER_SUMMARY_FALLBACK=offline`.

### External Command

Set:
- `AUTOPAPER_SUMMARIZER=command`
- `AUTOPAPER_SUMMARY_COMMAND`

The command receives JSON on stdin and must return the expected summary JSON payload.

## Example Files

- `.env.example`
- `examples/researcher_template.env`
- `examples/livestock_decision_support.env`
- `examples/ollama_local.env`

## Legacy Script Wrappers

These wrappers call into the packaged CLI:

```bash
python3 scripts/daily_research_ingest.py --dry-run
python3 scripts/ingest_latest_paper.py --dry-run --max-results 20
python3 scripts/import_pdf_files_for_collection.py --collection-name autopaper-ingested --dry-run
python3 scripts/backup_and_cleanup_attachments.py --dry-run
python3 scripts/purge_my_library_attachments.py --dry-run
```

## Repository Layout

```text
src/autopaper/      package source
scripts/            wrapper scripts
examples/           env templates
.env.example        starter config
pyproject.toml      package metadata
```

## Notes

- Do not commit real `.env.local` files or API keys.
- Reports and state are written locally and are ignored by `.gitignore`.
- This repo intentionally excludes private reports, backups, outputs, and local machine artifacts.
