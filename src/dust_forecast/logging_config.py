"""共通ロギング設定。

標準出力への簡潔なログと、長大な出力(外部コマンドのstdout/stderr等)を
outputs/logs/ 以下のファイルへ退避する仕組みを提供する。
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path

from dust_forecast.paths import ensure_outputs_dir

_CONFIGURED = False


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """アプリケーション共通のロガーを初期化する(冪等)。"""
    global _CONFIGURED
    root = logging.getLogger("dust_forecast")
    if _CONFIGURED:
        return root

    root.setLevel(level)

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root.addHandler(stream_handler)

    log_dir = ensure_outputs_dir("logs")
    file_handler = logging.FileHandler(log_dir / "dust_forecast.log", encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    )
    root.addHandler(file_handler)

    _CONFIGURED = True
    return root


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(f"dust_forecast.{name}")


def write_long_output(label: str, text: str) -> Path:
    """長大な標準出力等をファイルへ退避し、そのパスを返す。"""
    log_dir = ensure_outputs_dir("logs")
    out_path = log_dir / f"{label}.txt"
    out_path.write_text(text, encoding="utf-8")
    return out_path
