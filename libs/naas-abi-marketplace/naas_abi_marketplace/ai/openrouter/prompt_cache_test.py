from langchain_core.messages import AIMessage, HumanMessage, SystemMessage, ToolMessage
from naas_abi_marketplace.ai.openrouter.prompt_cache import (
    CACHE_CONTROL,
    OpenRouterChatOpenAI,
    add_cache_breakpoints,
)
from pydantic import SecretStr


def model(model_id: str) -> OpenRouterChatOpenAI:
    return OpenRouterChatOpenAI(
        model=model_id,
        api_key=SecretStr("test"),
        base_url="https://openrouter.ai/api/v1",
    )


CONVERSATION = [
    SystemMessage("You are Abi."),
    HumanMessage("first question"),
    AIMessage("", tool_calls=[{"name": "search", "args": {}, "id": "c1"}]),
    ToolMessage("results", tool_call_id="c1"),
    HumanMessage("second question"),
]


def test_an_anthropic_model_marks_the_system_prompt_and_the_last_user_message():
    messages = model("anthropic/claude-sonnet-5")._get_request_payload(CONVERSATION)[
        "messages"
    ]

    assert messages[0]["content"] == [
        {"type": "text", "text": "You are Abi.", "cache_control": CACHE_CONTROL}
    ]
    assert messages[-1]["content"] == [
        {"type": "text", "text": "second question", "cache_control": CACHE_CONTROL}
    ]
    assert messages[1]["content"] == "first question"
    assert messages[3]["content"] == "results"


def test_tools_are_sent_unchanged_ahead_of_the_marked_system_prompt():
    bound = model("anthropic/claude-sonnet-5").bind_tools(
        [{"type": "function", "function": {"name": "search", "parameters": {}}}]
    )
    payload = bound.bound._get_request_payload(CONVERSATION, **bound.kwargs)

    assert [tool["function"]["name"] for tool in payload["tools"]] == ["search"]
    assert "cache_control" in payload["messages"][0]["content"][0]


def test_other_providers_are_left_alone():
    messages = model("openai/gpt-4.1-mini")._get_request_payload(CONVERSATION)[
        "messages"
    ]

    assert messages[0]["content"] == "You are Abi."
    assert messages[-1]["content"] == "second question"


def test_list_content_gets_the_breakpoint_on_its_last_text_part():
    marked = add_cache_breakpoints(
        [
            {
                "role": "user",
                "content": [
                    {"type": "image_url", "image_url": {"url": "data:,"}},
                    {"type": "text", "text": "what is this?"},
                ],
            }
        ]
    )

    assert marked[0]["content"][0] == {
        "type": "image_url",
        "image_url": {"url": "data:,"},
    }
    assert marked[0]["content"][1]["cache_control"] == CACHE_CONTROL


def test_empty_content_is_not_marked():
    assert add_cache_breakpoints([{"role": "user", "content": ""}]) == [
        {"role": "user", "content": ""}
    ]
