from ports.models import ConflictEvent
from services.conflict.ConflictPort import IConflictAdapter, IConflictService


class ConflictService(IConflictService):
    def __init__(self, adapter: IConflictAdapter) -> None:
        self._adapter = adapter

    def get_events(self) -> list[ConflictEvent]:
        return self._adapter.fetch()
