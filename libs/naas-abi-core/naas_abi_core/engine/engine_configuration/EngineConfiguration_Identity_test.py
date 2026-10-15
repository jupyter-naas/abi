import pytest
from naas_abi_core.engine.engine_configuration.EngineConfiguration_Identity import (
    IdentityConfiguration,
)
from pydantic import ValidationError


def provider(**overrides):
    return {
        "name": "acme",
        "issuer": "https://acme.okta.com",
        "client_id": "abi",
        "client_secret": "s3cret",
        **overrides,
    }


def test_a_provider_block_validates():
    config = IdentityConfiguration.model_validate(
        {"default_provider": "acme", "providers": [provider(groups_claim="groups")]}
    )
    built = config.providers[0].to_provider()
    assert (built.name, built.issuer, built.groups_claim) == (
        "acme",
        "https://acme.okta.com",
        "groups",
    )
    assert built.scopes == ("openid", "email", "profile")
    assert "s3cret" not in repr(config)


def test_no_block_trusts_no_provider():
    assert IdentityConfiguration().providers == []


@pytest.mark.parametrize(
    "bad",
    [
        provider(name="Acme"),
        provider(name="a" * 33),
        provider(issuer="http://acme.okta.com"),
        provider(issuer="ftp://acme"),
        provider(issuer="https://acme.okta.com?x=1"),
        provider(scopes=["email"]),
        provider(client_id=""),
        provider(unknown="x"),
    ],
)
def test_a_bad_provider_is_refused(bad):
    with pytest.raises(ValidationError):
        IdentityConfiguration.model_validate({"providers": [bad]})


def test_http_is_allowed_on_localhost_only():
    config = IdentityConfiguration.model_validate(
        {"providers": [provider(issuer="http://localhost:8080")]}
    )
    assert config.providers[0].issuer == "http://localhost:8080"


def test_names_and_issuers_are_unique():
    with pytest.raises(ValidationError, match="duplicate names"):
        IdentityConfiguration.model_validate(
            {"providers": [provider(), provider(issuer="https://b.example")]}
        )
    with pytest.raises(ValidationError, match="issuers used twice"):
        IdentityConfiguration.model_validate(
            {"providers": [provider(), provider(name="other")]}
        )


def test_the_default_must_name_a_provider():
    with pytest.raises(ValidationError, match="names no provider"):
        IdentityConfiguration.model_validate(
            {"default_provider": "nope", "providers": [provider()]}
        )


def test_an_empty_secret_render_is_no_secret():
    config = IdentityConfiguration.model_validate(
        {"providers": [provider(client_secret="")]}
    )
    assert config.providers[0].client_secret is None
