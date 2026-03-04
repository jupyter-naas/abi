from naas_abi_cli.cli.stack_runtime import ComposeServiceState, _parse_ps_json


def test_parse_ps_json_list_payload() -> None:
    payload = '[{"Service":"postgres","State":"running"}]'
    rows = _parse_ps_json(payload)
    assert len(rows) == 1
    assert rows[0]["Service"] == "postgres"


def test_parse_ps_json_single_payload() -> None:
    payload = '{"Service":"redis","State":"running"}'
    rows = _parse_ps_json(payload)
    assert len(rows) == 1
    assert rows[0]["Service"] == "redis"


def test_parse_ps_json_line_delimited_payload() -> None:
    payload = "\n".join(
        [
            '{"Service":"redis","State":"running"}',
            '{"Service":"postgres","State":"running"}',
        ]
    )
    rows = _parse_ps_json(payload)
    assert len(rows) == 2


def test_compose_service_state_dataclass() -> None:
    state = ComposeServiceState(
        service="abi",
        container_name="proj-abi-1",
        state="running",
        health="healthy",
        exit_code=None,
        status="Up 2m",
    )
    assert state.service == "abi"
    assert state.health == "healthy"
