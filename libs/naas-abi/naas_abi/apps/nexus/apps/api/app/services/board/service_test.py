from __future__ import annotations

from datetime import date, datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.board.adapters.secondary.memory import (
    InMemoryBoardMemberDirectory,
    InMemoryBoardStore,
)
from naas_abi.apps.nexus.apps.api.app.services.board.board__schema import (
    ACTIVITY_ARCHIVED,
    ACTIVITY_ASSIGNEES,
    ACTIVITY_CREATED,
    ACTIVITY_ITERATION,
    ACTIVITY_STAGE,
    BoardAssigneeError,
    BoardNotFoundError,
    BoardValidationError,
    iso_week_label,
    week_start,
)
from naas_abi.apps.nexus.apps.api.app.services.board.service import BoardService

WS = "ws-1"
OTHER_WS = "ws-2"
ALICE = "u-alice"
BOB = "u-bob"
# Thursday of ISO week 43 of 2026.
THURSDAY = date(2026, 10, 22)


@pytest.fixture
def service() -> BoardService:
    members = InMemoryBoardMemberDirectory({WS: {ALICE, BOB}, OTHER_WS: {ALICE}})
    ticks = iter(range(10_000))
    return BoardService(
        InMemoryBoardStore(),
        members,
        clock=lambda: datetime(2026, 10, 22, 9, 0, next(ticks) % 60),
    )


# ---------------------------------------------------------------------------
# Iterations
# ---------------------------------------------------------------------------


def test_week_start_is_monday_for_every_day_of_the_week():
    for offset in range(7):
        assert week_start(date(2026, 10, 19 + offset)) == date(2026, 10, 19)


def test_week_start_crosses_year_boundary():
    # 2027-01-01 is a Friday in ISO week 53 of 2026.
    assert week_start(date(2027, 1, 1)) == date(2026, 12, 28)
    assert iso_week_label(date(2026, 12, 28)) == "2026-W53"


async def test_ensure_iteration_creates_current_iso_week(service: BoardService):
    iteration = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)

    assert iteration.start_date == date(2026, 10, 19)
    assert iteration.end_date == date(2026, 10, 25)
    assert iteration.iso_week == "2026-W43"
    assert iteration.created_by == ALICE


async def test_ensure_iteration_is_idempotent_within_a_week(service: BoardService):
    first = await service.ensure_iteration(WS, date(2026, 10, 19), user_id=ALICE)
    again = await service.ensure_iteration(WS, date(2026, 10, 25), user_id=BOB)

    assert again.id == first.id
    assert len(await service.list_iterations(WS)) == 1


async def test_adjacent_iterations_are_created_on_demand(service: BoardService):
    current = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)

    previous = await service.adjacent_iteration(WS, current.id, -1, user_id=ALICE)
    following = await service.adjacent_iteration(WS, current.id, 1, user_id=ALICE)

    assert previous.start_date == date(2026, 10, 12)
    assert following.start_date == date(2026, 10, 26)
    assert [i.start_date for i in await service.list_iterations(WS)] == [
        date(2026, 10, 12),
        date(2026, 10, 19),
        date(2026, 10, 26),
    ]


async def test_iteration_goal_is_trimmed_and_bounded(service: BoardService):
    iteration = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)

    updated = await service.update_iteration_goal(
        WS, iteration.id, "  Ship the board  ", user_id=BOB
    )

    assert updated.goal == "Ship the board"
    assert updated.updated_by == BOB
    with pytest.raises(BoardValidationError):
        await service.update_iteration_goal(WS, iteration.id, "x" * 201, user_id=BOB)


async def test_iterations_are_workspace_scoped(service: BoardService):
    iteration = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)

    assert await service.list_iterations(OTHER_WS) == []
    with pytest.raises(BoardNotFoundError):
        await service.get_iteration(OTHER_WS, iteration.id)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


async def test_new_task_defaults_to_inbox_in_selected_iteration(service: BoardService):
    iteration = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)

    task = await service.create_task(
        WS, {"title": " Write spec ", "iteration_id": iteration.id}, user_id=ALICE
    )

    assert task.title == "Write spec"
    assert task.stage == "inbox"
    assert task.iteration_id == iteration.id
    assert task.created_by == ALICE and task.updated_by == ALICE
    assert task.created_at is not None
    assert await service.list_tasks(WS, iteration_id=iteration.id) == [task]


async def test_task_without_iteration_is_in_backlog(service: BoardService):
    iteration = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)
    task = await service.create_task(WS, {"title": "Idea"}, user_id=ALICE)

    assert task.iteration_id is None
    assert await service.list_tasks(WS, iteration_id=None) == [task]
    assert await service.list_tasks(WS, iteration_id=iteration.id) == []


async def test_task_validation(service: BoardService):
    with pytest.raises(BoardValidationError):
        await service.create_task(WS, {"title": "   "}, user_id=ALICE)
    with pytest.raises(BoardValidationError):
        await service.create_task(WS, {"title": "T", "stage": "doing"}, user_id=ALICE)
    with pytest.raises(BoardValidationError):
        await service.create_task(WS, {"title": "T", "priority": "critical"}, user_id=ALICE)
    with pytest.raises(BoardValidationError):
        await service.create_task(WS, {"title": "T", "owner": ALICE}, user_id=ALICE)
    with pytest.raises(BoardNotFoundError):
        await service.create_task(WS, {"title": "T", "iteration_id": "missing"}, user_id=ALICE)


async def test_task_properties_are_normalised(service: BoardService):
    task = await service.create_task(
        WS,
        {
            "title": "Model eval",
            "content": "line 1\nline 2",
            "project": "  Nexus ",
            "priority": "high",
            "due_date": date(2026, 11, 2),
            "labels": ["Feature", " Data ", "Feature", ""],
        },
        user_id=ALICE,
    )

    assert task.content == "line 1\nline 2"
    assert task.project == "Nexus"
    assert task.priority == "high"
    assert task.due_date == date(2026, 11, 2)
    assert task.labels == ("Feature", "Data")


async def test_update_records_audit_and_activity(service: BoardService):
    iteration = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)
    task = await service.create_task(WS, {"title": "T"}, user_id=ALICE)

    updated = await service.update_task(
        WS,
        task.id,
        {"stage": "in_progress", "assignee_ids": [BOB], "iteration_id": iteration.id},
        user_id=BOB,
    )

    assert updated.stage == "in_progress"
    assert updated.assignee_ids == (BOB,)
    assert updated.updated_by == BOB
    assert updated.created_by == ALICE
    assert updated.updated_at is not None and updated.updated_at > task.updated_at  # type: ignore[operator]

    activity = await service.list_activity(WS, task.id)
    assert [(a.field, a.old_value, a.new_value) for a in activity] == [
        (ACTIVITY_CREATED, None, None),
        (ACTIVITY_STAGE, "inbox", "in_progress"),
        (ACTIVITY_ASSIGNEES, [], [BOB]),
        (ACTIVITY_ITERATION, None, iteration.id),
    ]
    assert activity[-1].actor_id == BOB


async def test_update_without_tracked_change_records_no_activity(service: BoardService):
    task = await service.create_task(WS, {"title": "T"}, user_id=ALICE)

    await service.update_task(WS, task.id, {"title": "Renamed", "stage": "inbox"}, user_id=ALICE)

    assert [a.field for a in await service.list_activity(WS, task.id)] == [ACTIVITY_CREATED]


async def test_assign_and_unassign_members(service: BoardService):
    task = await service.create_task(
        WS, {"title": "T", "assignee_ids": [ALICE, BOB, ALICE]}, user_id=ALICE
    )
    assert task.assignee_ids == (ALICE, BOB)

    task = await service.update_task(WS, task.id, {"assignee_ids": [BOB]}, user_id=ALICE)
    assert task.assignee_ids == (BOB,)


async def test_assignee_must_be_workspace_member(service: BoardService):
    with pytest.raises(BoardAssigneeError):
        await service.create_task(WS, {"title": "T", "assignee_ids": ["u-stranger"]}, user_id=ALICE)
    # BOB belongs to WS only.
    with pytest.raises(BoardAssigneeError):
        await service.create_task(OTHER_WS, {"title": "T", "assignee_ids": [BOB]}, user_id=ALICE)


async def test_tasks_are_workspace_scoped(service: BoardService):
    task = await service.create_task(WS, {"title": "T"}, user_id=ALICE)
    other_iteration = await service.ensure_iteration(OTHER_WS, THURSDAY, user_id=ALICE)

    assert await service.list_tasks(OTHER_WS, iteration_id=None) == []
    with pytest.raises(BoardNotFoundError):
        await service.update_task(OTHER_WS, task.id, {"title": "x"}, user_id=ALICE)
    with pytest.raises(BoardNotFoundError):
        await service.delete_task(OTHER_WS, task.id)
    # A task cannot be moved into another workspace's iteration.
    with pytest.raises(BoardNotFoundError):
        await service.update_task(WS, task.id, {"iteration_id": other_iteration.id}, user_id=ALICE)


async def test_archive_hides_and_restore_recovers(service: BoardService):
    task = await service.create_task(WS, {"title": "T"}, user_id=ALICE)

    archived = await service.set_archived(WS, task.id, True, user_id=BOB)
    assert archived.archived
    assert await service.list_tasks(WS, iteration_id=None) == []
    assert await service.list_tasks(WS, iteration_id=None, include_archived=True) == [archived]

    restored = await service.set_archived(WS, task.id, False, user_id=BOB)
    assert not restored.archived
    assert await service.list_tasks(WS, iteration_id=None) == [restored]
    assert [(a.field, a.new_value) for a in await service.list_activity(WS, task.id)][1:] == [
        (ACTIVITY_ARCHIVED, True),
        (ACTIVITY_ARCHIVED, False),
    ]


async def test_delete_removes_task_comments_and_activity(service: BoardService):
    task = await service.create_task(WS, {"title": "T"}, user_id=ALICE)
    await service.add_comment(WS, task.id, "Hello", user_id=ALICE)

    await service.delete_task(WS, task.id)

    with pytest.raises(BoardNotFoundError):
        await service.list_comments(WS, task.id)
    with pytest.raises(BoardNotFoundError):
        await service.delete_task(WS, task.id)


# ---------------------------------------------------------------------------
# Carry-over
# ---------------------------------------------------------------------------


async def test_carry_over_moves_unfinished_tasks_to_next_iteration(service: BoardService):
    current = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)
    done = await service.create_task(
        WS, {"title": "Done", "iteration_id": current.id, "stage": "done"}, user_id=ALICE
    )
    open_task = await service.create_task(
        WS, {"title": "Open", "iteration_id": current.id, "stage": "review"}, user_id=ALICE
    )
    archived = await service.create_task(
        WS, {"title": "Archived", "iteration_id": current.id}, user_id=ALICE
    )
    await service.set_archived(WS, archived.id, True, user_id=ALICE)

    result = await service.carry_over(WS, current.id, user_id=BOB)

    assert result.iteration.start_date == date(2026, 10, 26)
    assert [t.id for t in result.moved] == [open_task.id]
    moved = result.moved[0]
    assert moved.iteration_id == result.iteration.id
    assert moved.stage == "review"
    assert [t.id for t in await service.list_tasks(WS, iteration_id=current.id)] == [done.id]
    activity = await service.list_activity(WS, open_task.id)
    assert (activity[-1].field, activity[-1].old_value, activity[-1].new_value) == (
        ACTIVITY_ITERATION,
        current.id,
        result.iteration.id,
    )


async def test_carry_over_reuses_existing_next_iteration(service: BoardService):
    current = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)
    following = await service.adjacent_iteration(WS, current.id, 1, user_id=ALICE)

    result = await service.carry_over(WS, current.id, user_id=ALICE)

    assert result.iteration.id == following.id
    assert result.moved == []


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


async def test_comments_are_listed_oldest_first(service: BoardService):
    task = await service.create_task(WS, {"title": "T"}, user_id=ALICE)

    await service.add_comment(WS, task.id, " First ", user_id=ALICE)
    await service.add_comment(WS, task.id, "Second", user_id=BOB)

    comments = await service.list_comments(WS, task.id)
    assert [(c.author_id, c.body) for c in comments] == [(ALICE, "First"), (BOB, "Second")]
    with pytest.raises(BoardValidationError):
        await service.add_comment(WS, task.id, "  ", user_id=ALICE)
    with pytest.raises(BoardNotFoundError):
        await service.add_comment(OTHER_WS, task.id, "Hi", user_id=ALICE)
