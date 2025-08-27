"""
ABI Chat Interface - API-based version
Clean, minimal chat interface using the ABI API instead of direct module loading
"""

import streamlit as st
import requests
import os
import re
from datetime import datetime
from pathlib import Path

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Page config
st.set_page_config(
    page_title="ABI Chat (API)", 
    page_icon="🤖", 
    layout="centered"
)

# Configuration
ABI_API_BASE = os.getenv("ABI_API_BASE", "http://localhost:9879")
ABI_API_KEY = os.getenv("ABI_API_KEY", "***REMOVED***")

# Session state initialization
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'thread_id' not in st.session_state:
    st.session_state.thread_id = 1
if 'active_agent' not in st.session_state:
    st.session_state.active_agent = "abi"

# Agent name mapping for @mentions
AGENT_MAPPING = {
    "abi": "abi", "claude": "claude", "gemini": "gemini", 
    "mistral": "mistral", "chatgpt": "chatgpt", "grok": "grok",
    "llama": "llama", "perplexity": "perplexity", "qwen": "qwen",
    "deepseek": "deepseek"
}

def call_abi_api(agent_name: str, prompt: str, thread_id: int = 1) -> dict:
    """Call the ABI API for agent completion"""
    try:
        headers = {
            "Authorization": f"Bearer {ABI_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "ABI-Streamlit-Chat/1.0"
        }
        
        data = {
            "prompt": prompt,
            "thread_id": str(thread_id)  # API expects string
        }
        
        # Map agent names to API endpoints (capitalize first letter)
        api_agent_name = agent_name.capitalize()
        url = f"{ABI_API_BASE}/agents/{api_agent_name}/completion"
        
        response = requests.post(url, json=data, headers=headers, timeout=30)
        
        if response.status_code == 200:
            return {"success": True, "content": response.text.strip('"')}
        elif response.status_code == 401:
            return {"success": False, "error": "🔒 Authentication failed. Check your ABI_API_KEY."}
        elif response.status_code == 404:
            return {"success": False, "error": f"❓ Agent '{agent_name}' not found."}
        else:
            return {"success": False, "error": f"❌ HTTP {response.status_code}: {response.text}"}
            
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": f"❌ Cannot connect to ABI API at {ABI_API_BASE}. Is the API running?"}
    except requests.exceptions.Timeout:
        return {"success": False, "error": f"⏱️ Timeout calling {agent_name} agent."}
    except Exception as e:
        return {"success": False, "error": f"❌ Error: {str(e)}"}

def process_user_input(user_input: str) -> tuple[str, str]:
    """Process user input and handle @mentions"""
    # Check for @mentions
    mention_match = re.search(r'@(\w+)', user_input.lower())
    agent_name = st.session_state.active_agent
    
    if mention_match:
        mentioned_agent = mention_match.group(1)
        if mentioned_agent in AGENT_MAPPING:
            # Update active agent
            agent_name = AGENT_MAPPING[mentioned_agent]
            st.session_state.active_agent = agent_name
            
            # Clean input (remove @mention)
            user_input_clean = re.sub(r'@\w+\s*', '', user_input).strip()
            if user_input_clean:
                user_input = user_input_clean
            else:
                user_input = f"Hello, I want to talk to {mentioned_agent}"
    
    return agent_name, user_input

def send_message(user_input: str):
    """Send message to ABI API and handle response"""
    # Process input and determine agent
    agent_name, processed_input = process_user_input(user_input)
    
    # Add user message to chat
    st.session_state.messages.append({
        "role": "user",
        "content": user_input,
        "timestamp": datetime.now()
    })
    
    # Call API
    with st.spinner(f"Thinking... (via {agent_name})"):
        result = call_abi_api(agent_name, processed_input, st.session_state.thread_id)
    
    if result["success"]:
        # Clean response content (remove thinking tags, etc.)
        content = re.sub(r'<think>.*?</think>', '', result["content"], flags=re.DOTALL).strip()
        
        # Add assistant response to chat
        st.session_state.messages.append({
            "role": "assistant",
            "content": content,
            "agent": agent_name,
            "timestamp": datetime.now()
        })
    else:
        # Add error message
        st.session_state.messages.append({
            "role": "assistant",
            "content": result["error"],
            "agent": "system",
            "timestamp": datetime.now()
        })

# UI Layout
st.title("🤖 ABI Chat (API)")
st.caption(f"Active Agent: **{st.session_state.active_agent.title()}** | Thread: {st.session_state.thread_id}")

# Sidebar controls
with st.sidebar:
    st.header("🎛️ Controls")
    
    # API Status
    st.subheader("API Status")
    try:
        health_response = requests.get(f"{ABI_API_BASE}/health", timeout=5)
        if health_response.status_code == 200:
            st.success("✅ API Connected")
        else:
            st.error("❌ API Error")
    except:
        st.error("❌ API Offline")
        st.write(f"Expected at: {ABI_API_BASE}")
        st.write("Start with: `uv run api`")
    
    # Chat controls
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()
    
    if st.button("🔄 New Thread"):
        st.session_state.thread_id += 1
        st.session_state.messages = []
        st.rerun()
    
    # Agent selection
    st.subheader("🤖 Available Agents")
    st.write("Use @mentions to switch:")
    for key, name in AGENT_MAPPING.items():
        emoji = "🎯" if name == st.session_state.active_agent else "🤖"
        st.write(f"{emoji} @{key} → {name.title()}")
    
    # Configuration
    st.subheader("⚙️ Configuration")
    st.write(f"**API Base:** {ABI_API_BASE}")
    st.write(f"**Thread ID:** {st.session_state.thread_id}")

# Display messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            agent_name = msg.get('agent', 'unknown')
            if agent_name == "system":
                st.error(msg['content'])
            else:
                st.write(f"**{agent_name.title()}:** {msg['content']}")
        else:
            st.write(msg['content'])

# Chat input
if prompt := st.chat_input("Message ABI..."):
    send_message(prompt)
    st.rerun()

# Footer
st.markdown("---")
st.markdown("**ABI Chat Interface** - API Version | Powered by NaasAI")
st.markdown("💡 *Tip: Use @agent to switch agents (e.g., @claude, @gemini)*")
