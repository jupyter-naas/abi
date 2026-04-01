from naas_abi.apps.nexus.apps.api.app.services.iam.service import IAMService


class ServiceBase:
    @property
    def iam(self) -> IAMService:
        from naas_abi.apps.nexus.apps.api.app.services.registry import ServiceRegistry

        return ServiceRegistry.instance().iam
