from services.conflict.adapters.conflict_events import ConflictEventsAdapter
from services.conflict.ConflictService import ConflictService

conflict_service = ConflictService(adapter=ConflictEventsAdapter())

__all__ = ["conflict_service"]
