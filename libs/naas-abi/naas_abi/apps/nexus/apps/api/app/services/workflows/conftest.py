"""Workflows are the platform admin's, decided by IAM: ``root`` holds
``builtin.platform_admin``, ``u1`` holds nothing."""

import pytest


@pytest.fixture(autouse=True)
def platform_admin_root(nexus_iam):
    nexus_iam.platform_admin("root")
    nexus_iam.user("u1")
    return nexus_iam
