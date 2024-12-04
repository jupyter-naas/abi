from lib.abi.integration.integration import Integration, IntegrationConfiguration
from dataclasses import dataclass

@dataclass
class YourIntegrationConfiguration(IntegrationConfiguration):
    """Configuration for YourIntegration.
    
    Attributes:
        attribute_1 (str): Description of attribute_1
        attribute_2 (int): Description of attribute_2
    """
    attribute_1: str
    attribute_2: int

class YourIntegration(Integration):
    """YourIntegration class for interacting with YourService.
    
    This class provides methods to interact with YourService's API endpoints.
    It handles authentication and request management.
    
    Attributes:
        __configuration (YourIntegrationConfiguration): Configuration instance
            containing necessary credentials and settings.
    
    Example:
        >>> config = YourIntegrationConfiguration(
        ...     attribute_1="value1",
        ...     attribute_2=42
        ... )
        >>> integration = YourIntegration(config)
    """

    __configuration: YourIntegrationConfiguration

    def __init__(self, configuration: YourIntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

