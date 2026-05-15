from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)

NAME = "World Situation Room"
DESCRIPTION = "Real-time geospatial intelligence platform. Fuses live satellite orbits, commercial and military flight data, seismic activity, CCTV streams, and conflict-zone intelligence into a single 3D globe."
AVATAR_URL = "https://assets.naas.ai/marketplace/wsr/logo.png"
APP_URL = "https://worldsituationroom.com/"
DEMO_LOGIN = "demo@naas.ai"
DEMO_PASSWORD = "demo1234"
TIER = "community"
MAINTAINER = "naas.ai"


class ABIModule(BaseModule):
    dependencies: ModuleDependencies = ModuleDependencies(
        modules=[],
        services=[],
    )

    class Configuration(ModuleConfiguration):
        """
        Configuration for the World Situation Room module.

        module: naas_abi_marketplace.alpha.wsr
        enabled: true
        config:
            opensky_client_id: ""
            opensky_client_secret: ""
            tfl_app_key: ""
            openwebcamdb_api_key: ""
        """
        opensky_client_id: str = ""
        opensky_client_secret: str = ""
        tfl_app_key: str = ""
        openwebcamdb_api_key: str = ""
