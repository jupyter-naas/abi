import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

import requests
from naas_abi_core import logger
from naas_abi_core.integration import Integration, IntegrationConfiguration
from naas_abi_core.integration.integration import IntegrationConnectionError
from naas_abi_core.services.cache.CacheFactory import CacheFactory
from naas_abi_core.services.cache.CachePort import DataType
from naas_abi_core.services.cache.CacheService import CacheService


@dataclass
class {{integration_name_pascal}}IntegrationConfiguration(IntegrationConfiguration):
    """Configuration for the {{integration_name_pascal}} integration."""
    pass


class {{integration_name_pascal}}Integration(Integration):
    """{{integration_name_pascal}} integration."""

    __configuration: {{integration_name_pascal}}IntegrationConfiguration

    def __init__(self, configuration: {{integration_name_pascal}}IntegrationConfiguration):
        super().__init__(configuration)
        self.__configuration = configuration

