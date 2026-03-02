from __future__ import annotations

import argparse
import json
import os

from autopaper.cleanup import (
    BackupAttachmentsConfig,
    CleanupCredentials,
    DEFAULT_ATTACHMENT_MODES,
    PurgeAttachmentsConfig,
    backup_attachments,
    purge_attachments,
)
from autopaper.config import ConfigError, config_as_json, resolve_runtime_config
from autopaper.job_runner import execute_run
from autopaper.launchd import build_launchd_plist, launchd_label, write_launchd_plist
from autopaper.logging import configure_logger
from autopaper.query_presets import list_presets
from autopaper.utils import load_env_file


def add_common_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--env-file", default=None, help="Path to .env file")
    parser.add_argument("--profile-name", default=None, help="Profile name")
    parser.add_argument("--query-preset", default=None, help="Query preset name")
    parser.add_argument("--query", action="append", dest="queries", help="Extra query (repeatable)")
    parser.add_argument("--source", action="append", dest="sources", help="Source adapter (repeatable)")
    parser.add_argument("--collection-name", default=None, help="Target Zotero collection")
    parser.add_argument("--max-new", type=int, default=None, help="Maximum new papers per run")
    parser.add_argument("--max-results-per-query", type=int, default=None, help="Maximum search results per query")
    parser.add_argument("--min-relevance-score", type=int, default=None, help="Minimum relevance score")
    parser.add_argument("--dry-run", action="store_true", default=None, help="Do not write to Zotero")
    parser.add_argument("--attach-real-pdfs", action="store_true", default=None, help="Import real PDF files after ingest")
    parser.add_argument("--no-github-search", action="store_true", default=None, help="Disable GitHub repository discovery")
    parser.add_argument("--report-dir", default=None, help="Report directory")
    parser.add_argument("--state-dir", default=None, help="State directory")
    parser.add_argument("--timezone", default=None, help="IANA timezone")
    parser.add_argument("--zotero-user-id", default=None, help="Override ZOTERO_USER_ID")
    parser.add_argument("--zotero-api-key", default=None, help="Override ZOTERO_API_KEY")
    parser.add_argument("--summarizer", default=None, choices=["offline", "openai_compatible", "command"], help="Summary provider")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="autopaper", description="Distributable research paper ingest daemon")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_once = subparsers.add_parser("run-once", help="Run one ingest pass")
    add_common_args(run_once)

    daemon = subparsers.add_parser("daemon", help="Run the scheduler daemon")
    add_common_args(daemon)
    daemon.add_argument("--schedule-cron", default=None, help="Cron expression, e.g. '0 9 * * *'")
    daemon.add_argument("--run-on-start", action="store_true", default=None, help="Run once immediately before scheduling")

    validate = subparsers.add_parser("validate-config", help="Validate the effective configuration")
    add_common_args(validate)
    validate.add_argument("--schedule-cron", default=None, help="Cron expression to validate")
    validate.add_argument("--run-on-start", action="store_true", default=None, help="Validate run-on-start flag")

    subparsers.add_parser("list-presets", help="List built-in query presets")

    print_config = subparsers.add_parser("print-effective-config", help="Print the resolved runtime config")
    add_common_args(print_config)
    print_config.add_argument("--schedule-cron", default=None, help="Optional cron expression")
    print_config.add_argument("--run-on-start", action="store_true", default=None, help="Optional run-on-start flag")

    print_launchd = subparsers.add_parser("print-launchd-plist", help="Print a macOS launchd plist for the daemon")
    add_common_args(print_launchd)
    print_launchd.add_argument("--python-executable", default=None, help="Python executable for launchd")
    print_launchd.add_argument("--working-dir", default=None, help="Working directory for launchd")

    write_launchd = subparsers.add_parser("write-launchd-plist", help="Write a macOS launchd plist for the daemon")
    add_common_args(write_launchd)
    write_launchd.add_argument("--python-executable", default=None, help="Python executable for launchd")
    write_launchd.add_argument("--working-dir", default=None, help="Working directory for launchd")
    write_launchd.add_argument("--output", required=True, help="Output path for the launchd plist")

    backup_cmd = subparsers.add_parser("backup-attachments", help="Back up Zotero stored attachments and optionally delete remote copies")
    backup_cmd.add_argument("--env-file", default=None, help="Path to .env file")
    backup_cmd.add_argument("--zotero-user-id", default=None, help="Override ZOTERO_USER_ID")
    backup_cmd.add_argument("--zotero-api-key", default=None, help="Override ZOTERO_API_KEY")
    backup_cmd.add_argument("--modes", default=",".join(DEFAULT_ATTACHMENT_MODES), help="Comma-separated attachment link modes")
    backup_cmd.add_argument("--backup-root", default="local_backups/zotero_attachments", help="Backup root directory")
    backup_cmd.add_argument("--report-dir", default="reports", help="Report directory")
    backup_cmd.add_argument("--limit", type=int, default=0, help="Limit targeted attachments")
    backup_cmd.add_argument("--backup-from-item-url-on-missing-file", action="store_true", default=None, help="Fallback to attachment URL when Zotero file is missing")
    backup_cmd.add_argument("--delete-remote", action="store_true", default=None, help="Delete backed-up attachment items from Zotero")
    backup_cmd.add_argument("--delete-when-no-remote-file", action="store_true", default=None, help="Delete attachment records even when Zotero-hosted file is missing")
    backup_cmd.add_argument("--dry-run", action="store_true", default=None, help="Inspect only, do not download or delete")

    purge_cmd = subparsers.add_parser("purge-attachments", help="Purge My Library file attachments and matching local Zotero storage folders")
    purge_cmd.add_argument("--env-file", default=None, help="Path to .env file")
    purge_cmd.add_argument("--zotero-user-id", default=None, help="Override ZOTERO_USER_ID")
    purge_cmd.add_argument("--zotero-api-key", default=None, help="Override ZOTERO_API_KEY")
    purge_cmd.add_argument("--modes", default=",".join(DEFAULT_ATTACHMENT_MODES), help="Comma-separated attachment link modes")
    purge_cmd.add_argument("--zotero-storage-dir", default=os.path.expanduser("~/Zotero/storage"), help="Local Zotero storage directory")
    purge_cmd.add_argument("--report-dir", default="reports", help="Report directory")
    purge_cmd.add_argument("--dry-run", action="store_true", default=None, help="Preview only, do not delete")
    purge_cmd.add_argument("--confirm-my-library", action="store_true", default=None, help="Required for live purge to acknowledge My Library scope")

    return parser


def _resolve_cleanup_credentials(args: argparse.Namespace) -> CleanupCredentials:
    load_env_file(getattr(args, "env_file", None))
    user_id = getattr(args, "zotero_user_id", None) or os.getenv("ZOTERO_USER_ID")
    api_key = getattr(args, "zotero_api_key", None) or os.getenv("ZOTERO_API_KEY")
    if not api_key:
        raise ConfigError("Missing ZOTERO_API_KEY")
    return CleanupCredentials(user_id=user_id, api_key=api_key)


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "list-presets":
        payload = [{"name": preset.name, "description": preset.description, "sources": preset.sources} for preset in list_presets()]
        print(json.dumps(payload, indent=2))
        return 0

    if args.command == "backup-attachments":
        try:
            credentials = _resolve_cleanup_credentials(args)
        except ConfigError as exc:
            parser.error(str(exc))
            return 2
        report, exit_code = backup_attachments(
            BackupAttachmentsConfig(
                credentials=credentials,
                modes=[mode.strip() for mode in args.modes.split(",") if mode.strip()],
                backup_root=args.backup_root,
                report_dir=args.report_dir,
                limit=args.limit,
                backup_from_item_url_on_missing_file=bool(args.backup_from_item_url_on_missing_file),
                delete_remote=bool(args.delete_remote),
                delete_when_no_remote_file=bool(args.delete_when_no_remote_file),
                dry_run=bool(args.dry_run),
            )
        )
        print(json.dumps(report, indent=2))
        return exit_code

    if args.command == "purge-attachments":
        try:
            credentials = _resolve_cleanup_credentials(args)
            report, exit_code = purge_attachments(
                PurgeAttachmentsConfig(
                    credentials=credentials,
                    modes=[mode.strip() for mode in args.modes.split(",") if mode.strip()],
                    zotero_storage_dir=args.zotero_storage_dir,
                    report_dir=args.report_dir,
                    dry_run=bool(args.dry_run),
                    confirm_my_library=bool(args.confirm_my_library),
                )
            )
        except ConfigError as exc:
            parser.error(str(exc))
            return 2
        except ValueError as exc:
            parser.error(str(exc))
            return 2
        print(json.dumps(report, indent=2))
        return exit_code

    try:
        config = resolve_runtime_config(args)
    except ConfigError as exc:
        parser.error(str(exc))
        return 2

    if args.command == "print-effective-config":
        print(config_as_json(config))
        return 0

    if args.command == "print-launchd-plist":
        print(
            build_launchd_plist(
                config,
                env_file=getattr(args, "env_file", None),
                python_executable=getattr(args, "python_executable", None),
                working_dir=getattr(args, "working_dir", None),
            )
        )
        return 0

    if args.command == "write-launchd-plist":
        path = write_launchd_plist(
            getattr(args, "output"),
            config,
            env_file=getattr(args, "env_file", None),
            python_executable=getattr(args, "python_executable", None),
            working_dir=getattr(args, "working_dir", None),
        )
        print(json.dumps({"label": launchd_label(config.profile_name), "output": path}, indent=2))
        return 0

    if args.command == "validate-config":
        print("Configuration valid")
        print(config_as_json(config))
        return 0

    if args.command == "run-once":
        logger = configure_logger(config.profile_name, config.state_dir)
        report = execute_run(config, logger=logger, scheduler_context={"mode": "run-once"})
        print(json.dumps(report.to_dict(), indent=2))
        return 0 if not report.failures else 1

    if args.command == "daemon":
        from autopaper.daemon import run_daemon

        return run_daemon(config)

    parser.error(f"Unhandled command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
