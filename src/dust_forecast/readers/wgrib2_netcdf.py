"""wgrib2 (外部exe) -> NetCDF -> xarray 経路のGRIB Reader。

`reference/wxbcgribx.py` を設計参考資料として、以下を改善して独自実装した
(詳細は docs/provenance.md を参照)。

- `wgrib2.exe` の絶対パスをハードコードせず、設定 > 環境変数 > PATH > 既定の
  探索順で解決する (`resolve_wgrib2_exe`)
- `shell=True` / `pushd` を使わず、`subprocess.run(cmd_list, cwd=...)` を使用
- 日本語パス・UNCパスでの失敗に備え、ローカル一時フォルダへ入力ファイルを
  コピーして1回だけ再試行する
- 標準出力/エラーはまずUTF-8で復号し、失敗時はcp932にフォールバックする
- `sys.exit()` を呼ばず、`GribReaderError` 系の例外を送出する
- 一時ファイルは例外時も `finally` / コンテキストマネージャで削除する
- コマンド・戻り値・stderrをログへ残す。長大な出力はファイルへ退避する
- `subprocess.run` 呼び出しは `_invoke_subprocess` に分離し、単体テストで
  モック可能にする
"""
from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd
import xarray as xr

from dust_forecast.logging_config import get_logger, write_long_output
from dust_forecast.paths import ensure_temp_dir
from dust_forecast.readers.base import (
    INVENTORY_COLUMNS,
    STANDARD_FIELDS,
    BaseGribReader,
    GribReaderError,
    GribToolNotFoundError,
)

logger = get_logger("readers.wgrib2_netcdf")

# wgrib2インベントリ("-s")における要素名:レベル記述の対応。
WGRIB2_MATCH_PATTERNS: dict[str, str] = {
    "u10": "UGRD:10 m above ground",
    "v10": "VGRD:10 m above ground",
    "t2m": "TMP:2 m above ground",
    "r2": "RH:2 m above ground",
    "tcc": "TCDC:surface",
    "apcp": "APCP:surface",
}

# `-netcdf` 出力時にwgrib2がCOARDS規約で付与する変数名。
WGRIB2_NETCDF_VAR_NAMES: dict[str, str] = {
    "u10": "UGRD_10maboveground",
    "v10": "VGRD_10maboveground",
    "t2m": "TMP_2maboveground",
    "r2": "RH_2maboveground",
    "tcc": "TCDC_surface",
    "apcp": "APCP_surface",
}

_COMMON_INSTALL_DIRS = (
    Path("C:/wgrib2"),
    Path.home() / "wgrib2",
    Path("C:/Program Files/wgrib2"),
)


def resolve_wgrib2_exe(configured_path: str | Path | None = None) -> Path:
    """wgrib2実行ファイルの場所を 設定 > 環境変数 > PATH > 既定探索 の順で解決する。"""
    tried: list[str] = []

    if configured_path:
        p = Path(configured_path)
        tried.append(str(p))
        if p.exists():
            return p

    env_path = os.environ.get("DUST_FORECAST_WGRIB2")
    if env_path:
        p = Path(env_path)
        tried.append(str(p))
        if p.exists():
            return p

    which = shutil.which("wgrib2") or shutil.which("wgrib2.exe")
    if which:
        return Path(which)
    tried.append("PATH上のwgrib2/wgrib2.exe")

    for base in _COMMON_INSTALL_DIRS:
        for name in ("wgrib2.exe", "wgrib2"):
            p = base / name
            tried.append(str(p))
            if p.exists():
                return p

    raise GribToolNotFoundError(
        "wgrib2実行ファイルが見つかりません。"
        "config の grib.wgrib2_exe、環境変数 DUST_FORECAST_WGRIB2、"
        "または PATH のいずれかで指定してください。"
        f" 試行した候補: {tried}"
    )


@contextlib.contextmanager
def _ascii_temp_dir(prefix: str):
    """outputs/_tmp配下(ASCIIパス)に一時ディレクトリを作り、終了時に削除する。

    既定の一時ディレクトリ(%TEMP%)は日本語ユーザー名を含む場合があり、
    netCDF4/HDF5ライブラリがそのパスを開けないことがあるため、
    プロジェクト配下のASCIIパスを使用する。
    """
    base = ensure_temp_dir()
    tmpdir = Path(tempfile.mkdtemp(prefix=prefix, dir=base))
    try:
        yield tmpdir
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def _decode_bytes(data: bytes) -> str:
    for encoding in ("utf-8", "cp932"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def _invoke_subprocess(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """subprocess.run の薄いラッパー。単体テストではここをモックする。"""
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True)


@dataclass
class Wgrib2RunResult:
    returncode: int
    stdout: str
    stderr: str


def _run_wgrib2(exe: Path, args: list[str], cwd: Path, label: str) -> Wgrib2RunResult:
    cmd = [str(exe)] + args
    logger.info("wgrib2実行: %s (cwd=%s)", " ".join(cmd), cwd)
    try:
        proc = _invoke_subprocess(cmd, cwd)
    except OSError as exc:
        raise GribToolNotFoundError(f"wgrib2の実行に失敗しました: {exc}") from exc

    stdout = _decode_bytes(proc.stdout)
    stderr = _decode_bytes(proc.stderr)

    if len(stdout) > 2000 or len(stderr) > 2000:
        out_path = write_long_output(f"wgrib2_{label}", f"[stdout]\n{stdout}\n[stderr]\n{stderr}")
        logger.info("wgrib2の出力が長いためファイルへ退避しました: %s", out_path)
    logger.info("wgrib2 returncode=%s", proc.returncode)
    if stderr.strip():
        logger.info("wgrib2 stderr(先頭200文字): %s", stderr[:200])

    return Wgrib2RunResult(returncode=proc.returncode, stdout=stdout, stderr=stderr)


def _looks_like_path_issue(result: Wgrib2RunResult) -> bool:
    text = (result.stdout + result.stderr).lower()
    markers = (
        "no such file", "cannot open", "could not open", "invalid argument",
        "missing input file", "fatal error",
    )
    return any(m in text for m in markers)


class Wgrib2NetcdfReader(BaseGribReader):
    backend_name = "wgrib2_netcdf"

    def __init__(self, wgrib2_exe: str | Path | None = None):
        self._configured_exe = wgrib2_exe

    def _exe(self) -> Path:
        return resolve_wgrib2_exe(self._configured_exe)

    def _run_with_local_copy_retry(
        self, exe: Path, input_path: Path, opt_args: list[str], label: str
    ) -> Wgrib2RunResult:
        result = _run_wgrib2(exe, [str(input_path)] + opt_args, cwd=input_path.parent, label=label)
        if result.returncode == 0:
            return result
        if not _looks_like_path_issue(result):
            raise GribReaderError(
                f"wgrib2実行に失敗しました (returncode={result.returncode}): {result.stderr[:500]}"
            )

        logger.warning(
            "日本語パス/UNCパスが原因の可能性があるため、ローカル一時フォルダへコピーして再試行します: %s",
            input_path,
        )
        with _ascii_temp_dir(prefix="dust_forecast_grib_") as tmpdir:
            local_input = Path(tmpdir) / "input.bin"
            try:
                shutil.copy2(input_path, local_input)
            except OSError as exc:
                raise GribReaderError(f"入力ファイルの一時コピーに失敗しました: {exc}") from exc

            retry_result = _run_wgrib2(exe, [str(local_input)] + opt_args, cwd=local_input.parent, label=f"{label}_retry")
            if retry_result.returncode != 0:
                raise GribReaderError(
                    "wgrib2実行に失敗しました(ローカルコピー再試行後も失敗): "
                    f"returncode={retry_result.returncode}: {retry_result.stderr[:500]}"
                )
            return retry_result

    def read(
        self,
        input_path: str | Path,
        fields: tuple[str, ...] = tuple(STANDARD_FIELDS.keys()),
    ) -> xr.Dataset:
        input_path = Path(input_path)
        if not input_path.exists():
            raise GribReaderError(f"GRIB2ファイルが見つかりません: {input_path}")
        input_path = input_path.resolve()

        exe = self._exe()
        unknown = [f for f in fields if f not in WGRIB2_MATCH_PATTERNS]
        if unknown:
            raise GribReaderError(f"wgrib2_netcdf Readerが未対応の要素です: {unknown}")

        match_expr = "|".join(WGRIB2_MATCH_PATTERNS[f] for f in fields)

        with _ascii_temp_dir(prefix="dust_forecast_wgrib2out_") as tmpdir:
            out_nc = Path(tmpdir) / "extract.nc"
            self._run_with_local_copy_retry(
                exe, input_path, ["-match", match_expr, "-netcdf", str(out_nc)], label="netcdf_export"
            )
            if not out_nc.exists():
                raise GribReaderError("wgrib2はNetCDF出力に成功しましたが、出力ファイルが見つかりません")
            with xr.open_dataset(out_nc) as ds:
                ds = ds.load()

        rename_map = {
            WGRIB2_NETCDF_VAR_NAMES[f]: f
            for f in fields
            if WGRIB2_NETCDF_VAR_NAMES[f] in ds.data_vars
        }
        missing = [f for f in fields if WGRIB2_NETCDF_VAR_NAMES[f] not in ds.data_vars]
        if missing:
            raise GribReaderError(f"要求した要素がNetCDF出力に含まれていません: {missing}")

        ds = ds.rename(rename_map)
        ds.attrs["source_file"] = input_path.name
        ds.attrs["reader_backend"] = self.backend_name
        return ds

    def inventory(self, input_path: str | Path) -> pd.DataFrame:
        input_path = Path(input_path)
        if not input_path.exists():
            raise GribReaderError(f"GRIB2ファイルが見つかりません: {input_path}")
        input_path = input_path.resolve()

        exe = self._exe()
        result = self._run_with_local_copy_retry(
            exe, input_path, ["-s", "-varX", "-npts", "-nxny"], label="inventory"
        )
        rows = [_parse_inventory_line(line, idx) for idx, line in enumerate(result.stdout.splitlines(), start=1) if line.strip()]
        return pd.DataFrame(rows, columns=INVENTORY_COLUMNS)


_LEVEL_NUMBER_RE = re.compile(r"(-?\d+(?:\.\d+)?)")
_STEP_HOUR_RE = re.compile(r"(\d+)")


def _parse_step_hours(step_desc: str) -> tuple[int, int]:
    """wgrib2のstepRange記述("anl","1 hour fcst","0-1 hour acc fcst"等)から
    (開始時間, 終了時間)[h]を抽出する。解析できない場合は (0, 0) を返す。
    """
    if step_desc.strip() == "anl":
        return 0, 0
    hours = [int(h) for h in _STEP_HOUR_RE.findall(step_desc)]
    if not hours:
        return 0, 0
    if len(hours) == 1:
        return hours[0], hours[0]
    return hours[0], hours[-1]


def _parse_inventory_line(line: str, fallback_index: int) -> dict:
    parts = line.split(":")
    row = {col: None for col in INVENTORY_COLUMNS}
    row["record_index"] = fallback_index
    try:
        row["record_index"] = int(parts[0].split(".")[-1])
    except (ValueError, IndexError):
        pass

    if len(parts) > 3:
        row["name"] = parts[3]
        row["shortName"] = parts[3]
    if len(parts) > 4:
        row["typeOfLevel"] = parts[4]
        level_match = _LEVEL_NUMBER_RE.search(parts[4])
        if level_match:
            row["level"] = float(level_match.group(1))

    if len(parts) > 5:
        row["stepRange"] = parts[5]
        init_match = re.search(r"d=(\d{10})", line)
        if init_match:
            init_dt = datetime.strptime(init_match.group(1), "%Y%m%d%H")
            start_h, end_h = _parse_step_hours(parts[5])
            row["forecastTime"] = end_h
            row["validDate"] = (init_dt + timedelta(hours=end_h)).strftime("%Y%m%d%H")

    for part in parts:
        if part.startswith("var"):
            nums = part[len("var"):].split("_")
            if len(nums) == 6:
                row["discipline"] = int(nums[0])
                row["parameterCategory"] = int(nums[4])
                row["parameterNumber"] = int(nums[5])
        if part.startswith("npts="):
            pass
        if part.strip().startswith("(") and "x" in part:
            grid_match = re.match(r"\((\d+)\s*x\s*(\d+)\)", part.strip())
            if grid_match:
                row["Ni"] = int(grid_match.group(1))
                row["Nj"] = int(grid_match.group(2))

    row["gridType"] = "regular_ll"
    return row
