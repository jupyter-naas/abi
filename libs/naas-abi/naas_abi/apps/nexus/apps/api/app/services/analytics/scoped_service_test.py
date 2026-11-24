"""The scoped service: its pure helpers, and how the overview reads its figures."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.analytics.port import (
    AnalyticsScope,
    OverviewAggregate,
    PageAggregate,
    UserAggregate,
    WorkspaceAggregate,
)
from naas_abi.apps.nexus.apps.api.app.services.analytics.scoped_service import (
    ScopedAnalyticsService,
    _decorate_page_title,
)


def test_a_chat_page_title_names_its_conversation() -> None:
    assert _decorate_page_title("Chat", "/workspace/ws-1/chat/conv-abc") == "Chat - conv-abc"
    assert _decorate_page_title("Chat - conv-abc", "/chat/conv-abc?x=1") == "Chat - conv-abc"
    assert _decorate_page_title("Home", "/workspace/ws-1/home") == "Home"
    assert _decorate_page_title("Home", "") == "Home"


# -- the overview's reads ------------------------------------------------------------

SCOPE = AnalyticsScope("organization", "org-1", ("ws-1",), ("u-1",))


class SlowQueries:
    """Each read takes a while and notes how many reads were running with it."""

    def __init__(self, running: list[int], peak: list[int]) -> None:
        self.running, self.peak = running, peak

    async def _read(self, value):
        self.running[0] += 1
        self.peak[0] = max(self.peak[0], self.running[0])
        await asyncio.sleep(0.05)
        self.running[0] -= 1
        return value

    async def overview(self, scope, window):
        n = len(window.slots)
        return await self._read(OverviewAggregate(3, 60, 1, (0,) * n, (0,) * n))

    async def users(self, scope, window):
        return await self._read([UserAggregate("u-1", 3, 7, 1, 9, None)])

    async def pages(self, scope, window):
        return await self._read([PageAggregate("/chat", "Chat", 7, 1)])

    async def workspaces(self, scope, window):
        return await self._read([WorkspaceAggregate("ws-1", 1, 3, 9)])

    async def events(self, scope, window, *, limit):
        return await self._read([])

    async def user_emails(self, user_ids):
        return {"u-1": "u@example.com"}

    async def workspace_names(self, workspace_ids):
        return {"ws-1": "One"}


def _service(parallel: bool) -> tuple[ScopedAnalyticsService, list[int], list[int]]:
    running, peak, opened = [0], [0], [0]
    queries = SlowQueries(running, peak)

    @asynccontextmanager
    async def apart():
        opened[0] += 1
        yield SlowQueries(running, peak)

    service = ScopedAnalyticsService(
        queries,  # type: ignore[arg-type]
        now=lambda: datetime(2026, 11, 20, 10, tzinfo=UTC),
        parallel=apart if parallel else None,
    )
    return service, peak, opened


@pytest.mark.asyncio
async def test_the_overview_reads_its_five_figures_at_the_same_time() -> None:
    service, peak, opened = _service(parallel=True)
    response = await service.overview(SCOPE, service.window(SCOPE, "today"))
    assert peak[0] == 5 and opened[0] == 5  # each on a connection of its own
    assert response.kpi.total_sessions == 3 and response.kpi.active_users == 1
    assert response.top_pages[0].page_path == "/chat"
    assert response.kpi.most_active_workspace is not None
    assert response.kpi.most_active_workspace.name == "One"


@pytest.mark.asyncio
async def test_without_connections_of_their_own_the_reads_go_one_by_one() -> None:
    service, peak, opened = _service(parallel=False)
    response = await service.overview(SCOPE, service.window(SCOPE, "today"))
    assert peak[0] == 1 and opened[0] == 0
    assert response.kpi.total_sessions == 3
