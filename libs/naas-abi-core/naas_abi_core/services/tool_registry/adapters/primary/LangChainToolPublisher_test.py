from __future__ import annotations

from collections.abc import Mapping
from typing import Annotated, Any

import pytest
from langchain_core.tools import BaseTool, InjectedToolCallId, StructuredTool, tool
from naas_abi_core.services.tool_registry.adapters.primary.LangChainToolPublisher import (
    FactoryToolBinding,
    StaticToolBinding,
    ToolPublisher,
    definition_from_tool,
    model_facing_name,
)
from naas_abi_core.services.tool_registry.ToolRegistryPort import (
    ConfigRequirement,
    ToolConfigurationError,
    ToolContext,
    ToolRegistryError,
)
from naas_abi_core.services.tool_registry.ToolRegistryService import (
    ToolRegistryService,
)
from naas_abi_core.utils.Expose import Expose
from pydantic import BaseModel, Field

MODULE = "acme.github"


@tool
def get_repository(repo_name: str) -> str:
    """Get a repository by its full name.

    Args:
        repo_name: Full repository name, 'owner/repo'.
    """
    return f"repo {repo_name}"


class _IssueSchema(BaseModel):
    repo_name: str = Field(..., description="Full repository name, 'owner/repo'")
    title: str = Field(..., description="Title of the issue")


class _RepoSchema(BaseModel):
    repo_name: str = Field(..., description="Full repository name, 'owner/repo'")


def _github_tools(configuration: Mapping[str, Any]) -> list[BaseTool]:
    """Stand-in for an integration's ``as_tools(configuration)``."""
    token = configuration["access_token"]
    return [
        StructuredTool(
            name="github_create_issue",
            description="Create an issue in a GitHub repository.",
            func=lambda repo_name, title: f"{token}:{repo_name}:{title}",
            args_schema=_IssueSchema,
        ),
        StructuredTool(
            name="github_list_issues",
            description="List the issues of a GitHub repository.",
            func=lambda repo_name: f"{token}:{repo_name}",
            args_schema=_RepoSchema,
        ),
    ]


class TestDefinitionFromTool:
    def test_captures_name_description_and_input_contract(self):
        definition = definition_from_tool(
            get_repository, namespace=MODULE, module=MODULE
        )
        assert str(definition.id) == f"{MODULE}/get_repository@1"
        assert definition.description.startswith("Get a repository")
        assert definition.input_schema["properties"]["repo_name"]["type"] == "string"

    def test_injected_arguments_are_not_part_of_the_contract(self):
        @tool
        def with_injection(
            query: str, tool_call_id: Annotated[str, InjectedToolCallId]
        ) -> str:
            """Look something up."""
            return query

        definition = definition_from_tool(
            with_injection, namespace=MODULE, module=MODULE
        )
        assert set(definition.input_schema["properties"]) == {"query"}

    def test_names_are_sanitised_like_the_agent_runtime_does(self):
        from naas_abi_core.services.agent.Agent import Agent

        for raw in ["github:create", "create issue", "a__b", "ok_name-1"]:
            assert model_facing_name(raw) == Agent.validate_name(raw)

    def test_workspace_gated_tools_declare_the_requirement(self):
        from naas_abi_core.services.agent.tools.workspace_tools import (
            REQUIRES_WORKSPACE_KEY,
        )

        @tool
        def write_file(path: str) -> str:
            """Write a file in the workspace."""
            return path

        write_file.metadata = {REQUIRES_WORKSPACE_KEY: True}
        definition = definition_from_tool(write_file, namespace=MODULE, module=MODULE)
        assert definition.requirements.requires_workspace is True


class TestStaticBinding:
    def test_returns_the_published_instance(self):
        binding = StaticToolBinding(get_repository)
        assert binding.create(ToolContext(), {}) is get_repository
        assert binding.default_config == {}


class TestFactoryBinding:
    def test_builds_the_named_tool_from_the_resolved_config(self):
        binding = FactoryToolBinding(
            _github_tools, "github_create_issue", default_config={"access_token": "t"}
        )
        built = binding.create(ToolContext(), {"access_token": "other"})
        assert isinstance(built, BaseTool)
        assert built.invoke({"repo_name": "o/r", "title": "x"}) == "other:o/r:x"

    def test_reuses_the_factory_output_for_identical_config(self):
        calls: list[Mapping[str, Any]] = []

        def factory(configuration):
            calls.append(configuration)
            return _github_tools(configuration)

        binding = FactoryToolBinding(
            factory, "github_create_issue", {"access_token": "t"}
        )
        first = binding.create(ToolContext(), {"access_token": "t"})
        second = binding.create(ToolContext(), {"access_token": "t"})
        binding.create(ToolContext(), {"access_token": "u"})
        assert first is second
        assert len(calls) == 2

    def test_a_factory_that_no_longer_produces_the_tool_is_explicit(self):
        binding = FactoryToolBinding(_github_tools, "github_delete_repo", {})
        with pytest.raises(ToolRegistryError, match="github_delete_repo"):
            binding.create(ToolContext(), {"access_token": "t"})


class TestToolPublisher:
    def test_publishes_existing_tool_instances(self):
        registry = ToolRegistryService()
        publisher = ToolPublisher(MODULE)
        publisher.add_tool(get_repository, tags=("vcs",))
        publisher.publish_to(registry)

        definition = registry.get_definition(f"{MODULE}/get_repository")
        assert definition.tags == ("vcs",)
        assert (
            registry.resolve(f"{MODULE}/get_repository", ToolContext())
            is get_repository
        )

    def test_publishes_every_tool_an_as_tools_factory_produces(self):
        registry = ToolRegistryService()
        publisher = ToolPublisher(MODULE)
        definitions = publisher.add_factory(
            _github_tools,
            default_config={"access_token": "module-token"},
            requirements=[ConfigRequirement(key="access_token", secret=True)],
        )
        publisher.publish_to(registry)

        assert [d.name for d in definitions] == [
            "github_create_issue",
            "github_list_issues",
        ]
        tool_ = registry.resolve(f"{MODULE}/github_create_issue", ToolContext())
        assert tool_.invoke({"repo_name": "o/r", "title": "x"}) == "module-token:o/r:x"

    def test_factory_definitions_can_be_derived_without_credentials(self):
        registry = ToolRegistryService()
        publisher = ToolPublisher(MODULE)
        publisher.add_factory(
            _github_tools,
            default_config={},
            requirements=[ConfigRequirement(key="access_token", secret=True)],
        )
        publisher.publish_to(registry)

        assert registry.availability(f"{MODULE}/github_list_issues").missing_config == (
            "access_token",
        )
        with pytest.raises(ToolConfigurationError):
            registry.resolve(f"{MODULE}/github_list_issues", ToolContext())
        tool_ = registry.resolve(
            f"{MODULE}/github_list_issues",
            ToolContext(),
            config={"access_token": "mine"},
        )
        assert tool_.invoke({"repo_name": "o/r"}) == "mine:o/r"

    def test_include_restricts_the_factory_tools(self):
        publisher = ToolPublisher(MODULE)
        definitions = publisher.add_factory(
            _github_tools,
            default_config={"access_token": "t"},
            include=["github_list_issues"],
        )
        assert [d.name for d in definitions] == ["github_list_issues"]

    def test_include_naming_an_unknown_tool_is_explicit(self):
        publisher = ToolPublisher(MODULE)
        with pytest.raises(ToolRegistryError, match="github_nope"):
            publisher.add_factory(
                _github_tools,
                default_config={"access_token": "t"},
                include=["github_nope"],
            )

    def test_publishes_tools_of_an_expose_instance(self):
        class Exposed(Expose):
            def as_tools(self):
                return [get_repository]

        publisher = ToolPublisher(MODULE)
        publisher.add_exposed(Exposed())
        assert [p.definition.name for p in publisher.tools] == ["get_repository"]

    def test_the_same_name_twice_is_rejected_before_publication(self):
        publisher = ToolPublisher(MODULE)
        publisher.add_tool(get_repository)
        with pytest.raises(ToolRegistryError, match="get_repository"):
            publisher.add_tool(get_repository)

    def test_namespace_defaults_to_the_module(self):
        publisher = ToolPublisher(MODULE)
        (definition,) = [publisher.add_tool(get_repository)]
        assert definition.namespace == MODULE
        assert definition.module == MODULE
