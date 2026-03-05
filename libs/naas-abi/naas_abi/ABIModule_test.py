import pytest
from pydantic import ValidationError

from naas_abi import NexusConfig


def test_nexus_config_rejects_legacy_cors_origins_str() -> None:
    with pytest.raises(ValidationError):
        NexusConfig(cors_origins_str="https://nexus.example.com")


def test_nexus_config_rejects_legacy_cors_origins() -> None:
    with pytest.raises(ValidationError):
        NexusConfig(cors_origins='["https://nexus.example.com"]')
