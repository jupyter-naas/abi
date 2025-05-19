from dataclasses import dataclass


class IntegrationConnectionError(Exception):
    pass


@dataclass
class IntegrationConfiguration:
    pass


class Integration:
    """An Integration represents a way to interact with a third-party tool.

    The Integration class serves as a base class for implementing connections to external services,
    APIs, or tools. It provides a standardized interface for configuring and establishing these
    connections.

    Attributes:
        __configuration (IntegrationConfiguration): Configuration instance containing
            necessary credentials and settings for connecting to the third-party tool.
    """

    __configuration: IntegrationConfiguration

    def __init__(self, configuration: IntegrationConfiguration):
        self.__configuration = configuration
