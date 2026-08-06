"""wgrib2 Readerのコマンド組立て・エラー処理・一時ファイル削除のテスト
(仕様書11章 項目14)。実際の wgrib2.exe やGRIB2ファイルは使わず、
`subprocess.run` 相当の呼び出しをモックして検証する。
"""
import pytest

from dust_forecast.paths import TEMP_DIR
from dust_forecast.readers import wgrib2_netcdf as w2
from dust_forecast.readers.base import GribReaderError, GribToolNotFoundError


class _FakeCompletedProcess:
    def __init__(self, returncode: int, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def test_resolve_wgrib2_exe_from_configured_path(tmp_path):
    exe = tmp_path / "wgrib2.exe"
    exe.write_bytes(b"")
    resolved = w2.resolve_wgrib2_exe(configured_path=str(exe))
    assert resolved == exe


def test_resolve_wgrib2_exe_from_env_var(tmp_path, monkeypatch):
    exe = tmp_path / "wgrib2_env.exe"
    exe.write_bytes(b"")
    monkeypatch.setenv("DUST_FORECAST_WGRIB2", str(exe))
    resolved = w2.resolve_wgrib2_exe(configured_path=None)
    assert resolved == exe


def test_resolve_wgrib2_exe_not_found_raises(tmp_path, monkeypatch):
    monkeypatch.delenv("DUST_FORECAST_WGRIB2", raising=False)
    monkeypatch.setattr(w2.shutil, "which", lambda name: None)
    monkeypatch.setattr(w2, "_COMMON_INSTALL_DIRS", (tmp_path / "no_such_dir",))
    with pytest.raises(GribToolNotFoundError):
        w2.resolve_wgrib2_exe(configured_path=None)


def test_decode_bytes_utf8():
    assert w2._decode_bytes("こんにちは".encode("utf-8")) == "こんにちは"


def test_decode_bytes_cp932_fallback():
    text = "コマンド実行"
    data = text.encode("cp932")
    assert w2._decode_bytes(data) == text


def test_run_wgrib2_success(monkeypatch):
    calls = []

    def fake_invoke(cmd, cwd):
        calls.append((cmd, cwd))
        return _FakeCompletedProcess(0, stdout=b"1.1:0:d=2023031412:UGRD:...\n")

    monkeypatch.setattr(w2, "_invoke_subprocess", fake_invoke)
    result = w2._run_wgrib2(w2.Path("wgrib2.exe"), ["-s"], cwd=w2.Path("."), label="test")
    assert result.returncode == 0
    assert "UGRD" in result.stdout
    assert calls[0][0] == ["wgrib2.exe", "-s"]


def test_run_wgrib2_tool_not_found_raises(monkeypatch):
    def fake_invoke(cmd, cwd):
        raise OSError("no such executable")

    monkeypatch.setattr(w2, "_invoke_subprocess", fake_invoke)
    with pytest.raises(GribToolNotFoundError):
        w2._run_wgrib2(w2.Path("missing.exe"), ["-s"], cwd=w2.Path("."), label="test")


def test_local_copy_retry_on_path_issue(tmp_path, monkeypatch):
    """日本語/UNCパス等が原因の失敗時、ローカルコピーへ再試行すること。"""
    src = tmp_path / "input.bin"
    src.write_bytes(b"dummy grib data")

    calls = []

    def fake_invoke(cmd, cwd):
        calls.append((cmd, cwd))
        if len(calls) == 1:
            return _FakeCompletedProcess(8, stderr=b"*** FATAL ERROR: missing input file ***")
        return _FakeCompletedProcess(0, stdout=b"ok")

    monkeypatch.setattr(w2, "_invoke_subprocess", fake_invoke)
    reader = w2.Wgrib2NetcdfReader(wgrib2_exe=str(tmp_path / "wgrib2.exe"))
    (tmp_path / "wgrib2.exe").write_bytes(b"")

    result = reader._run_with_local_copy_retry(tmp_path / "wgrib2.exe", src, ["-s"], label="test")
    assert result.returncode == 0
    assert len(calls) == 2
    # 2回目の呼び出しはローカル一時フォルダ(outputs/_tmp配下)内のコピーに対して行われている
    second_cwd = calls[1][1]
    assert str(TEMP_DIR) in str(second_cwd)


def test_local_copy_retry_cleans_up_temp_dir(tmp_path, monkeypatch):
    """一時ファイルが例外時にも確実に削除されること。"""
    src = tmp_path / "input.bin"
    src.write_bytes(b"dummy")

    def fake_invoke(cmd, cwd):
        return _FakeCompletedProcess(8, stderr=b"cannot open file")

    monkeypatch.setattr(w2, "_invoke_subprocess", fake_invoke)
    reader = w2.Wgrib2NetcdfReader(wgrib2_exe=str(tmp_path / "wgrib2.exe"))
    (tmp_path / "wgrib2.exe").write_bytes(b"")

    before = set(TEMP_DIR.iterdir()) if TEMP_DIR.exists() else set()
    with pytest.raises(GribReaderError):
        reader._run_with_local_copy_retry(tmp_path / "wgrib2.exe", src, ["-s"], label="test")
    after = set(TEMP_DIR.iterdir()) if TEMP_DIR.exists() else set()
    assert after == before  # 一時ディレクトリが残っていないこと


def test_non_path_error_does_not_retry(tmp_path, monkeypatch):
    """パス問題以外のエラーではローカルコピー再試行を行わないこと。"""
    src = tmp_path / "input.bin"
    src.write_bytes(b"dummy")

    calls = []

    def fake_invoke(cmd, cwd):
        calls.append(1)
        return _FakeCompletedProcess(1, stderr=b"unsupported grib edition")

    monkeypatch.setattr(w2, "_invoke_subprocess", fake_invoke)
    reader = w2.Wgrib2NetcdfReader(wgrib2_exe=str(tmp_path / "wgrib2.exe"))
    (tmp_path / "wgrib2.exe").write_bytes(b"")

    with pytest.raises(GribReaderError):
        reader._run_with_local_copy_retry(tmp_path / "wgrib2.exe", src, ["-s"], label="test")
    assert len(calls) == 1


def test_parse_inventory_line_extracts_grib_identifiers():
    line = "1.21:0:d=2023031412:APCP:surface:0-1 hour acc fcst::var0_2_1_34_1_8:npts=72541:(241 x 301)"
    row = w2._parse_inventory_line(line, fallback_index=1)
    assert row["name"] == "APCP"
    assert row["discipline"] == 0
    assert row["parameterCategory"] == 1
    assert row["parameterNumber"] == 8
    assert row["Ni"] == 241
    assert row["Nj"] == 301


def test_parse_step_hours_analysis_and_range():
    assert w2._parse_step_hours("anl") == (0, 0)
    assert w2._parse_step_hours("1 hour fcst") == (1, 1)
    assert w2._parse_step_hours("0-3 hour acc fcst") == (0, 3)
