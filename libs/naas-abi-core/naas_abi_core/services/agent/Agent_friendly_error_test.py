from naas_abi_core.services.agent.Agent import _friendly_model_invoke_error


def test_friendly_model_invoke_error_rewrites_429() -> None:
    raw = (
        "Error code: 429 - {'error': {'message': 'Provider returned error', "
        "'code': 429, 'metadata': {'raw': "
        "'google/gemma-4-26b-a4b-it:free is temporarily rate-limited upstream.'}}}"
    )
    assert _friendly_model_invoke_error(Exception(raw)) == (
        "This model is rate limited. Pick another model in the agent menu and try again."
    )


def test_friendly_model_invoke_error_hides_json_dump() -> None:
    raw = "Error code: 500 - {'error': {'message': 'Provider returned error', 'code': 500}}"
    assert _friendly_model_invoke_error(Exception(raw)) == (
        "The model provider failed. Pick another model and try again."
    )
