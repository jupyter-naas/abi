from typing import Any

import pytest
from pydantic import ValidationError

from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    ConfigRequirement,
    InvalidToolReferenceError,
    ToolContext,
    ToolDefinition,
    ToolId,
    ToolRef,
    ToolRequirements,
)


def _definition(**overrides) -> ToolDefinition:
    values: dict[str, Any] = {
        "namespace": "acme.github",
        "name": "create_issue",
        "description": "Create an issue in a repository.",
        "input_schema": {
            "type": "object",
            "properties": {"title": {"type": "string", "description": "Title"}},
        },
        "module": "acme.github",
    }
    values.update(overrides)
    return ToolDefinition(**values)


class TestToolId:
    def test_formats_as_namespace_name_version(self):
        assert str(
            ToolId(namespace="acme.github", name="create_issue", version="2")
        ) == ("acme.github/create_issue@2")

    def test_parse_round_trips(self):
        tool_id = ToolId.parse("acme.github/create_issue@1.2.0")
        assert tool_id == ToolId(
            namespace="acme.github", name="create_issue", version="1.2.0"
        )

    def test_parse_requires_a_version(self):
        with pytest.raises(InvalidToolReferenceError):
            ToolId.parse("acme.github/create_issue")

    @pytest.mark.parametrize(
        "raw",
        [
            "",
            "create_issue",
            "acme github/create_issue@1",
            "acme.github/create issue@1",
            "acme.github/create_issue@one",
            "acme.github/create_issue@1@2",
            "/create_issue@1",
        ],
    )
    def test_parse_rejects_malformed_ids(self, raw):
        with pytest.raises(InvalidToolReferenceError):
            ToolId.parse(raw)

    def test_version_sort_key_is_numeric(self):
        assert ToolId.parse("a/b@10").version_key > ToolId.parse("a/b@9").version_key
        assert (
            ToolId.parse("a/b@1.10").version_key > ToolId.parse("a/b@1.9").version_key
        )


class TestToolRef:
    def test_ref_without_version_matches_every_version(self):
        ref = ToolRef.parse("acme.github/create_issue")
        assert ref.version is None
        assert ref.matches(ToolId.parse("acme.github/create_issue@1"))
        assert ref.matches(ToolId.parse("acme.github/create_issue@2"))
        assert not ref.matches(ToolId.parse("acme.github/close_issue@1"))

    def test_ref_with_version_matches_exactly(self):
        ref = ToolRef.parse("acme.github/create_issue@2")
        assert not ref.matches(ToolId.parse("acme.github/create_issue@1"))
        assert ref.matches(ToolId.parse("acme.github/create_issue@2"))

    def test_str_keeps_the_caller_form(self):
        assert str(ToolRef.parse("acme.github/create_issue")) == (
            "acme.github/create_issue"
        )


class TestToolDefinition:
    def test_id_is_derived_from_namespace_name_and_version(self):
        assert str(_definition(version="3").id) == "acme.github/create_issue@3"

    def test_default_version_is_one(self):
        assert _definition().version == "1"

    def test_rejects_unknown_fields(self):
        with pytest.raises(ValidationError):
            _definition(unexpected=True)

    def test_rejects_invalid_model_facing_name(self):
        with pytest.raises(ValidationError):
            _definition(name="create issue")

    def test_is_serialisable_without_runtime_objects(self):
        definition = _definition(
            requirements=ToolRequirements(
                config=(ConfigRequirement(key="access_token", secret=True),)
            ),
            required_scopes=("github",),
            tags=("vcs",),
        )
        payload = definition.model_dump(mode="json")
        assert ToolDefinition.model_validate(payload) == definition

    def test_embedding_text_describes_the_capability(self):
        text = _definition(tags=("vcs",)).embedding_text()
        assert "create issue" in text
        assert "Create an issue in a repository." in text
        assert "title: Title" in text
        assert "vcs" in text

    def test_embedding_text_keeps_only_the_module_product_name(self):
        text = _definition(
            module="naas_abi_marketplace.applications.github"
        ).embedding_text()
        assert "module: github" in text
        assert "marketplace" not in text

    def test_embedding_text_changes_when_the_description_changes(self):
        assert (
            _definition().embedding_text()
            != _definition(description="Open a ticket").embedding_text()
        )

    def test_required_config_keys_only_lists_required_entries(self):
        definition = _definition(
            requirements=ToolRequirements(
                config=(
                    ConfigRequirement(key="access_token", secret=True),
                    ConfigRequirement(key="base_url", required=False),
                )
            )
        )
        assert definition.required_config_keys() == ("access_token",)


class TestToolContext:
    def test_anonymous_context_has_no_scopes(self):
        assert ToolContext().scopes == frozenset()

    def test_scopes_are_normalised_to_a_frozenset(self):
        assert ToolContext(scopes=["a", "b", "a"]).scopes == frozenset({"a", "b"})
