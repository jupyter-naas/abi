"""
ABI Chat Interface - Clean, minimal, functional
"""

import streamlit as st
import os
import sys
from pathlib import Path
from datetime import datetime
import re

# Load environment
from dotenv import load_dotenv

# Environment setup
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
os.chdir(str(project_root))
load_dotenv()
os.environ['ENV'] = 'dev'
os.environ['LOG_LEVEL'] = 'DEBUG'  # Increase logging for debugging

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

def initialize_agent():
    """Initialize ABI agent with proper error handling"""
    if st.session_state.agent is not None:
        return st.session_state.agent
    
    try:
        from src.core.modules.abi.agents.AbiAgent import create_agent
        
        agent = create_agent()
        if not agent:
            st.error("Failed to create ABI agent")
            return None
        
        # Debug: Show agent structure
        st.write("🔍 **Debug Info:**")
        st.write(f"- Agent type: {type(agent).__name__}")
        st.write(f"- Agent name: {getattr(agent, 'name', 'Unknown')}")
        
        # Check for sub-agents
        if hasattr(agent, 'agents') and agent.agents:
            st.write(f"- Sub-agents found: {len(agent.agents)}")
            for i, sub_agent in enumerate(agent.agents):
                if sub_agent:
                    st.write(f"  - {i}: {getattr(sub_agent, 'name', 'Unknown')} ({type(sub_agent).__name__})")
                    # Store sub-agents for direct access
                    if not hasattr(st.session_state, 'sub_agents'):
                        st.session_state.sub_agents = {}
                    st.session_state.sub_agents[sub_agent.name] = sub_agent
        else:
            st.write("- No sub-agents found")
        
        # Set up response callback
        def handle_response(message, agent_name=None):
            st.write(f"🔍 **Response Debug:** Agent={agent_name}, Message type={type(message)}")
            if hasattr(message, 'content') and message.content:
                # Clean response content
                content = re.sub(r'<think>.*?</think>', '', message.content, flags=re.DOTALL).strip()
                if content:
                    # Update active agent
                    if agent_name:
                        st.session_state.active_agent = agent_name
                        st.write(f"🔍 **Active agent updated to:** {agent_name}")
                    
                    # Store response
                    st.session_state.messages.append({
                        "role": "assistant",
                        "content": content,
                        "agent": agent_name or "Abi",
                        "timestamp": datetime.now()
                    })
        
        agent.on_ai_message(handle_response)
        st.session_state.agent = agent
        return agent
        
    except Exception as e:
        st.error(f"Agent initialization failed: {e}")
        import traceback
        st.error(f"Traceback: {traceback.format_exc()}")
        return None

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
        if hasattr(agent, '_state') and hasattr(agent._state, 'set_current_active_agent'):
            agent._state.set_current_active_agent(st.session_state.active_agent)
            st.write(f"🔍 **Set agent state to:** {st.session_state.active_agent}")
        else:
            st.write("🔍 **Warning:** Agent has no _state or set_current_active_agent method")
            
        # Check agent state structure
        if hasattr(agent, '_state'):
            st.write(f"🔍 **Agent state type:** {type(agent._state)}")
            if hasattr(agent._state, 'current_active_agent'):
                st.write(f"🔍 **Current active agent in state:** {agent._state.current_active_agent}")
        
        # Invoke agent (ABI will handle routing based on active agent state)
        st.write("🔍 **Invoking ABI agent with orchestration**")
        agent.invoke(user_input)
        
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