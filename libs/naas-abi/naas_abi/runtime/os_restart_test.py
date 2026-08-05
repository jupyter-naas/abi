from __future__ import annotations

import json
from pathlib import Path

from naas_abi.runtime.os_restart import (
    find_dev_project_root,
    is_restart_pending,
    schedule_os_restart,
)


def test_find_dev_project_root(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    assert find_dev_project_root() is None

    dev_dir = tmp_path / ".abi/dev"
    dev_dir.mkdir(parents=True)
    (dev_dir / "instance.json").write_text("{}", encoding="utf-8")

    assert find_dev_project_root() == tmp_path.resolve()


def test_schedule_os_restart_writes_pending_and_spawns(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    dev_dir = tmp_path / ".abi/dev"
    dev_dir.mkdir(parents=True)
    (dev_dir / "instance.json").write_text(json.dumps({"project_root": str(tmp_path)}))

    spawned: dict = {}

    def fake_popen(cmd, **kwargs):
        spawned["cmd"] = cmd
        spawned["cwd"] = kwargs.get("cwd")
        class _Proc:
            pid = 123

        return _Proc()

    monkeypatch.setattr("naas_abi.runtime.os_restart.shutil.which", lambda _: "/usr/bin/abi")
    monkeypatch.setattr("naas_abi.runtime.os_restart.time.sleep", lambda _s: None)
    monkeypatch.setattr("naas_abi.runtime.os_restart.subprocess.Popen", fake_popen)

    result = schedule_os_restart(delay_seconds=0)

    assert result.scheduled is True
    assert result.mode == "dev"
    assert is_restart_pending(tmp_path)
    assert spawned["cmd"] == ["abi", "dev", "restart"]
    assert spawned["cwd"] == str(tmp_path)
