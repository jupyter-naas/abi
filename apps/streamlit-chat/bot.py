import streamlit as st
from utils import write_message
from agent import generate_response
from os import environ

# Set page config
page_title = "Naas.ai"
page_icon = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABwAAAAcCAMAAABF0y+mAAAAbFBMVEUYGhwQEhUAAAYVFxkGCw4AAAAVGBpOT1GLjY5GR0koKSttbnCqqqu2treRk5RTVFUbHR8TFRgkJSf////IycnR0dEzNDa7vLz29va+v7/Y2Nmenp/n6OgABwtcXV7f4OB5enukpKU6Oz0/QEKodfx9AAAAfklEQVR4AdVPxRHEQAwLL6PDDP3XeMye+yf6mC0pOCbCKIyTNE3DDM9iQhkXUmljHZp5BXkBV8jSoWEFUBdV0wJ0PsbDuivTlFXQmxAPm/LSHMYJZjwEmVwSVzaggz/Dq7LOxjsfWgnLcE0ChawE2SrK+La2XZMfuCR+J4fEGdDqCumQc8zDAAAAAElFTkSuQmCC"
st.set_page_config(
    page_title,
    page_icon=page_icon
    )

# Set up Session State
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Hi, I'm the Your Content Assistant!  How can I help you?"},
    ]

# Submit handler
def handle_submit(message):
    """
    Submit handler:

    You will modify this method to talk with an LLM and provide
    context using data from Neo4j.
    """

    # Handle the response
    with st.spinner('Thinking...'):

        response = generate_response(message)
        write_message('assistant', response)

# Display messages in Session State
for message in st.session_state.messages:
    write_message(message['role'], message['content'], save=False)

# Handle any user input
if prompt := st.chat_input("What is up?"):
    # Display user message in chat message container
    write_message('user', prompt)

    # Generate a response
    handle_submit(prompt)
