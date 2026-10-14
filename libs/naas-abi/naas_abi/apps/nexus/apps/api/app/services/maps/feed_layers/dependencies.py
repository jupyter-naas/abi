"""The process-wide map layer service (built on first use: it sits on the feed service)."""

from __future__ import annotations

from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.service import (
    MapsFeedLayerService,
)

_service: MapsFeedLayerService | None = None


def get_maps_feed_layer_service() -> MapsFeedLayerService:
    global _service
    if _service is None:
        from naas_abi.apps.nexus.apps.api.app.services.maps.feed_layers.adapters.secondary.postgres import (  # noqa: E501
            PostgresMapsFeedLayerStore,
        )
        from naas_abi.apps.nexus.apps.api.app.services.maps.layouts.adapters.primary.maps_layouts__primary_adapter__FastAPI import (  # noqa: E501
            get_maps_layout_service,
        )
        from naas_abi.apps.nexus.apps.api.app.services.maps.settings.adapters.secondary.postgres import (  # noqa: E501
            PostgresMapsSettingsStore,
        )

        _service = MapsFeedLayerService(
            PostgresMapsFeedLayerStore(), PostgresMapsSettingsStore(), get_maps_layout_service()
        )
    return _service
