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


def test_keys_compose_cannot_read_go_to_the_sidecar(tmp_path, monkeypatch):
    # IAM and the IdP keep their keys under iam/... and idp/...: docker compose
    # refuses a .env with such a name ("unexpected character "/"").
    monkeypatch.delenv("ABI_DOTENV_SIDECAR_TEST", raising=False)
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
    import os

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


def test_a_dotenv_an_earlier_engine_wrote_its_keys_into_is_repaired(tmp_path):
    path = tmp_path / ".env"
    path.write_text("A=1\n")
    # What 3.7.0 left behind: the keys written with set_key into .env itself.
    from dotenv import set_key

    set_key(str(path), "iam/signing-keys/k1", PEM)
    set_key(str(path), "B", "2")

    adapter = DotenvSecretSecondaryAdaptor(str(path))

    assert dotenv_values(path) == {"A": "1", "B": "2"}
    assert "/" not in path.read_text()
    assert dotenv_values(tmp_path / ".env.sidecar") == {"iam/signing-keys/k1": PEM}
    assert adapter.get("iam/signing-keys/k1") == PEM


def test_a_read_only_file_is_not_repaired_but_its_sidecar_is_read(tmp_path):
    path, sidecar = tmp_path / "coding.env", tmp_path / "coding.env.sidecar"
    path.write_text("A=1\niam/old=x\n")
    sidecar.write_text("idp/code-key=abc\n")

    adapter = DotenvSecretSecondaryAdaptor(str(path), read_only=True)

    assert path.read_text() == "A=1\niam/old=x\n"
    assert adapter.get("idp/code-key") == "abc"
    assert adapter.get("iam/old") == "x"


def test_the_sidecar_path_can_be_configured(tmp_path):
    path, sidecar = tmp_path / ".env", tmp_path / "secrets" / "engine.env"
    path.touch()
    adapter = DotenvSecretSecondaryAdaptor(str(path), sidecar_path=str(sidecar))
    adapter.set("iam/job-trigger-seal", "seal")
    assert dotenv_values(sidecar) == {"iam/job-trigger-seal": "seal"}
    assert path.read_text() == ""


def test_names_compose_reads_stay_in_the_file(tmp_path):
    path = tmp_path / ".env"
    path.touch()
    adapter = DotenvSecretSecondaryAdaptor(str(path))
    for key in ("A_B", "a.b", "a-b", "_x"):
        adapter.set(key, "v")
    for key in ("iam/x", "x:y", "1A"):
        adapter.set(key, "v")
    assert set(dotenv_values(path)) == {"A_B", "a.b", "a-b", "_x"}
    assert set(dotenv_values(tmp_path / ".env.sidecar")) == {"iam/x", "x:y", "1A"}
