from __future__ import annotations

from datetime import date, datetime

import pytest
from naas_abi.apps.nexus.apps.api.app.services.tasks.adapters.secondary.memory import (
    InMemoryTasksMemberDirectory,
    InMemoryTasksStore,
)
from naas_abi.apps.nexus.apps.api.app.services.tasks.service import TasksService
from naas_abi.apps.nexus.apps.api.app.services.tasks.tasks__schema import (
    ACTIVITY_ARCHIVED,
    ACTIVITY_ASSIGNEES,
    ACTIVITY_CREATED,
    ACTIVITY_ITERATION,
    ACTIVITY_STAGE,
    TasksAssigneeError,
    TasksNotFoundError,
    TasksSettings,
    TasksValidationError,
    iso_week_label,
    week_start,
)

WS = "ws-1"
OTHER_WS = "ws-2"
ALICE = "u-alice"
BOB = "u-bob"
# Thursday of ISO week 43 of 2026.
THURSDAY = date(2026, 10, 22)


@pytest.fixture
def service() -> TasksService:
    members = InMemoryTasksMemberDirectory({WS: {ALICE, BOB}, OTHER_WS: {ALICE}})
    ticks = iter(range(10_000))
    return TasksService(
        InMemoryTasksStore(),
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


async def test_ensure_iteration_creates_current_iso_week(service: TasksService):
    iteration = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)

    assert iteration.start_date == date(2026, 10, 19)
    assert iteration.end_date == date(2026, 10, 25)
    assert iteration.iso_week == "2026-W43"
    assert iteration.created_by == ALICE


async def test_ensure_iteration_is_idempotent_within_a_week(service: TasksService):
    first = await service.ensure_iteration(WS, date(2026, 10, 19), user_id=ALICE)
    again = await service.ensure_iteration(WS, date(2026, 10, 25), user_id=BOB)

    assert again.id == first.id
    assert len(await service.list_iterations(WS)) == 1


async def test_adjacent_iterations_are_created_on_demand(service: TasksService):
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


async def test_iteration_goal_is_trimmed_and_bounded(service: TasksService):
    iteration = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)

    updated = await service.update_iteration_goal(
        WS, iteration.id, "  Ship the release  ", user_id=BOB
    )

    assert updated.goal == "Ship the release"
    assert updated.updated_by == BOB
    with pytest.raises(TasksValidationError):
        await service.update_iteration_goal(WS, iteration.id, "x" * 201, user_id=BOB)


async def test_iterations_are_workspace_scoped(service: TasksService):
    iteration = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)

    assert await service.list_iterations(OTHER_WS) == []
    with pytest.raises(TasksNotFoundError):
        await service.get_iteration(OTHER_WS, iteration.id)


# ---------------------------------------------------------------------------
# Tasks
# ---------------------------------------------------------------------------


async def test_new_iteration_task_starts_in_the_default_stage(service: TasksService):
    iteration = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)

    task = await service.create_task(
        WS, {"title": " Write spec ", "iteration_id": iteration.id}, user_id=ALICE
    )

    assert task.title == "Write spec"
    assert task.stage == "ready"
    assert task.iteration_id == iteration.id
    assert task.created_by == ALICE and task.updated_by == ALICE
    assert task.created_at is not None
    assert await service.list_tasks(WS, iteration_id=iteration.id) == [task]


async def test_task_without_iteration_is_in_backlog(service: TasksService):
    iteration = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)
    task = await service.create_task(WS, {"title": "Idea"}, user_id=ALICE)

    assert task.iteration_id is None
    assert await service.list_tasks(WS, iteration_id=None) == [task]
    assert await service.list_tasks(WS, iteration_id=iteration.id) == []


async def test_task_validation(service: TasksService):
    with pytest.raises(TasksValidationError):
        await service.create_task(WS, {"title": "   "}, user_id=ALICE)
    with pytest.raises(TasksValidationError):
        await service.create_task(WS, {"title": "T", "stage": "doing"}, user_id=ALICE)
    with pytest.raises(TasksValidationError):
        await service.create_task(WS, {"title": "T", "priority": "critical"}, user_id=ALICE)
    with pytest.raises(TasksValidationError):
        await service.create_task(WS, {"title": "T", "owner": ALICE}, user_id=ALICE)
    with pytest.raises(TasksNotFoundError):
        await service.create_task(WS, {"title": "T", "iteration_id": "missing"}, user_id=ALICE)


async def test_task_properties_are_normalised(service: TasksService):
    task = await service.create_task(
        WS,
        {
            "title": "Model eval",
            "content": "line 1\nline 2",
            "priority": "high",
            "due_date": date(2026, 11, 2),
            "labels": ["Feature", " Data ", "Feature", ""],
        },
        user_id=ALICE,
    )

    assert task.content == "line 1\nline 2"
    assert task.priority == "high"
    assert task.due_date == date(2026, 11, 2)
    assert task.labels == ("Feature", "Data")


async def test_update_records_audit_and_activity(service: TasksService):
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


async def test_update_without_tracked_change_records_no_activity(service: TasksService):
    task = await service.create_task(WS, {"title": "T"}, user_id=ALICE)

    await service.update_task(WS, task.id, {"title": "Renamed", "stage": "inbox"}, user_id=ALICE)

    assert [a.field for a in await service.list_activity(WS, task.id)] == [ACTIVITY_CREATED]


async def test_assign_and_unassign_members(service: TasksService):
    task = await service.create_task(
        WS, {"title": "T", "assignee_ids": [ALICE, BOB, ALICE]}, user_id=ALICE
    )
    assert task.assignee_ids == (ALICE, BOB)

    task = await service.update_task(WS, task.id, {"assignee_ids": [BOB]}, user_id=ALICE)
    assert task.assignee_ids == (BOB,)


async def test_assignee_must_be_workspace_member(service: TasksService):
    with pytest.raises(TasksAssigneeError):
        await service.create_task(WS, {"title": "T", "assignee_ids": ["u-stranger"]}, user_id=ALICE)
    # BOB belongs to WS only.
    with pytest.raises(TasksAssigneeError):
        await service.create_task(OTHER_WS, {"title": "T", "assignee_ids": [BOB]}, user_id=ALICE)


async def test_tasks_are_workspace_scoped(service: TasksService):
    task = await service.create_task(WS, {"title": "T"}, user_id=ALICE)
    other_iteration = await service.ensure_iteration(OTHER_WS, THURSDAY, user_id=ALICE)

    assert await service.list_tasks(OTHER_WS, iteration_id=None) == []
    with pytest.raises(TasksNotFoundError):
        await service.update_task(OTHER_WS, task.id, {"title": "x"}, user_id=ALICE)
    with pytest.raises(TasksNotFoundError):
        await service.delete_task(OTHER_WS, task.id)
    # A task cannot be moved into another workspace's iteration.
    with pytest.raises(TasksNotFoundError):
        await service.update_task(WS, task.id, {"iteration_id": other_iteration.id}, user_id=ALICE)


async def test_list_all_tasks_spans_iterations_newest_first(service: TasksService):
    iteration = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)
    backlog = await service.create_task(WS, {"title": "Idea"}, user_id=ALICE)
    scheduled = await service.create_task(
        WS, {"title": "Planned", "iteration_id": iteration.id}, user_id=ALICE
    )
    archived = await service.create_task(WS, {"title": "Old"}, user_id=ALICE)
    await service.set_archived(WS, archived.id, True, user_id=ALICE)
    await service.create_task(OTHER_WS, {"title": "Elsewhere"}, user_id=ALICE)

    assert [t.id for t in await service.list_all_tasks(WS)] == [scheduled.id, backlog.id]
    assert [t.id for t in await service.list_all_tasks(WS, include_archived=True)] == [
        archived.id,
        scheduled.id,
        backlog.id,
    ]


async def test_archive_hides_and_restore_recovers(service: TasksService):
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


async def test_delete_removes_task_comments_and_activity(service: TasksService):
    task = await service.create_task(WS, {"title": "T"}, user_id=ALICE)
    await service.add_comment(WS, task.id, "Hello", user_id=ALICE)

    await service.delete_task(WS, task.id)

    with pytest.raises(TasksNotFoundError):
        await service.list_comments(WS, task.id)
    with pytest.raises(TasksNotFoundError):
        await service.delete_task(WS, task.id)


# ---------------------------------------------------------------------------
# Carry-over
# ---------------------------------------------------------------------------


async def test_carry_over_moves_unfinished_tasks_to_next_iteration(service: TasksService):
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


async def test_carry_over_reuses_existing_next_iteration(service: TasksService):
    current = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)
    following = await service.adjacent_iteration(WS, current.id, 1, user_id=ALICE)

    result = await service.carry_over(WS, current.id, user_id=ALICE)

    assert result.iteration.id == following.id
    assert result.moved == []


# ---------------------------------------------------------------------------
# Comments
# ---------------------------------------------------------------------------


async def test_comments_are_listed_oldest_first(service: TasksService):
    task = await service.create_task(WS, {"title": "T"}, user_id=ALICE)

    await service.add_comment(WS, task.id, " First ", user_id=ALICE)
    await service.add_comment(WS, task.id, "Second", user_id=BOB)

    comments = await service.list_comments(WS, task.id)
    assert [(c.author_id, c.body) for c in comments] == [(ALICE, "First"), (BOB, "Second")]
    with pytest.raises(TasksValidationError):
        await service.add_comment(WS, task.id, "  ", user_id=ALICE)
    with pytest.raises(TasksNotFoundError):
        await service.add_comment(OTHER_WS, task.id, "Hi", user_id=ALICE)


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------


def _settings_payload(settings: TasksSettings, **changes) -> dict:
    payload = {
        "iteration_weeks": settings.iteration_weeks,
        "iteration_start_day": settings.iteration_start_day,
        "stages": [vars(c) for c in settings.stages],
        "priorities": [vars(c) for c in settings.priorities],
        "default_stage": settings.default_stage,
        "suggested_labels": list(settings.suggested_labels),
    }
    payload.update(changes)
    return payload


async def test_defaults_match_iso_weeks(service: TasksService):
    settings = await service.get_settings(WS)
    assert settings.stage_keys[0] == "inbox" and settings.stage_keys[-1] == "done"
    assert settings.period(THURSDAY) == (date(2026, 10, 19), date(2026, 10, 25))


async def test_two_week_iterations_start_after_the_ongoing_one(service: TasksService):
    ongoing = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)
    current = await service.get_settings(WS)

    updated = await service.update_settings(
        WS, _settings_payload(current, iteration_weeks=2), today=THURSDAY, user_id=ALICE
    )

    assert updated.iteration_anchor == date(2026, 10, 26)
    # The ongoing week keeps its dates; the next iteration spans two weeks.
    assert (await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)).id == ongoing.id
    following = await service.adjacent_iteration(WS, ongoing.id, 1, user_id=ALICE)
    assert (following.start_date, following.end_date) == (date(2026, 10, 26), date(2026, 11, 8))
    assert following.iso_week == "2026-W44–W45"


async def test_new_start_day_bridges_the_gap_without_overlap(service: TasksService):
    ongoing = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)
    current = await service.get_settings(WS)
    # Iterations now start on Wednesdays.
    await service.update_settings(
        WS, _settings_payload(current, iteration_start_day=2), today=THURSDAY, user_id=ALICE
    )

    bridge = await service.adjacent_iteration(WS, ongoing.id, 1, user_id=ALICE)
    assert (bridge.start_date, bridge.end_date) == (date(2026, 10, 26), date(2026, 10, 27))
    regular = await service.adjacent_iteration(WS, bridge.id, 1, user_id=ALICE)
    assert (regular.start_date, regular.end_date) == (date(2026, 10, 28), date(2026, 11, 3))


async def test_custom_stages_and_priorities_drive_validation(service: TasksService):
    current = await service.get_settings(WS)
    stages = [vars(c) for c in current.stages]
    stages.insert(2, {"key": "", "label": "QA check", "color": "pink"})
    priorities = [
        {"key": "", "label": "P0", "color": "red"},
        *[vars(c) for c in current.priorities],
    ]

    updated = await service.update_settings(
        WS,
        _settings_payload(current, stages=stages, priorities=priorities),
        today=THURSDAY,
        user_id=ALICE,
    )

    assert updated.stage_keys[2] == "qa_check"
    assert updated.priority_keys[0] == "p0"
    task = await service.create_task(
        WS, {"title": "T", "stage": "qa_check", "priority": "p0"}, user_id=ALICE
    )
    assert (task.stage, task.priority) == ("qa_check", "p0")
    with pytest.raises(TasksValidationError):
        await service.create_task(WS, {"title": "T", "stage": "doing"}, user_id=ALICE)


async def test_settings_validation(service: TasksService):
    current = await service.get_settings(WS)
    bad = [
        {"iteration_weeks": 5},
        {"iteration_start_day": 7},
        {"stages": [vars(c) for c in current.stages][1:]},
        {
            "stages": [
                *[vars(c) for c in current.stages],
                {"key": "", "label": "x", "color": "neon"},
            ]
        },
        {"default_stage": "inbox"},
        {"priorities": []},
    ]
    for changes in bad:
        with pytest.raises(TasksValidationError):
            await service.update_settings(
                WS, _settings_payload(current, **changes), today=THURSDAY, user_id=ALICE
            )


async def test_removing_a_stage_or_priority_in_use_is_refused(service: TasksService):
    current = await service.get_settings(WS)
    await service.create_task(
        WS, {"title": "T", "stage": "on_hold", "priority": "low"}, user_id=ALICE
    )
    without_hold = [vars(c) for c in current.stages if c.key != "on_hold"]
    without_low = [vars(c) for c in current.priorities if c.key != "low"]

    with pytest.raises(TasksValidationError, match="1 task in stage on_hold"):
        await service.update_settings(
            WS, _settings_payload(current, stages=without_hold), today=THURSDAY, user_id=ALICE
        )
    with pytest.raises(TasksValidationError, match="priority low"):
        await service.update_settings(
            WS, _settings_payload(current, priorities=without_low), today=THURSDAY, user_id=ALICE
        )
    # Unused ones can go.
    without_review = [vars(c) for c in current.stages if c.key != "review"]
    updated = await service.update_settings(
        WS, _settings_payload(current, stages=without_review), today=THURSDAY, user_id=ALICE
    )
    assert "review" not in updated.stage_keys


async def test_tasks_and_their_records_carry_the_workspace(service: TasksService):
    iteration = await service.ensure_iteration(WS, THURSDAY, user_id=ALICE)
    task = await service.create_task(
        WS, {"title": "T", "iteration_id": iteration.id}, user_id=ALICE
    )
    comment = await service.add_comment(WS, task.id, "Hi", user_id=ALICE)
    activity = await service.list_activity(WS, task.id)

    assert iteration.workspace_id == WS
    assert task.workspace_id == WS
    assert comment.workspace_id == WS
    assert {a.workspace_id for a in activity} == {WS}
