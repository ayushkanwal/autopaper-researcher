# Auto Paper Populator

Distributable Python tooling for researchers who want to:
- discover new papers on a schedule
- rank them against their own research interests
- ingest them into Zotero
- attach structured summary notes
- optionally attach linked or real PDF files
- keep local reports and run state
- back up or clean up Zotero attachment storage

## Fastest Start

This is the shortest working path for a local Zotero + local Ollama setup.

### 1. Clone the repo and create a local config

```bash
git clone https://github.com/ayushkanwal/autopaper-researcher.git
cd autopaper-researcher
cp examples/ollama_local.env .env.local
```

### 2. Edit `.env.local`

Set at least these values:

```bash
ZOTERO_USER_ID=your_zotero_user_id
ZOTERO_API_KEY=your_zotero_api_key
AUTOPAPER_COLLECTION_NAME=autopaper-ingested
AUTOPAPER_QUERIES_JSON=["all:\"multivariate time series\" AND (all:forecasting OR all:prediction)"]
AUTOPAPER_BOOST_TERMS_JSON=["multivariate","forecasting","retrieval"]
AUTOPAPER_PENALTY_TERMS_JSON=["stock price","cryptocurrency"]
```

### 3. Start Ollama

```bash
ollama pull qwen2.5:3b-instruct
ollama serve
```

### 4. Run a dry-run

```bash
./scripts/bootstrap_and_run.sh --env-file .env.local --dry-run
```

### 5. Run a live ingest

```bash
./scripts/bootstrap_and_run.sh --env-file .env.local
```

What this does:
- searches `arXiv`, `PubMed`, and `OpenAlex`
- ranks results using your preset and keyword overrides
- summarizes selected papers with local Ollama
- adds them to Zotero with structured notes
- optionally imports real PDFs if `AUTOPAPER_ATTACH_REAL_PDFS=true`

## Core Concepts

### Search

Paper discovery uses the built-in source adapters:
- `arXiv`
- `PubMed`
- `OpenAlex`

### Ranking

The core ranking engine is intentionally generic.

Researcher-specific relevance should be controlled with:
- built-in presets
- `AUTOPAPER_BOOST_TERMS_JSON`
- `AUTOPAPER_PENALTY_TERMS_JSON`
- `AUTOPAPER_INCLUDE_TERMS_JSON`
- `AUTOPAPER_EXCLUDE_TERMS_JSON`

### Summaries

Summary generation happens after papers are found and ranked.

Supported modes:
- `offline`
- `openai_compatible`
- `command`

For local Ollama, use:

```bash
AUTOPAPER_SUMMARIZER=openai_compatible
AUTOPAPER_SUMMARY_FALLBACK=offline
AUTOPAPER_LLM_BASE_URL=http://127.0.0.1:11434/v1
AUTOPAPER_LLM_API_KEY=
AUTOPAPER_LLM_MODEL=qwen2.5:3b-instruct
```

### Zotero

Zotero is the write target in v1.

The tool can:
- create collections if needed
- add paper items
- attach summary notes
- attach PDF links
- optionally import real PDF files

## Install Options

### Default: one-command runner

Use the bootstrap script if you want the shortest path:

```bash
./scripts/bootstrap_and_run.sh --env-file .env.local --dry-run
```

The script:
- creates `.venv`
- uses the source tree directly
- installs the package only if needed
- validates config
- runs the requested command

### Manual install

Use this if you want direct CLI control:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
```

Then run commands such as:

```bash
autopaper validate-config --env-file .env.local
autopaper run-once --env-file .env.local --dry-run
autopaper run-once --env-file .env.local
```

## Configuration Reference

### Required
- `ZOTERO_USER_ID`
- `ZOTERO_API_KEY`

### Main research profile
- `AUTOPAPER_PROFILE_NAME`
- `AUTOPAPER_QUERY_PRESET`
- `AUTOPAPER_QUERIES_JSON`
- `AUTOPAPER_SOURCES`
- `AUTOPAPER_COLLECTION_NAME`
- `AUTOPAPER_MAX_NEW`
- `AUTOPAPER_MAX_RESULTS_PER_QUERY`
- `AUTOPAPER_MIN_RELEVANCE_SCORE`

### Ranking overrides
- `AUTOPAPER_BOOST_TERMS_JSON`
- `AUTOPAPER_PENALTY_TERMS_JSON`
- `AUTOPAPER_INCLUDE_TERMS_JSON`
- `AUTOPAPER_EXCLUDE_TERMS_JSON`

### Summary provider
- `AUTOPAPER_SUMMARIZER`
- `AUTOPAPER_SUMMARY_FALLBACK`
- `AUTOPAPER_LLM_BASE_URL`
- `AUTOPAPER_LLM_API_KEY`
- `AUTOPAPER_LLM_MODEL`
- `AUTOPAPER_LLM_TIMEOUT_SECONDS`
- `AUTOPAPER_SUMMARY_COMMAND`

### Scheduling
- `AUTOPAPER_SCHEDULE_CRON`
- `AUTOPAPER_TIMEZONE`
- `AUTOPAPER_RUN_ON_START`

### Output and behavior
- `AUTOPAPER_REPORT_DIR`
- `AUTOPAPER_STATE_DIR`
- `AUTOPAPER_ATTACH_REAL_PDFS`
- `AUTOPAPER_ENABLE_GITHUB_SEARCH`

### Source-specific optional settings
- `PUBMED_EMAIL`
- `PUBMED_API_KEY`
- `OPENALEX_MAILTO`
- `GITHUB_TOKEN`

## Built-In Presets

Current presets:
- `general_time_series_v1`
- `livestock_decision_support_v1`
- `livestock_decision_support_v2`

List them from the CLI:

```bash
PYTHONPATH=src python3 -m autopaper.cli list-presets
```

Show exactly what your env resolves to:

```bash
PYTHONPATH=src python3 -m autopaper.cli print-effective-config --env-file .env.local
```

## Common Commands

### Validate config

```bash
./scripts/bootstrap_and_run.sh --env-file .env.local --dry-run
```

Or manually:

```bash
PYTHONPATH=src python3 -m autopaper.cli validate-config --env-file .env.local
```

### One ingest pass

```bash
./scripts/bootstrap_and_run.sh --env-file .env.local
```

Or manually:

```bash
PYTHONPATH=src python3 -m autopaper.cli run-once --env-file .env.local
```

### Foreground scheduler

```bash
./scripts/bootstrap_and_run.sh --env-file .env.local --daemon
```

Or manually:

```bash
PYTHONPATH=src python3 -m autopaper.cli daemon --env-file .env.local --run-on-start
```

## macOS Scheduling

Generate a `launchd` plist:

```bash
PYTHONPATH=src python3 -m autopaper.cli write-launchd-plist --env-file .env.local --output ~/Library/LaunchAgents/com.autopaper.researcher.plist
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

The `launchd` service keeps the daemon alive. The ingest schedule still comes from `AUTOPAPER_SCHEDULE_CRON`.

## Zotero Attachment Backup and Cleanup

Back up stored attachments:

```bash
PYTHONPATH=src python3 -m autopaper.cli backup-attachments --env-file .env.local --dry-run
```

Back up and delete remote attachments after successful backup:

```bash
PYTHONPATH=src python3 -m autopaper.cli backup-attachments --env-file .env.local --delete-remote
```

Preview a My Library purge:

```bash
PYTHONPATH=src python3 -m autopaper.cli purge-attachments --env-file .env.local --dry-run
```

Run a live purge of My Library file attachments:

```bash
PYTHONPATH=src python3 -m autopaper.cli purge-attachments --env-file .env.local --confirm-my-library
```

Important:
- `purge-attachments` is intentionally My Library only
- it deletes matching remote attachment items
- it attempts to empty My Library trash
- it removes matching local Zotero storage directories

## Example Files

- `.env.example`
- `examples/researcher_template.env`
- `examples/livestock_decision_support.env`
- `examples/ollama_local.env`

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
