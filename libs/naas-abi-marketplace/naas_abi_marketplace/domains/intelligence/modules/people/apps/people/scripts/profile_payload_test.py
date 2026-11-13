"""Contact links: mailto: and tel: built here, anything else only as a web URL."""

from __future__ import annotations

import pytest
from naas_abi_marketplace.domains.intelligence.modules.people.apps.people.scripts.profile_payload import (
    _contact_href,
)


@pytest.mark.parametrize(
    ("field", "value", "href"),
    [
        ("email", "ada@example.com", "mailto:ada@example.com"),
        ("phone", "+33 1 23 45", "tel:+3312345"),
        (
            "linkedin_url",
            "https://www.linkedin.com/in/ada",
            "https://www.linkedin.com/in/ada",
        ),
        ("linkedin_url", "javascript:alert(document.domain)", ""),
        ("linkedin_url", "data:text/html,x", ""),
        ("website", "https://ex.example/ a", ""),
        ("website", "//example.com", ""),
    ],
)
def test_contact_links_keep_to_web_urls(field: str, value: str, href: str) -> None:
    assert _contact_href(field, value) == href
