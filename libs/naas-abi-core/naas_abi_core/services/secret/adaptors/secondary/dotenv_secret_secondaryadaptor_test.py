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
