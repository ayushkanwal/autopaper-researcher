from __future__ import annotations

import logging as pylogging
from pathlib import Path

from autopaper.utils import ensure_directory



def configure_logger(profile_name: str, state_dir: str) -> pylogging.Logger:
    logger_name = f"autopaper.{profile_name}"
    logger = pylogging.getLogger(logger_name)
    if logger.handlers:
        return logger
    logger.setLevel(pylogging.INFO)
    formatter = pylogging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")

    stream_handler = pylogging.StreamHandler()
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    log_dir = ensure_directory(Path(state_dir) / "logs")
    file_handler = pylogging.FileHandler(log_dir / f"{profile_name}.log")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    return logger
