"""Central filesystem location constants.

All other modules must import locations from here instead of
hardcoding or re-deriving path strings.
"""
from __future__ import annotations

from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
SRC_DIR = PACKAGE_DIR.parent
PROJECT_ROOT = SRC_DIR.parent

CONFIG_DIR = PROJECT_ROOT / "config"
DATA_DIR = PROJECT_ROOT / "data"
DATA_INPUT_DIR = DATA_DIR / "input"
DATA_BACKGROUND_DIR = DATA_DIR / "background"
OUTPUTS_DIR = PROJECT_ROOT / "outputs"
# netCDF4/HDF5はWindowsで非ASCII(日本語)を含むユーザープロファイル配下の
# 既定TEMPディレクトリを開けない場合がある。プロジェクト配下のASCIIパスを
# 一時ファイル置き場として使うことでこれを回避する。
TEMP_DIR = OUTPUTS_DIR / "_tmp"
DOCS_DIR = PROJECT_ROOT / "docs"
REFERENCE_DIR = PROJECT_ROOT / "reference"

DEFAULT_CONFIG_PATH = CONFIG_DIR / "sample.yaml"


def ensure_outputs_dir(subdir: str | None = None) -> Path:
    """Create (if needed) and return outputs/ or outputs/<subdir>."""
    target = OUTPUTS_DIR if subdir is None else OUTPUTS_DIR / subdir
    target.mkdir(parents=True, exist_ok=True)
    return target


def ensure_temp_dir() -> Path:
    """ASCIIパスの一時ディレクトリ(outputs/_tmp)を作成して返す。"""
    TEMP_DIR.mkdir(parents=True, exist_ok=True)
    return TEMP_DIR
