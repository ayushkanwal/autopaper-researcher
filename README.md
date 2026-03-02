# Auto Paper Populator

Lightweight Python tooling for researchers who want to:
- discover new papers on a schedule
- ingest them into Zotero
- attach structured summary notes
- optionally attach linked or real PDF files
- keep per-run reports and local state
- back up or clean up Zotero attachment storage

This public repo contains only the distributable package, wrapper scripts, templates, and run instructions.

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

## Quick Start

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

### External Command

Set:
- `AUTOPAPER_SUMMARIZER=command`
- `AUTOPAPER_SUMMARY_COMMAND`

The command receives JSON on stdin and must return the expected summary JSON payload.

## Example Files

- `.env.example`
- `examples/researcher_template.env`
- `examples/livestock_decision_support.env`

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
