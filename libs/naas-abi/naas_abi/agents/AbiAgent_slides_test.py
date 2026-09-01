import inspect

from naas_abi.agents.AbiAgent import AbiAgent


def test_slides_guidelines_require_research_before_write() -> None:
    prompt = AbiAgent.system_prompt
    assert "web_search" in prompt
    assert "Research loop" in prompt
    assert "start writing immediately" not in prompt
    assert "Context / Approach / Plan" in prompt


def test_new_accepts_model_id() -> None:
    assert "model_id" in inspect.signature(AbiAgent.New).parameters
