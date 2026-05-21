from naas_abi_core.module.Module import (
    BaseModule,
    ModuleConfiguration,
    ModuleDependencies,
)


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
            demo_login: ""
            demo_password: ""
        """
        opensky_client_id: str = ""
        opensky_client_secret: str = ""
        tfl_app_key: str = ""
        openwebcamdb_api_key: str = ""
        demo_login: str = ""
        demo_password: str = ""
