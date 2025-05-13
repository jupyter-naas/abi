import streamlit as st
from pathlib import Path
import sys
import json
from datetime import datetime

# Add the project root to the Python path
project_root = Path(__file__).parent.parent.parent.parent.parent
sys.path.append(str(project_root))

from src.custom.modules.gpt_4o_disabled.agents.Gpt4oAgent import create_agent

def initialize_session_state():
    """Initialize session state variables if they don't exist"""
    if 'messages' not in st.session_state:
        st.session_state.messages = []
    if 'agent' not in st.session_state:
        st.session_state.agent = create_agent()

def save_conversation(messages, topic):
    """Save the conversation to a JSON file"""
    output_dir = project_root / 'storage' / 'datastore' / 'gpt-4o' / 'messages'
    output_dir.mkdir(parents=True, exist_ok=True)
    
    conversation_data = {
        'topic': topic,
        'messages': messages,
        'timestamp': datetime.now().isoformat(),
        'total_tokens': 0,  # Placeholder for token counting
        'processing_time': 0  # Placeholder for processing time
    }
    
    output_file = output_dir / f'conversation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
    with open(output_file, 'w') as f:
        json.dump(conversation_data, f, indent=2)

def main():
    st.title("GPT-4o Chat Interface")
    
    # Initialize session state
    initialize_session_state()
    
    # Sidebar for settings
    with st.sidebar:
        st.header("Settings")
        topic = st.text_input("Conversation Topic", "General Discussion")
        
        if st.button("Clear Chat"):
            st.session_state.messages = []
            st.rerun()
    
    # Display chat messages
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Chat input
    if prompt := st.chat_input("What would you like to discuss?"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Get AI response
        with st.chat_message("assistant"):
            with st.spinner("Thinking..."):
                response = st.session_state.agent.run(prompt)
                st.markdown(response)
                st.session_state.messages.append({"role": "assistant", "content": response})
        
        # Save conversation periodically
        if len(st.session_state.messages) % 5 == 0:  # Save every 5 messages
            save_conversation(st.session_state.messages, topic)

if __name__ == "__main__":
    main()
