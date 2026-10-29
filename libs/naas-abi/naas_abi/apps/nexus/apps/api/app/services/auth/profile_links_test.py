import pytest

from naas_abi.apps.nexus.apps.api.app.services.auth.profile_links import (
    normalize_github_handle,
    normalize_linkedin_profile_url,
)


@pytest.mark.parametrize(
    "value",
    [
        "https://www.linkedin.com/in/jeremyravenel",
        "https://www.linkedin.com/in/JeremyRavenel/",
        "linkedin.com/in/jeremyravenel?originalSubdomain=fr",
        "http://fr.linkedin.com/in/jeremyravenel/details/experience/",
        "  www.linkedin.com/in/jeremyravenel  ",
    ],
)
def test_a_linkedin_profile_url_is_stored_in_one_shape(value) -> None:
    assert (
        normalize_linkedin_profile_url(value)
        == "https://www.linkedin.com/in/jeremyravenel"
    )


def test_an_accented_vanity_is_kept() -> None:
    assert (
        normalize_linkedin_profile_url(
            "https://www.linkedin.com/in/julien-huv%C3%A9-6955665a"
        )
        == "https://www.linkedin.com/in/julien-huvé-6955665a"
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "jeremyravenel",
        "https://www.linkedin.com/company/forvis-mazars",
        "https://www.linkedin.com/in/",
        "https://evil.com/in/jeremyravenel",
        "https://linkedin.com.evil.com/in/x",
        "ftp://www.linkedin.com/in/x",
    ],
)
def test_anything_but_a_linkedin_profile_is_refused(value) -> None:
    assert normalize_linkedin_profile_url(value) is None


@pytest.mark.parametrize(
    "value",
    ["octocat", "@octocat", "https://github.com/octocat", "github.com/octocat/"],
)
def test_a_github_handle_is_stored_bare(value) -> None:
    assert normalize_github_handle(value) == "octocat"


@pytest.mark.parametrize(
    "value",
    ["", "-octocat", "octo cat", "https://github.com/octocat/repo", "a" * 40, "octo--cat"],
)
def test_anything_but_a_github_username_is_refused(value) -> None:
    assert normalize_github_handle(value) is None
