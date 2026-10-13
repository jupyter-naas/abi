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
