"""A way to interact with a third-party tool, as ``naas_abi_core.integration``.

Standard library only. The engine consumes nothing here: an integration is a
code pattern a module's workflows, pipelines and agents build on. Read its
credentials from ``self.engine.services.secret`` (needs the ``secret`` service
dependency) and pass them in through the configuration.
"""

from __future__ import annotations

from dataclasses import dataclass


class IntegrationConnectionError(Exception):
    pass


@dataclass
class IntegrationConfiguration:
    pass


class Integration:
    """Base class for connections to external services, APIs or tools.

    Attributes:
        __configuration (IntegrationConfiguration): Credentials and settings for
            connecting to the third-party tool.
    """

    __configuration: IntegrationConfiguration

    def __init__(self, configuration: IntegrationConfiguration):
        self.__configuration = configuration
