import os
import stat

import pytest

from physiosync import config


def test_data_root_required():
    with pytest.raises(config.ConfigError, match="PHYSIOSYNC_DATA is not set"):
        config.load({})


def test_defaults_and_creates_root(tmp_path):
    root = tmp_path / "new" / "data"
    s = config.load({"PHYSIOSYNC_DATA": str(root)})
    assert root.is_dir()
    assert s.port == 8000
    assert s.reference_stream == "tobii.gaze"
    assert s.db_path == root.resolve() / "physiosync.db"


def test_overrides(tmp_path):
    s = config.load(
        {
            "PHYSIOSYNC_DATA": str(tmp_path),
            "PHYSIOSYNC_PORT": "9001",
            "PHYSIOSYNC_REFERENCE_STREAM": "scaner.telemetry",
        }
    )
    assert (s.port, s.reference_stream) == (9001, "scaner.telemetry")


@pytest.mark.parametrize("bad", ["abc", "0", "70000"])
def test_bad_port(tmp_path, bad):
    with pytest.raises(config.ConfigError, match="PHYSIOSYNC_PORT"):
        config.load({"PHYSIOSYNC_DATA": str(tmp_path), "PHYSIOSYNC_PORT": bad})


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="POSIX permissions only")
def test_unwritable_root(tmp_path):
    tmp_path.chmod(stat.S_IRUSR | stat.S_IXUSR)
    try:
        with pytest.raises(config.ConfigError, match="not a writable directory"):
            config.load({"PHYSIOSYNC_DATA": str(tmp_path)})
    finally:
        tmp_path.chmod(stat.S_IRWXU)
