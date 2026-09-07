from ports.models import ConflictEvent


class IConflictAdapter:
    def fetch(self) -> list[ConflictEvent]:
        raise NotImplementedError


class IConflictService:
    def get_events(self) -> list[ConflictEvent]:
        raise NotImplementedError
