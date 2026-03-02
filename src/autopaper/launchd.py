from __future__ import annotations

import plistlib
import re
import sys
from pathlib import Path
from typing import Optional

from autopaper.config import RuntimeConfig
from autopaper.utils import ensure_directory


def launchd_label(profile_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", (profile_name or "default").strip().lower()).strip("-")
    return f"com.autopaper.{slug or 'default'}"


def build_launchd_plist(
    config: RuntimeConfig,
    *,
    env_file: Optional[str],
    python_executable: Optional[str],
    working_dir: Optional[str],
) -> str:
    workdir = Path(working_dir or Path.cwd()).resolve()
    python_bin = Path(python_executable or sys.executable).resolve()
    state_root = Path(config.state_dir).expanduser()
    if not state_root.is_absolute():
        state_root = (workdir / state_root).resolve()
    logs_dir = ensure_directory(state_root / "logs")
    label = launchd_label(config.profile_name)

    program_args = [str(python_bin), "-m", "autopaper.cli", "daemon"]
    if env_file:
        program_args.extend(["--env-file", str(Path(env_file).resolve())])

    env_vars = {
        "PYTHONUNBUFFERED": "1",
        "PYTHONPATH": str((workdir / "src").resolve()),
    }
    if config.timezone:
        env_vars["TZ"] = config.timezone

    payload = {
        "Label": label,
        "ProgramArguments": program_args,
        "WorkingDirectory": str(workdir),
        "RunAtLoad": True,
        "KeepAlive": True,
        "ProcessType": "Background",
        "EnvironmentVariables": env_vars,
        "StandardOutPath": str(logs_dir / f"{config.profile_name}.launchd.out.log"),
        "StandardErrorPath": str(logs_dir / f"{config.profile_name}.launchd.err.log"),
    }
    return plistlib.dumps(payload).decode("utf-8")


def write_launchd_plist(
    output_path: str,
    config: RuntimeConfig,
    *,
    env_file: Optional[str],
    python_executable: Optional[str],
    working_dir: Optional[str],
) -> str:
    target = Path(output_path).expanduser().resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        build_launchd_plist(
            config,
            env_file=env_file,
            python_executable=python_executable,
            working_dir=working_dir,
        ),
        encoding="utf-8",
    )
    return str(target)
