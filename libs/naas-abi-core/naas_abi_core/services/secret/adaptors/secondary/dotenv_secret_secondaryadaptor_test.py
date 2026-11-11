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

    _forget_env(monkeypatch, "B")
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


def test_a_read_only_file_is_read_and_never_written(tmp_path, monkeypatch):
    key = "ABI_DOTENV_READ_ONLY_TEST"
    monkeypatch.delenv(key, raising=False)
    path = tmp_path / "coding.env"
    path.write_text(f"{key}=minted\n")
    path.chmod(0o444)  # as on a volume mounted :ro
    adapter = DotenvSecretSecondaryAdaptor(str(path), read_only=True)

    adapter.set(key, "updated")
    adapter.set("ABI_DOTENV_READ_ONLY_OTHER", "value")
    adapter.remove(key)

    assert adapter.get(key) == "minted"
    assert adapter.list() == {key: "minted"}
    assert path.read_text() == f"{key}=minted\n"


def test_a_read_only_file_beside_a_writable_one_lets_the_service_write(
    tmp_path, monkeypatch
):
    from naas_abi_core.services.secret.Secret import Secret

    key = "ABI_DOTENV_FANOUT_TEST"
    monkeypatch.delenv(key, raising=False)
    writable, minted = tmp_path / ".env", tmp_path / "coding.env"
    writable.touch()
    minted.write_text("CODER_ADMIN_TOKEN=minted\n")
    minted.chmod(0o444)
    secret = Secret(
        [
            DotenvSecretSecondaryAdaptor(str(writable)),
            DotenvSecretSecondaryAdaptor(str(minted), read_only=True),
        ]
    )

    secret.set(key, "value")
    assert dotenv_values(writable)[key] == "value"
    secret.remove(key)
    assert key not in dotenv_values(writable)
    assert secret.get("CODER_ADMIN_TOKEN") == "minted"


def test_environment_first_lets_the_environment_win_over_the_file(
    tmp_path, monkeypatch
):
    key, only_in_file = "ABI_DOTENV_ENV_FIRST_TEST", "ABI_DOTENV_ENV_FIRST_FILE"
    path = tmp_path / ".env"
    path.write_text(f"{key}=saved\n{only_in_file}=saved\n")
    monkeypatch.setenv(key, "deployed")
    monkeypatch.delenv(only_in_file, raising=False)

    assert DotenvSecretSecondaryAdaptor(str(path)).get(key) == "saved"
    adapter = DotenvSecretSecondaryAdaptor(str(path), environment_first=True)
    assert adapter.get(key) == "deployed"
    assert adapter.get(only_in_file) == "saved"
    # The listing (what the admin console shows) agrees with get().
    assert adapter.list() == {key: "deployed", only_in_file: "saved"}
    # A value saved in this process is seen at once.
    adapter.set(key, "changed")
    assert adapter.get(key) == "changed"
    assert dotenv_values(path)[key] == "changed"


PEM = "-----BEGIN PRIVATE KEY-----\nMIGHAgEAMBMGByqGSM49\nAgEGCCqGSM49AwEHBG0w\n-----END PRIVATE KEY-----\n"


def _forget_env(monkeypatch, *keys):
    """Have monkeypatch restore ``keys`` in os.environ, which ``set`` writes:
    a delenv of an unset variable records nothing to undo."""
    for key in keys:
        monkeypatch.setenv(key, "")
        monkeypatch.delenv(key)


def test_keys_compose_cannot_read_go_to_the_sidecar(tmp_path, monkeypatch):
    # IAM and the IdP keep their keys under iam/... and idp/...: docker compose
    # refuses a .env with such a name ("unexpected character "/"").
    import os

    _forget_env(monkeypatch, "ABI_DOTENV_SIDECAR_TEST")
    path = tmp_path / ".env"
    path.write_text("A=1\n")
    adapter = DotenvSecretSecondaryAdaptor(str(path))

    adapter.set("iam/signing-keys/k1", PEM)
    adapter.set("idp/code-key", "abc")
    adapter.set("ABI_DOTENV_SIDECAR_TEST", "plain")

    assert dotenv_values(path) == {"A": "1", "ABI_DOTENV_SIDECAR_TEST": "plain"}
    sidecar = tmp_path / ".env.sidecar"
    assert dotenv_values(sidecar) == {"iam/signing-keys/k1": PEM, "idp/code-key": "abc"}
    assert sidecar.stat().st_mode & 0o777 == 0o600
    # Not environment variables: child processes do not inherit them.
    assert "iam/signing-keys/k1" not in os.environ
    assert adapter.get("iam/signing-keys/k1") == PEM
    assert adapter.list()["idp/code-key"] == "abc"

    reopened = DotenvSecretSecondaryAdaptor(str(path))
    assert reopened.get("iam/signing-keys/k1") == PEM
    assert reopened.get("A") == "1"

    reopened.remove("idp/code-key")
    assert reopened.get("idp/code-key") is None
    assert "idp/code-key" not in dotenv_values(sidecar)
    assert DotenvSecretSecondaryAdaptor(str(path)).get("idp/code-key") is None


def test_names_compose_reads_stay_in_the_file(tmp_path, monkeypatch):
    # Every name compose v5.6 reads back from an env_file, any character first.
    kept = ("A_B", "a.b", "a-b", "_x", "1A", "2FA_SECRET")
    _forget_env(monkeypatch, *kept)
    path = tmp_path / ".env"
    path.touch()
    adapter = DotenvSecretSecondaryAdaptor(str(path))
    for key in kept + ("iam/x", "x:y"):
        adapter.set(key, "v")
    assert set(dotenv_values(path)) == set(kept)
    assert set(dotenv_values(tmp_path / ".env.sidecar")) == {"iam/x", "x:y"}


def _three_seven_env(path):
    """A .env as 3.7.x left it: the engine's keys written into it."""
    from dotenv import set_key

    path.write_text("A=1\n")
    set_key(str(path), "iam/signing-keys/k1", PEM)
    set_key(str(path), "B", "it's $HOME")


def test_move_keys_to_sidecar_repairs_a_file_an_earlier_engine_wrote(tmp_path):
    from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
        move_keys_to_sidecar,
    )

    path, sidecar = tmp_path / ".env", tmp_path / ".env.sidecar"
    _three_seven_env(path)
    path.chmod(0o640)
    sidecar.write_text("idp/code-key='abc'\n")

    assert move_keys_to_sidecar(str(path)) == ["iam/signing-keys/k1"]

    assert dotenv_values(path) == {"A": "1", "B": "it's $HOME"}
    assert "/" not in path.read_text()
    assert path.stat().st_mode & 0o777 == 0o640
    assert dotenv_values(sidecar, interpolate=False) == {
        "idp/code-key": "abc",
        "iam/signing-keys/k1": PEM,
    }
    adapter = DotenvSecretSecondaryAdaptor(str(path))
    assert adapter.get("iam/signing-keys/k1") == PEM
    # Nothing left to move.
    assert move_keys_to_sidecar(str(path)) == []


def test_a_new_sidecar_is_readable_by_its_owner_only(tmp_path):
    from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
        move_keys_to_sidecar,
    )

    path = tmp_path / ".env"
    _three_seven_env(path)
    move_keys_to_sidecar(str(path))
    assert (tmp_path / ".env.sidecar").stat().st_mode & 0o777 == 0o600


def test_opening_the_adapter_never_writes(tmp_path):
    path = tmp_path / ".env"
    _three_seven_env(path)
    before = path.read_text()

    adapter = DotenvSecretSecondaryAdaptor(str(path))

    assert path.read_text() == before
    assert not (tmp_path / ".env.sidecar").exists()
    # The key is still read where an earlier engine wrote it.
    assert adapter.get("iam/signing-keys/k1") == PEM


def test_the_configured_adapter_repairs_a_writable_file(tmp_path):
    from naas_abi_core.engine.engine_configuration.EngineConfiguration_SecretService import (
        SecretAdapterConfiguration,
    )

    path = tmp_path / ".env"
    _three_seven_env(path)
    adapter = SecretAdapterConfiguration(
        adapter="dotenv", config={"path": str(path)}
    ).load()

    assert "/" not in path.read_text()
    assert adapter.get("iam/signing-keys/k1") == PEM


def test_a_read_only_file_is_never_repaired_and_its_sidecar_is_read(tmp_path):
    # As on a volume mounted :ro, in a directory this process cannot write.
    from naas_abi_core.engine.engine_configuration.EngineConfiguration_SecretService import (
        SecretAdapterConfiguration,
    )

    directory = tmp_path / "ro"
    directory.mkdir()
    path = directory / "coding.env"
    path.write_text("A=1\niam/old=x\n")
    (directory / "coding.env.sidecar").write_text("idp/code-key=abc\n")
    path.chmod(0o444)
    directory.chmod(0o555)
    try:
        adapter = SecretAdapterConfiguration(
            adapter="dotenv", config={"path": str(path), "read_only": True}
        ).load()
        assert path.read_text() == "A=1\niam/old=x\n"
        assert adapter.get("idp/code-key") == "abc"
        assert adapter.get("iam/old") == "x"
    finally:
        directory.chmod(0o755)


def test_loading_the_engine_config_reads_the_bootstrap_dotenv_only(tmp_path):
    # The bootstrap adapter resolves ENV and {{ secret.X }} before the
    # configured adapters exist: it must not rewrite the file.
    from naas_abi_core.engine.engine_configuration.EngineConfiguration import (
        EngineConfiguration,
    )

    path = tmp_path / ".env"
    _three_seven_env(path)
    before = path.read_text()
    config = (
        "services:\n  secret:\n    secret_adapters:\n"
        f"      - adapter: dotenv\n        config:\n          path: {path}\n"
        "          read_only: true\n"
    )

    adapter = EngineConfiguration._load_bootstrap_dotenv_adapter_from_yaml_content(
        config
    )

    assert adapter is not None and adapter.get("A") == "1"
    assert path.read_text() == before
    assert not (tmp_path / ".env.sidecar").exists()


def test_the_repair_gives_both_files_the_owner_of_the_env(tmp_path, monkeypatch):
    # A root container repairing a bind-mounted .env the host user owns: both
    # files must end up the user's, or `abi deploy local` stops on them.
    import os

    from naas_abi_core.services.secret.adaptors.secondary.dotenv_secret_secondaryadaptor import (
        move_keys_to_sidecar,
    )

    path = tmp_path / ".env"
    _three_seven_env(path)
    real_stat = os.stat
    user = (real_stat(path).st_uid + 1, real_stat(path).st_gid + 1)
    # What the files look like: .env stays the user's until it is replaced.
    owners = {str(path): user}

    def stat(p, *args, **kwargs):
        st = real_stat(p, *args, **kwargs)
        if str(p) not in owners:
            return st
        fields = list(st)
        fields[4], fields[5] = owners[str(p)]
        return os.stat_result(fields)

    real_replace = os.replace

    def replace(source, destination):
        # The renamed file brings its own owner: this process's, unless
        # chowned before the rename.
        real_replace(source, destination)
        st = real_stat(destination)
        owners[str(destination)] = owners.pop(str(source), (st.st_uid, st.st_gid))

    def chown(p, uid, gid):
        owners[str(p)] = (uid, gid)

    monkeypatch.setattr(os, "stat", stat)
    monkeypatch.setattr(os, "chown", chown)
    monkeypatch.setattr(os, "replace", replace)

    move_keys_to_sidecar(str(path))

    assert owners[str(path)] == user
    assert owners[str(tmp_path / ".env.sidecar")] == user
