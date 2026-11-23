import pytest

from naas_abi_idp.configuration import Branding, IdPConfiguration
from naas_abi_idp.pages import code_page

ISSUER = "https://abi.test/idp"


def page(mailbox_url: str | None) -> str:
    return code_page(
        Branding(),
        action=f"{ISSUER}/login/code",
        again_action=f"{ISSUER}/login",
        csrf="token",
        email="sam@acme.test",
        mailbox_url=mailbox_url,
    )


def test_the_code_page_links_the_local_mailbox_when_set():
    html = page("http://localhost:8025")
    assert "Local environment: your code was sent to the local mailbox." in html
    assert (
        '<a href="http://localhost:8025" target="_blank" rel="noopener">'
        "Open the mailbox</a>" in html
    )


def test_without_a_mailbox_the_code_page_says_nothing_of_it():
    html = page(None)
    assert "mailbox" not in html.lower()
    assert 'class="local"' not in html


def test_the_mailbox_url_is_escaped():
    html = page('http://localhost:8025/"><script>x</script>')
    assert "<script>" not in html
    assert (
        'href="http://localhost:8025/&quot;&gt;&lt;script&gt;x&lt;/script&gt;"' in html
    )


@pytest.mark.parametrize(
    "url",
    ["http://localhost:8025", "https://mail.acme.test/", "http://127.0.0.1:8025/#/"],
)
def test_a_mailbox_is_an_http_or_https_url(url):
    assert IdPConfiguration(issuer=ISSUER, mailbox_url=url).mailbox_url == url


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "data:text/html,x",
        "ftp://mail.acme.test",
        "/mailbox",
        "http://",
    ],
)
def test_anything_else_is_refused(url):
    with pytest.raises(ValueError, match="mailbox_url"):
        IdPConfiguration(issuer=ISSUER, mailbox_url=url)


def test_a_blank_mailbox_is_none():
    assert IdPConfiguration(issuer=ISSUER, mailbox_url="  ").mailbox_url is None


def test_the_environment_sets_the_mailbox():
    env = {"ABI_IDP_ISSUER": ISSUER, "ABI_IDP_MAILBOX_URL": "http://localhost:8025"}
    assert IdPConfiguration.from_environment(env).mailbox_url == "http://localhost:8025"
    assert (
        IdPConfiguration.from_environment({"ABI_IDP_ISSUER": ISSUER}).mailbox_url
        is None
    )


def test_the_config_file_sets_the_mailbox(tmp_path):
    path = tmp_path / "idp.json"
    path.write_text('{"mailbox_url": "http://localhost:8025"}')
    env = {"ABI_IDP_ISSUER": ISSUER, "ABI_IDP_CONFIG": str(path)}
    assert IdPConfiguration.from_environment(env).mailbox_url == "http://localhost:8025"
