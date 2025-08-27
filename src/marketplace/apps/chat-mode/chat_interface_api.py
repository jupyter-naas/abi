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
    page_icon="💬", 
    layout="centered"
)

# Apple-style CSS for chat messages
st.markdown("""
<style>
    /* Chat message styling */
    .chat-label {
        font-weight: 600;
        font-size: 0.9rem;
        color: #1d1d1f;
        margin-bottom: 4px;
        letter-spacing: -0.01em;
    }
    
    .chat-content {
        font-weight: 400;
        font-size: 1rem;
        color: #000000;
        line-height: 1.4;
        margin-top: 0;
        margin-bottom: 0;
    }
    
    /* User message styling */
    .user-label {
        color: #86868b;
        font-weight: 600;
    }
    
    /* Assistant message styling */
    .assistant-label {
        color: #86868b;
        font-weight: 600;
    }
    
    /* Reduce spacing in chat messages */
    .stChatMessage > div {
        gap: 0.5rem !important;
    }
    
    /* Streamlit chat message content spacing */
    .stChatMessage [data-testid="stMarkdownContainer"] p {
        margin-bottom: 0.25rem !important;
        margin-top: 0 !important;
    }
    
    .stChatMessage [data-testid="stMarkdownContainer"]:last-child p {
        margin-bottom: 0 !important;
    }
</style>
""", unsafe_allow_html=True)

# Configuration
ABI_API_BASE = os.getenv("ABI_API_BASE", "http://localhost:9879")
ABI_API_KEY = os.getenv("ABI_API_KEY")

# Check if API key is provided
if not ABI_API_KEY:
    st.error("❌ ABI_API_KEY environment variable is required")
    st.stop()

# Session state initialization
if 'messages' not in st.session_state:
    st.session_state.messages = []
if 'thread_id' not in st.session_state:
    st.session_state.thread_id = 1
if 'active_agent' not in st.session_state:
    st.session_state.active_agent = "Abi"

# Agent name mapping for @mentions (maps to actual API endpoint names)
AGENT_MAPPING = {
    "abi": "Abi", "claude": "Claude", "gemini": "Gemini", 
    "mistral": "Mistral", "chatgpt": "ChatGPT", "grok": "Grok",
    "llama": "Llama", "perplexity": "Perplexity", "qwen": "Qwen",
    "deepseek": "DeepSeek"
}

# Agent avatar URLs
AGENT_AVATARS = {
    "Abi": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi-demo/ontology_ABI.png",
    "Claude": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/claude.png",
    "Gemini": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/gemini.png",
    "Mistral": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/mistral.png",
    "ChatGPT": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/chatgpt.jpg",
    "Grok": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/grok.jpg",
    "Llama": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/llama.jpeg",
    "Perplexity": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/perplexity.png",
    "Qwen": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/qwen.jpg",
    "DeepSeek": "https://naasai-public.s3.eu-west-3.amazonaws.com/abi/assets/deepseek.png"
}

def check_api_status() -> bool:
    """Check if the ABI API is running"""
    try:
        response = requests.get(f"{ABI_API_BASE}/openapi.json", timeout=3)
        return response.status_code == 200
    except:
        return False

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
        
        # Map agent names to API endpoints using the mapping
        api_agent_name = AGENT_MAPPING.get(agent_name, agent_name.capitalize())
        url = f"{ABI_API_BASE}/agents/{api_agent_name}/completion"
        
        response = requests.post(url, json=data, headers=headers, timeout=120)
        
        if response.status_code == 200:
            return {"success": True, "content": response.text.strip('"')}
        elif response.status_code == 401:
            return {"success": False, "error": "🔒 Authentication failed. Check your ABI_API_KEY."}
        elif response.status_code == 404:
            return {"success": False, "error": f"❓ Agent '{agent_name}' not found."}
        else:
            return {"success": False, "error": f"❌ HTTP {response.status_code}: {response.text}"}
            
    except requests.exceptions.ConnectionError:
        return {"success": False, "error": f"❌ Cannot connect to ABI API at {ABI_API_BASE}.\n\n💡 **To fix this:**\n1. Open a terminal in the project root\n2. Run: `make api`\n3. Wait for the API to start, then try again"}
    except requests.exceptions.Timeout:
        return {"success": False, "error": f"⏱️ Timeout calling {agent_name} agent (>2 minutes). The agent might be processing a complex request. Try a simpler question or try again later."}
    except Exception as e:
        return {"success": False, "error": f"❌ Error: {str(e)}"}

def process_user_input(user_input: str) -> tuple[str, str]:
    """Process user input and handle @mentions and natural language agent switching"""
    agent_name = st.session_state.active_agent
    original_agent = agent_name
    
    # Check for @mentions first
    mention_match = re.search(r'@(\w+)', user_input.lower())
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
    else:
        # Check for natural language agent switching
        user_lower = user_input.lower()
        for agent_key, agent_value in AGENT_MAPPING.items():
            # Look for patterns like "talk to grok", "switch to claude", "use gemini", etc.
            patterns = [
                f"talk to {agent_key}",
                f"switch to {agent_key}",
                f"use {agent_key}",
                f"parlons a {agent_key}",  # French
                f"parler avec {agent_key}",  # French
                f"je veux parler a {agent_key}",  # French
            ]
            
            if any(pattern in user_lower for pattern in patterns):
                agent_name = agent_value
                st.session_state.active_agent = agent_name
                user_input = f"Hello, I'm now talking to {agent_key}"
                break
    
    # If agent changed, we'll need to rerun to update the sidebar
    if original_agent != agent_name:
        st.session_state.agent_switched = True
    
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
    
    # If agent switched, rerun to update sidebar
    if st.session_state.get('agent_switched', False):
        st.session_state.agent_switched = False
        st.rerun()

# UI Layout - minimal

# Sidebar with active agent and API status
with st.sidebar:
    st.write(f"**Active: {st.session_state.active_agent}**")
    
    # API Status
    if check_api_status():
        st.success("✅ API Online")
    else:
        st.error("❌ API Offline")
        st.info("💡 Run `make api` in terminal to start")
    
    # Clear chat button
    if st.button("🗑️ Clear Chat"):
        st.session_state.messages = []
        st.rerun()
    


# Display messages
for msg in st.session_state.messages:
    if msg["role"] == "assistant":
        agent_name = msg.get('agent', 'unknown')
        if agent_name == "system":
            with st.chat_message("assistant"):
                st.error(msg['content'])
        else:
            # Get avatar URL for the agent
            avatar_url = AGENT_AVATARS.get(agent_name, None)
            with st.chat_message("assistant", avatar=avatar_url):
                st.markdown(f'<div class="assistant-label">{agent_name}:</div>', unsafe_allow_html=True)
                st.write(msg["content"])
    else:
        # User message with default user avatar
        with st.chat_message("user"):
            st.markdown('<div class="user-label">You:</div>', unsafe_allow_html=True)
            st.write(msg["content"])

# Chat input
if prompt := st.chat_input("Message ABI..."):
    send_message(prompt)
    st.rerun()


