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


def builtin(**overrides):
    return provider(
        **{
            "name": "builtin",
            "issuer": "http://localhost:9879/idp",
            "client_secret": None,
            "provisioning": "builtin",
            **overrides,
        }
    )


def test_the_built_in_idp_is_served_at_idp_and_there_is_one():
    config = IdentityConfiguration.model_validate({"providers": [builtin()]})
    assert config.providers[0].provisioning == "builtin"
    for bad in (
        builtin(issuer="https://abi.example/auth"),
        builtin(issuer="https://abi.example"),
        builtin(issuer="https://abi.example/idp/"),
    ):
        with pytest.raises(ValidationError, match="served at /idp"):
            IdentityConfiguration.model_validate({"providers": [bad]})
    with pytest.raises(ValidationError, match="only one provider is the built-in"):
        IdentityConfiguration.model_validate(
            {
                "providers": [
                    builtin(),
                    builtin(name="second", issuer="http://localhost:9880/idp"),
                ]
            }
        )


def test_a_built_in_provider_is_read_over_nats_not_http(monkeypatch):
    from naas_abi_core.services.iam.IAMService import IAMService
    from naas_abi_core.services.identity.adapters.secondary.OIDCHttpBuiltinIdP import (
        OIDCHttpBuiltinIdP,
    )

    config = IdentityConfiguration.model_validate(
        {
            "providers": [
                builtin(),
                provider(name="acme", issuer="https://acme.okta.com"),
            ]
        }
    )
    monkeypatch.setattr(
        "naas_abi_core.engine.engine_configuration.EngineConfiguration_Identity.warm_up_in_background",
        lambda service: None,
    )
    service = config.load(IAMService.__new__(IAMService))  # type: ignore[arg-type]
    assert isinstance(service._http, OIDCHttpBuiltinIdP)
    assert service._http._issuers == ("http://localhost:9879/idp",)
    assert service.attach_builtin_idp(None) is True
    plain = IdentityConfiguration.model_validate({"providers": [provider()]})
    assert plain.load(IAMService.__new__(IAMService)).attach_builtin_idp(None) is False  # type: ignore[arg-type]
