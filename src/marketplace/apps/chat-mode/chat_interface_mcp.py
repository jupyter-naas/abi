"""
ABI Chat Interface - MCP-based version
Ultra-clean chat interface using Model Context Protocol for agent communication
"""

import streamlit as st
import asyncio
import httpx
import os
import re
from datetime import datetime
from typing import Dict, Any

# Load environment
from dotenv import load_dotenv
load_dotenv()

# Page config
st.set_page_config(
    page_title="ABI Chat (MCP)", 
    page_icon="🚀", 
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

# MCP Agent Functions - Clean function definitions
AVAILABLE_AGENTS = {
    "abi": {
        "name": "Abi Super Assistant", 
        "description": "AI Super Assistant and multi-agent orchestrator",
        "emoji": "🤖"
    },
    "claude": {
        "name": "Claude", 
        "description": "Advanced reasoning and analysis",
        "emoji": "🧠"
    },
    "chatgpt": {
        "name": "ChatGPT", 
        "description": "Real-time web search and general intelligence",
        "emoji": "💬"
    },
    "gemini": {
        "name": "Gemini", 
        "description": "Multimodal and creative tasks",
        "emoji": "✨"
    },
    "mistral": {
        "name": "Mistral", 
        "description": "Code generation and mathematics",
        "emoji": "⚡"
    },
    "grok": {
        "name": "Grok", 
        "description": "Truth-seeking and current events",
        "emoji": "🔍"
    },
    "perplexity": {
        "name": "Perplexity", 
        "description": "Real-time research and web intelligence",
        "emoji": "🌐"
    }
}

async def call_agent_mcp(agent_name: str, prompt: str, thread_id: int = 1) -> Dict[str, Any]:
    """Call ABI agent via MCP-style HTTP interface"""
    try:
        headers = {
            "Authorization": f"Bearer {ABI_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "ABI-MCP-Chat/1.0"
        }
        
        data = {
            "prompt": prompt,
            "thread_id": str(thread_id)  # API expects string
        }
        
        # Map agent names to API endpoints (capitalize first letter)
        api_agent_name = agent_name.capitalize()
        url = f"{ABI_API_BASE}/agents/{api_agent_name}/completion"
        
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(url, json=data, headers=headers)
            
            if response.status_code == 200:
                content = response.text.strip('"')
                # Clean response (remove thinking tags)
                content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL).strip()
                return {"success": True, "content": content, "agent": agent_name}
            else:
                error_msg = f"HTTP {response.status_code}: {response.text}"
                return {"success": False, "error": error_msg}
                
    except httpx.ConnectError:
        return {"success": False, "error": f"❌ Cannot connect to ABI API at {ABI_API_BASE}"}
    except httpx.TimeoutException:
        return {"success": False, "error": f"⏱️ Request timeout for {agent_name}"}
    except Exception as e:
        return {"success": False, "error": f"❌ Unexpected error: {str(e)}"}

def process_mention(user_input: str) -> tuple[str, str]:
    """Process @mentions for agent switching"""
    mention_match = re.search(r'@(\w+)', user_input.lower())
    agent_name = st.session_state.active_agent
    
    if mention_match:
        mentioned_agent = mention_match.group(1)
        if mentioned_agent in AVAILABLE_AGENTS:
            agent_name = mentioned_agent
            st.session_state.active_agent = agent_name
            # Remove @mention from input
            user_input = re.sub(r'@\w+\s*', '', user_input).strip()
            if not user_input:
                user_input = f"Hello! I'd like to work with {mentioned_agent}."
    
    return agent_name, user_input

def run_async(coro):
    """Helper to run async functions in Streamlit"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    return loop.run_until_complete(coro)

# UI Layout
st.title("🚀 ABI Chat (MCP)")

# Status bar
col1, col2, col3 = st.columns([2, 1, 1])
with col1:
    agent_info = AVAILABLE_AGENTS.get(st.session_state.active_agent, {"name": "Unknown", "emoji": "❓"})
    st.write(f"**Active:** {agent_info['emoji']} {agent_info['name']}")
with col2:
    st.write(f"**Thread:** {st.session_state.thread_id}")
with col3:
    # API Health Check
    try:
        health_check = run_async(httpx.AsyncClient().get(f"{ABI_API_BASE}/health", timeout=2))
        if health_check.status_code == 200:
            st.write("🟢 **API Online**")
        else:
            st.write("🟡 **API Issues**")
    except:
        st.write("🔴 **API Offline**")

# Sidebar
with st.sidebar:
    st.header("🎛️ MCP Controls")
    
    # Agent Selection
    st.subheader("🤖 Available Agents")
    for agent_id, agent_info in AVAILABLE_AGENTS.items():
        is_active = agent_id == st.session_state.active_agent
        status = "🎯" if is_active else "⚪"
        if st.button(f"{status} {agent_info['emoji']} {agent_info['name']}", 
                    key=f"agent_{agent_id}",
                    disabled=is_active):
            st.session_state.active_agent = agent_id
            st.rerun()
        
        if is_active:
            st.caption(f"📝 {agent_info['description']}")
    
    st.divider()
    
    # Chat Controls
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()
    
    if st.button("🔄 New Thread"):
        st.session_state.thread_id += 1
        st.session_state.messages = []
        st.rerun()
    
    st.divider()
    
    # MCP Info
    st.subheader("ℹ️ MCP Mode")
    st.write("**Protocol:** Model Context Protocol")
    st.write(f"**Endpoint:** {ABI_API_BASE}")
    st.write("**Features:**")
    st.write("• Agent switching via @mentions")
    st.write("• Thread-based conversations")
    st.write("• Async HTTP communication")

# Display chat messages
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        if msg["role"] == "assistant":
            agent_name = msg.get('agent', 'system')
            if agent_name == "system":
                st.error(msg['content'])
            else:
                agent_info = AVAILABLE_AGENTS.get(agent_name, {"name": agent_name, "emoji": "🤖"})
                st.write(f"**{agent_info['emoji']} {agent_info['name']}:** {msg['content']}")
        else:
            st.write(msg['content'])

# Chat input
if prompt := st.chat_input("Message ABI via MCP..."):
    # Add user message
    st.session_state.messages.append({
        "role": "user",
        "content": prompt,
        "timestamp": datetime.now()
    })
    
    # Process mention and get agent
    agent_name, processed_prompt = process_mention(prompt)
    
    # Show user message immediately
    with st.chat_message("user"):
        st.write(prompt)
    
    # Call agent via MCP
    with st.chat_message("assistant"):
        with st.spinner(f"Calling {AVAILABLE_AGENTS[agent_name]['name']} via MCP..."):
            result = run_async(call_agent_mcp(agent_name, processed_prompt, st.session_state.thread_id))
        
        if result["success"]:
            agent_info = AVAILABLE_AGENTS.get(agent_name, {"name": agent_name, "emoji": "🤖"})
            st.write(f"**{agent_info['emoji']} {agent_info['name']}:** {result['content']}")
            
            # Add to message history
            st.session_state.messages.append({
                "role": "assistant",
                "content": result['content'],
                "agent": agent_name,
                "timestamp": datetime.now()
            })
        else:
            st.error(result['error'])
            st.session_state.messages.append({
                "role": "assistant",
                "content": result['error'],
                "agent": "system",
                "timestamp": datetime.now()
            })
    
    st.rerun()

# Footer
st.markdown("---")
st.markdown("**🚀 ABI MCP Chat** | Model Context Protocol Interface | Powered by NaasAI")
st.markdown("💡 *Use @agent to switch (e.g., @claude, @gemini) or click agent buttons in sidebar*")
