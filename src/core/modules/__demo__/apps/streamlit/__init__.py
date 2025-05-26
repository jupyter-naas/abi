import streamlit as st

from abi.services.agent.Agent import Agent, AgentConfiguration
from langchain_core.tools import tool

from src.installed.modules.google.google_gemini_2_0_flash.models.google_gemini_2_0_flash import (
    model as gemini_model,
)


@tool
def add_one(x: int) -> int:
    """Add one to the input"""
    return x + 1


agent = Agent(
    name="ABI",
    description="You are ABI, a helpful assistant.",
    chat_model=gemini_model.model,
    tools=[add_one],
    configuration=AgentConfiguration(
        system_prompt="You are ABI, a helpful assistant.",
    ),
)

st.title("ABI Streamlit Demo")


def langgraph_to_langchain_stream(langgraph_stream):
    for chunk in langgraph_stream:
        _, element = chunk
        if "call_model" in element and "messages" in element["call_model"]:
            for message in element["call_model"]["messages"]:
                yield message.content
        else:
            yield element


if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("What is up?"):
    st.session_state.messages.append({"role": "user", "content": prompt})

    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        user_prompt = st.session_state.messages[-1]["content"]
        response = st.write_stream(
            langgraph_to_langchain_stream(agent.stream(user_prompt))
        )
    st.session_state.messages.append({"role": "assistant", "content": response})
