from dataclasses import dataclass

class IntegrationConnectionError(Exception):
    pass

@dataclass
class IntegrationConfiguration:
    pass

class Integration():
    __configuration: IntegrationConfiguration
    
    def __init__(self, configuration: IntegrationConfiguration):
        self.__configuration = configuration
