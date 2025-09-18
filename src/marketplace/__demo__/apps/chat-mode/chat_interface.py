"""
ABI Chat Interface - Clean, minimal, functional
Uses the same initialization as the terminal agent for consistency
"""

import streamlit as st
import os
import sys
from pathlib import Path
from datetime import datetime
import re

# Load environment first
from dotenv import load_dotenv
load_dotenv()

# Environment setup - ensure we're in the correct project root
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
os.chdir(str(project_root))

# Debug path information
st.write(f"🔍 **Debug:** Current working directory: {os.getcwd()}")
st.write(f"🔍 **Debug:** Project root: {project_root}")
st.write(f"🔍 **Debug:** Python path includes: {str(project_root) in sys.path}")

# Set environment for development
os.environ['ENV'] = 'dev'
os.environ['LOG_LEVEL'] = 'ERROR'  # Reduce noise in Streamlit

# Page config
st.set_page_config(
    page_title="ABI Chat", 
    page_icon="🤖", 
    layout="centered"
)

# Session state initialization
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'agent' not in st.session_state:
    st.session_state.agent = None
if 'active_agent' not in st.session_state:
    st.session_state.active_agent = "Abi"

# Agent name mapping for @mentions
AGENT_MAPPING = {
    "abi": "Abi", "claude": "Claude", "gemini": "Gemini", 
    "mistral": "Mistral", "chatgpt": "ChatGPT", "grok": "Grok",
    "llama": "Llama", "perplexity": "Perplexity", "qwen": "Qwen",
    "deepseek": "DeepSeek", "gemma": "Gemma"
}

def load_agent(agent_class: str):
    """Load agent from modules like terminal agent does"""
    try:
        st.write("🔍 **Debug:** Attempting to import modules...")
        
        # Check if we can import src
        try:
            import src
            st.write(f"🔍 **Debug:** ✅ Successfully imported src from: {src.__file__}")
        except Exception as e:
            st.error(f"❌ Cannot import src: {e}")
            return None
        
        # Try to import modules
        from src import modules
        st.write("🔍 **Debug:** ✅ Successfully imported modules")
        
        # Force modules to load if they haven't been loaded yet
        loaded_modules = modules  # This triggers the LazyLoader
        
        st.write(f"🔍 **Debug:** Found {len(loaded_modules)} modules")
        
        if len(loaded_modules) == 0:
            st.error("❌ No modules loaded - check module loading errors")
            return None
        
        for module in loaded_modules:
            st.write(f"🔍 **Debug:** Checking module {module.module_import_path}")
            st.write(f"🔍 **Debug:** Module has {len(module.agents)} agents")
            
            for agent in module.agents:
                agent_name = agent.__class__.__name__
                st.write(f"🔍 **Debug:** Found agent: {agent_name}")
                if agent_name == agent_class:
                    st.write(f"🔍 **Debug:** ✅ Found matching agent: {agent_name}")
                    return agent
        
        st.write(f"🔍 **Debug:** ❌ Agent {agent_class} not found in any module")
        return None
    except Exception as e:
        st.error(f"Error loading modules: {str(e)}")
        import traceback
        st.error(f"Traceback: {traceback.format_exc()}")
        return None

def initialize_agent():
    """Initialize ABI agent using the same approach as terminal agent"""
    if st.session_state.agent is not None:
        return st.session_state.agent
    
    try:
        # Load agent from modules like terminal agent does
        agent = load_agent("AbiAgent")
        
        if not agent:
            st.error("Failed to load AbiAgent from modules")
            return None
        
        st.session_state.agent = agent
        return agent
        
    except Exception as e:
        st.error(f"Error initializing agent: {str(e)}")
        return None

def handle_agent_response(response):
    """Handle agent response like terminal agent does"""
    if not response:
        return
    
    # Extract content from response
    content = ""
    if hasattr(response, 'content'):
        content = response.content
    elif isinstance(response, str):
        content = response
    elif hasattr(response, 'messages') and response.messages:
        # Handle message list response
        for msg in response.messages:
            if hasattr(msg, 'content') and msg.content:
                content += msg.content + "\n"
    
    if content:
        # Clean up the content (remove thinking tags, etc.)
        content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
        if content:
            st.session_state.messages.append({"role": "assistant", "content": content})

def process_user_input(user_input):
    """Process user input and handle @mentions like terminal interface"""
    # Check for @mentions (like terminal line 344)
    mention_match = re.search(r'@(\w+)', user_input.lower())
    if mention_match:
        mentioned_agent = mention_match.group(1)
        if mentioned_agent in AGENT_MAPPING:
            # Update active agent (like terminal line 361)
            st.session_state.active_agent = AGENT_MAPPING[mentioned_agent]
            st.write(f"🔍 **@mention detected:** Switching to {AGENT_MAPPING[mentioned_agent]}")
            
            # Clean input (like terminal line 363)
            user_input_clean = re.sub(r'@\w+\s*', '', user_input).strip()
            if user_input_clean:
                # There's additional content, send it to the mentioned agent (like terminal line 366)
                user_input = f"ask {mentioned_agent} {user_input_clean}"
            else:
                # Just the mention, initiate conversation with agent (like terminal line 369)
                user_input = f"I want to talk to {mentioned_agent}"
                
            st.write(f"🔍 **Processed input:** '{user_input}'")
        else:
            st.error(f"Unknown agent: @{mentioned_agent}")
            st.error(f"Available agents: {', '.join([f'@{k}' for k in AGENT_MAPPING.keys()])}")
    
    return user_input

def send_message(user_input):
    """Send message to ABI agent with proper state management"""
    agent = st.session_state.agent
    if not agent:
        st.error("Agent not available")
        return
    
    try:
        st.write(f"🔍 **Sending Debug:** Input='{user_input}', Active Agent='{st.session_state.active_agent}'")
        
        # CRITICAL: Always use ABI orchestration like terminal does
        # Set active agent context BEFORE invoke (like terminal line 433)
        # Invoke agent like terminal agent does
        response = agent.invoke(user_input)
        
        # Handle the response
        handle_agent_response(response)
        
    except Exception as e:
        st.error(f"Error sending message: {e}")
        import traceback
        st.error(f"Traceback: {traceback.format_exc()}")

# UI Layout
st.title("🤖 ABI Chat")
st.caption(f"Active Agent: **{st.session_state.active_agent}**")

# Sidebar controls
with st.sidebar:
    st.header("Controls")
    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()
    
    if st.button("Reset Agent"):
        st.session_state.agent = None
        st.session_state.active_agent = "Abi"
        st.rerun()
    
    st.header("Available Agents")
    st.write("Use @mentions to switch:")
    for key, name in AGENT_MAPPING.items():
        st.write(f"• @{key} → {name}")

# Initialize agent
agent = initialize_agent()
if agent:
    st.success(f"✅ ABI Ready: {agent.name}")
else:
    st.error("❌ ABI not available")
    st.stop()

# Display messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            st.write(f"**{msg.get('agent', 'Abi')}:** {msg['content']}")
        else:
            st.write(msg["content"])

# Chat input
if prompt := st.chat_input("Type your message..."):
    # Add user message
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
        "timestamp": datetime.now()
    })
    
    # Display user message
    with st.chat_message("user"):
        st.write(prompt)
    
    # Process and send
    processed_input = process_user_input(prompt)
    
    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            send_message(processed_input)
    
    st.rerun()