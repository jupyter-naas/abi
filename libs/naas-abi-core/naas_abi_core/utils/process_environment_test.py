from naas_abi_core.utils.process_environment import allowed_environment


def test_the_process_environment_keeps_proxies_without_their_credentials(
    monkeypatch,
) -> None:
    monkeypatch.setenv("HTTPS_PROXY", "http://user:pass@proxy.internal:3128")
    monkeypatch.setenv("http_proxy", "user@proxy.internal:3128/path")
    monkeypatch.setenv("NO_PROXY", "localhost,.internal")
    monkeypatch.setenv("SSL_CERT_FILE", "/etc/ssl/private-ca.pem")
    monkeypatch.setenv("NODE_EXTRA_CA_CERTS", "/etc/ssl/private-ca.pem")
    monkeypatch.setenv("ENGINE_ONLY_SECRET", "kept-by-the-engine")

    env = allowed_environment(home="/work/home")

    assert env["HTTPS_PROXY"] == "http://proxy.internal:3128"
    assert env["http_proxy"] == "proxy.internal:3128/path"
    assert env["NO_PROXY"] == "localhost,.internal"
    assert env["SSL_CERT_FILE"] == "/etc/ssl/private-ca.pem"
    assert env["NODE_EXTRA_CA_CERTS"] == "/etc/ssl/private-ca.pem"
    assert "ENGINE_ONLY_SECRET" not in env
    assert "user" not in "".join(env.values())
