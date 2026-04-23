"""Tests for the AWS deploy scaffolding.

These tests cover template rendering + state round-trip without touching AWS
or `terraform`. The plan/apply commands that shell out to `terraform` are not
exercised here — they're thin wrappers.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from click.testing import CliRunner

from . import aws as aws_module
from .aws import AwsDeployConfig, _load_state, _save_state, _render_templates


def _config(env: str = "dev") -> AwsDeployConfig:
    return AwsDeployConfig(
        project="abi-test",
        env=env,
        region="us-east-1",
        account_id="123456789012",
        base_domain="dev.example.com",
        github_repo="jupyter-naas/abi",
        synapse_enabled=False,
        multi_tenant=True,
    )


def test_state_round_trip(tmp_path: Path) -> None:
    config = _config()
    _save_state(str(tmp_path), config)

    loaded = _load_state(str(tmp_path))
    assert loaded == config


def test_load_state_missing_returns_none(tmp_path: Path) -> None:
    assert _load_state(str(tmp_path)) is None


def test_state_bucket_and_lock_table_naming() -> None:
    config = _config()
    assert config.state_bucket == "abi-test-tfstate-123456789012-us-east-1"
    assert config.lock_table == "abi-test-tflock"


def test_render_templates_produces_expected_files(tmp_path: Path) -> None:
    config = _config()
    destination = tmp_path / "infra/terraform/envs/dev"
    _render_templates(config, destination)

    expected = {
        "main.tf",
        "variables.tf",
        "outputs.tf",
        "versions.tf",
        "backend.tf",
        "terraform.auto.tfvars",
    }
    assert expected.issubset({p.name for p in destination.iterdir()})


def test_rendered_tfvars_carries_user_input(tmp_path: Path) -> None:
    config = _config()
    destination = tmp_path / "envs/dev"
    _render_templates(config, destination)

    tfvars = (destination / "terraform.auto.tfvars").read_text()
    assert 'project         = "abi-test"' in tfvars
    assert 'env             = "dev"' in tfvars
    assert 'region          = "us-east-1"' in tfvars
    assert "synapse_enabled = false" in tfvars
    assert "multi_tenant    = true" in tfvars


def test_init_fails_when_env_dir_exists_without_force(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    env_dir = tmp_path / "infra/terraform/envs/dev"
    env_dir.mkdir(parents=True)

    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    result = runner.invoke(aws_module.init, ["-e", "dev"], input="\n")

    assert result.exit_code != 0
    assert "already exists" in result.output


def test_init_renders_templates_with_prompts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)

    # Answers for: project, region, account_id, base_domain, github_repo,
    # synapse (confirm), multi_tenant (confirm).
    answers = "\n".join([
        "",  # project → default (tmp_path name)
        "us-east-1",
        "123456789012",
        "dev.example.com",
        "jupyter-naas/abi",
        "n",  # synapse_enabled
        "y",  # multi_tenant
    ]) + "\n"

    runner = CliRunner()
    result = runner.invoke(aws_module.init, ["-e", "dev"], input=answers)

    assert result.exit_code == 0, result.output
    env_dir = tmp_path / "infra/terraform/envs/dev"
    assert (env_dir / "main.tf").exists()
    assert (env_dir / "terraform.auto.tfvars").exists()
    assert (tmp_path / ".abi-aws.json").exists()


def test_commands_fail_without_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    for cmd in (aws_module.plan, aws_module.apply, aws_module.destroy, aws_module.show_output):
        result = runner.invoke(cmd, ["-e", "dev"])
        assert result.exit_code != 0
        assert "No AWS deploy state found" in result.output


def test_aws_group_is_registered_in_deploy() -> None:
    from .deploy import deploy

    assert "aws" in deploy.commands


def test_new_commands_are_registered() -> None:
    expected = {"init", "plan", "apply", "destroy", "output",
                "kubeconfig", "deploy-apps", "ecr-login", "build-push"}
    assert expected.issubset(set(aws_module.aws.commands.keys()))


def test_render_values_from_outputs() -> None:
    config = _config()
    outputs = {
        "cluster_name": {"value": "abi-dev"},
        "ecr_repositories": {"value": {
            "abi": "111.dkr.ecr.us-east-1.amazonaws.com/abi/abi",
            "dagster": "111.dkr.ecr.us-east-1.amazonaws.com/abi/dagster",
            "mcp-server": "111.dkr.ecr.us-east-1.amazonaws.com/abi/mcp-server",
            "nexus-web": "111.dkr.ecr.us-east-1.amazonaws.com/abi/nexus-web",
            "service-portal": "111.dkr.ecr.us-east-1.amazonaws.com/abi/service-portal",
        }},
        "abi_api_role_arn": {"value": "arn:aws:iam::111:role/abi-api"},
        "tenant_secrets_role_arn": {"value": "arn:aws:iam::111:role/tenant-secrets"},
    }
    values = aws_module._render_values_from_outputs(config, outputs, "v1.2.3")

    assert values["global"]["awsAccountId"] == "123456789012"
    assert values["global"]["imageTag"] == "v1.2.3"
    assert values["abiApi"]["image"]["repository"].endswith("/abi/abi")
    assert values["externalSecrets"]["secrets"]["rds"] == "abi-test/dev/rds/main"
    assert values["externalSecrets"]["serviceAccountRoleArn"].endswith("tenant-secrets")
    assert values["synapse"]["enabled"] is False
