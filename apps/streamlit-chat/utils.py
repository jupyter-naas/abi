import streamlit as st
from os import environ

avatar_assistant = "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/content_creation.png"
avatar_human = environ.get("AVATAR", "ABI")

def write_message(role, content, save=True):
    """
    This is a helper function that saves a message to the
    session state and then writes a message to the UI
    """
    # Append to session state
    if save:
        st.session_state.messages.append({"role": role, "content": content})

    # Write to UI
    if role == "assistant":
        avatar = avatar_assistant
    else:
        avatar = avatar_human
    with st.chat_message(role, avatar=avatar):
        st.markdown(content)
