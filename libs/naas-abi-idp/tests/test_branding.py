import pytest

from naas_abi_idp.configuration import Branding
from naas_abi_idp.pages import _page


def head(branding: Branding) -> str:
    html = _page(branding, "Sign in", "<p>body</p>")
    return html.split("</head>", 1)[0]


def test_the_tab_icon_is_the_branding_favicon():
    branding = Branding.of({"favicon_url": "https://acme.test/favicon.ico"})
    assert '<link rel="icon" href="https://acme.test/favicon.ico">' in head(branding)


def test_a_favicon_on_this_origin_is_a_path():
    branding = Branding.of({"favicon_url": "/static/favicon.png"})
    assert '<link rel="icon" href="/static/favicon.png">' in head(branding)


def test_no_favicon_no_icon_link():
    assert 'rel="icon"' not in head(Branding())


def test_the_favicon_url_is_escaped():
    branding = Branding.of(
        {"favicon_url": 'https://acme.test/i.ico"><script>x</script>'}
    )
    rendered = head(branding)
    assert "<script>" not in rendered
    assert (
        'href="https://acme.test/i.ico&quot;&gt;&lt;script&gt;x&lt;/script&gt;"'
        in rendered
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://acme.test/favicon.ico",
        "data:image/png;base64,AAAA",
        "javascript:alert(1)",
        "ftp://acme.test/favicon.ico",
    ],
)
def test_a_favicon_is_https_or_a_path_only(url):
    with pytest.raises(ValueError, match="favicon_url"):
        Branding.of({"favicon_url": url})


def test_a_domain_branding_keeps_the_default_favicon_unless_it_sets_one():
    base = Branding.of({"favicon_url": "https://acme.test/favicon.ico"})
    assert (
        Branding.of({"app_name": "Other"}, base).favicon_url
        == "https://acme.test/favicon.ico"
    )
    assert Branding.of({"favicon_url": "/other.ico"}, base).favicon_url == "/other.ico"
