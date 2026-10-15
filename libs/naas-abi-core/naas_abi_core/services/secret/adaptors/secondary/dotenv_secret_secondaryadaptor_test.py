from dotenv import dotenv_values
from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
    DotenvSecretSecondaryAdaptor,
)


def test_mutations_keep_reads_listing_and_disk_consistent(tmp_path, monkeypatch):
    key = "ABI_DOTENV_MUTATION_TEST"
    monkeypatch.delenv(key, raising=False)
    path = tmp_path / ".env"
    path.write_text(f"{key}=initial\n")
    adapter = DotenvSecretSecondaryAdaptor(str(path))
    adapter.set(key, "updated")
    assert adapter.get(key) == "updated"
    assert adapter.list()[key] == "updated"
    assert dotenv_values(path)[key] == "updated"
    adapter.remove(key)
    assert adapter.get(key) is None
    assert key not in adapter.list()
    assert key not in dotenv_values(path)
    assert DotenvSecretSecondaryAdaptor(str(path)).get(key) is None
    adapter.remove(key)


def test_rewrites_give_the_file_back_to_its_owner(tmp_path, monkeypatch):
    # A root container rewriting a bind-mounted .env: the new file is root's.
    import os

    path = tmp_path / ".env"
    path.write_text("A=1\n")
    adapter = DotenvSecretSecondaryAdaptor(str(path))
    real_stat = os.stat
    owner = {"uid": real_stat(path).st_uid + 1, "gid": real_stat(path).st_gid + 1}
    calls = []

    def stat(p, *args, **kwargs):
        st = real_stat(p, *args, **kwargs)
        if str(p) != str(path) or not owner:
            return st
        fields = list(st)
        fields[4], fields[5] = owner.pop("uid"), owner.pop("gid")
        return os.stat_result(fields)

    monkeypatch.setattr(os, "stat", stat)
    monkeypatch.setattr(os, "chown", lambda p, uid, gid: calls.append((p, uid, gid)))
    adapter.set("B", "2")
    assert calls == [
        (str(path), real_stat(path).st_uid + 1, real_stat(path).st_gid + 1)
    ]
