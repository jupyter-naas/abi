"""
ABI Chat Interface - API-based version
Clean, minimal chat interface using the ABI API instead of direct module loading
"""

import streamlit as st
import requests
import os
import re
from datetime import datetime

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
        margin-bottom: 0px;
        display: block;
        line-height: 1.1;
    }
    
    /* Assistant message styling */
    .assistant-label {
        color: #86868b;
        font-weight: 600;
        margin-bottom: 0px;
        display: block;
        line-height: 1.1;
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
    
    /* Ensure consistent spacing for all chat message elements */
    .stChatMessage [data-testid="stMarkdownContainer"] {
        margin-bottom: 0.25rem !important;
    }
    
    .stChatMessage [data-testid="stMarkdownContainer"]:first-child {
        margin-bottom: 0.125rem !important;
    }
    
    /* Chat input styling - more aggressive selectors */
    [data-testid="stChatInput"] {
        border-radius: 8px !important;
        min-height: 80px !important;
    }
    
    [data-testid="stChatInput"] > div {
        border-radius: 8px !important;
        min-height: 80px !important;
    }
    
    [data-testid="stChatInput"] textarea {
        border-radius: 8px !important;
        min-height: 80px !important;
        height: 80px !important;
        resize: vertical !important;
    }
    
    /* Target all input elements in chat */
    .stChatInput * {
        border-radius: 8px !important;
    }
    
    /* Specific textarea targeting */
    textarea[data-testid="stChatInputTextArea"] {
        border-radius: 8px !important;
        min-height: 80px !important;
        height: 80px !important;
    }
    
    /* Reduce border radius on chat messages */
    .stChatMessage {
        border-radius: 8px !important;
    }
    
    .stChatMessage > div {
        border-radius: 8px !important;
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
if 'conversations' not in st.session_state:
    st.session_state.conversations = {}
if 'current_conversation_id' not in st.session_state:
    st.session_state.current_conversation_id = "default"
if 'conversation_counter' not in st.session_state:
    st.session_state.conversation_counter = 1

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

def get_postgres_connection():
    """Get PostgreSQL connection using the same config as agents"""
    postgres_url = os.getenv("POSTGRES_URL")
    if not postgres_url:
        return None
    
    try:
        import psycopg
        from psycopg.rows import dict_row
        conn = psycopg.Connection.connect(
            postgres_url,
            autocommit=True,
            prepare_threshold=0,
            row_factory=dict_row
        )
        return conn
    except Exception as e:
        st.error(f"Failed to connect to PostgreSQL: {e}")
        return None

def get_conversation_threads():
    """Get all conversation threads from PostgreSQL"""
    conn = get_postgres_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor() as cur:
            # Query the checkpoints table to get unique thread_ids with their latest checkpoint
            cur.execute("""
                SELECT DISTINCT 
                    thread_id,
                    MAX(checkpoint_id) as latest_checkpoint_id,
                    MAX(checkpoint_ns) as latest_ns
                FROM checkpoints 
                WHERE thread_id IS NOT NULL 
                GROUP BY thread_id 
                ORDER BY latest_ns DESC
                LIMIT 50
            """)
            threads = cur.fetchall()
            
            # Get conversation titles by looking at the first user message in each thread
            conversations = []
            for thread in threads:
                thread_id = thread['thread_id']
                
                # Get the first few checkpoints to find user messages
                cur.execute("""
                    SELECT checkpoint
                    FROM checkpoints 
                    WHERE thread_id = %s 
                    ORDER BY checkpoint_id ASC 
                    LIMIT 10
                """, (thread_id,))
                
                checkpoints = cur.fetchall()
                title = f"Thread {thread_id}"
                
                # Try to extract a meaningful title from the conversation
                for checkpoint in checkpoints:
                    try:
                        import json
                        data = json.loads(checkpoint['checkpoint']) if isinstance(checkpoint['checkpoint'], str) else checkpoint['checkpoint']
                        
                        # Look for messages in the checkpoint data
                        if 'channel_values' in data and 'messages' in data['channel_values']:
                            messages = data['channel_values']['messages']
                            for msg in messages:
                                if isinstance(msg, dict) and msg.get('type') == 'human':
                                    content = msg.get('content', '')
                                    if content and len(content.strip()) > 0:
                                        title = content[:40] + "..." if len(content) > 40 else content
                                        break
                            if title != f"Thread {thread_id}":
                                break
                    except Exception:
                        continue
                
                conversations.append({
                    'thread_id': thread_id,
                    'title': title,
                    'last_updated': thread['latest_ns']
                })
            
            return conversations
            
    except Exception as e:
        st.error(f"Error querying conversations: {e}")
        return []
    finally:
        conn.close()

def load_conversation_from_db(thread_id: str):
    """Load a conversation from PostgreSQL and switch to it"""
    st.session_state.thread_id = int(thread_id)
    st.session_state.current_conversation_id = thread_id
    
    # Load the actual conversation messages from PostgreSQL
    conn = get_postgres_connection()
    if not conn:
        st.error("Cannot connect to PostgreSQL to load conversation")
        return
    
    try:
        with conn.cursor() as cur:
            # Get all checkpoints for this thread in order
            cur.execute("""
                SELECT checkpoint, checkpoint_id
                FROM checkpoints 
                WHERE thread_id = %s 
                ORDER BY checkpoint_id ASC
            """, (thread_id,))
            
            checkpoints = cur.fetchall()
            messages = []
            
            # Extract messages from checkpoints
            for checkpoint_data in checkpoints:
                try:
                    import json
                    data = json.loads(checkpoint_data['checkpoint']) if isinstance(checkpoint_data['checkpoint'], str) else checkpoint_data['checkpoint']
                    
                    # Look for messages in the checkpoint data
                    if 'channel_values' in data and 'messages' in data['channel_values']:
                        checkpoint_messages = data['channel_values']['messages']
                        
                        for msg in checkpoint_messages:
                            if isinstance(msg, dict):
                                # Convert LangChain message format to our format
                                if msg.get('type') == 'human':
                                    messages.append({
                                        "role": "user",
                                        "content": msg.get('content', ''),
                                        "timestamp": datetime.now()
                                    })
                                elif msg.get('type') == 'ai':
                                    # Try to determine which agent responded
                                    agent_name = "Abi"  # Default
                                    content = msg.get('content', '')
                                    
                                    # Try to extract agent name from content or other fields
                                    if 'name' in msg:
                                        agent_name = msg['name']
                                    
                                    messages.append({
                                        "role": "assistant",
                                        "content": content,
                                        "agent": agent_name,
                                        "timestamp": datetime.now()
                                    })
                except Exception:
                    continue
            
            # Remove duplicates while preserving order
            seen = set()
            unique_messages = []
            for msg in messages:
                # Create a simple hash of the message
                msg_hash = f"{msg['role']}:{msg['content'][:50]}"
                if msg_hash not in seen:
                    seen.add(msg_hash)
                    unique_messages.append(msg)
            
            # Set the loaded messages
            st.session_state.messages = unique_messages
            
            if not unique_messages:
                st.session_state.messages = [{
                    "role": "assistant",
                    "content": f"Loaded conversation thread {thread_id}, but no messages found. You can continue the conversation from here.",
                    "agent": "system",
                    "timestamp": datetime.now()
                }]
                
    except Exception as e:
        st.error(f"Error loading conversation: {e}")
        st.session_state.messages = [{
            "role": "assistant",
            "content": f"Error loading conversation thread {thread_id}: {str(e)}",
            "agent": "system",
            "timestamp": datetime.now()
        }]
    finally:
        conn.close()

def create_new_conversation():
    """Create a new conversation with a new thread ID"""
    import random
    new_thread_id = random.randint(10000, 99999)
    st.session_state.thread_id = new_thread_id
    st.session_state.current_conversation_id = str(new_thread_id)
    st.session_state.messages = []
    st.session_state.active_agent = "Abi"

def check_api_status() -> bool:
    """Check if the ABI API is running"""
    try:
        response = requests.get(f"{ABI_API_BASE}/openapi.json", timeout=3)
        return response.status_code == 200
    except Exception:
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
    with st.spinner(f"{agent_name} is responding..."):
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

# Sidebar with active agent, API status, and conversation history
with st.sidebar:
    st.write(f"**Active: {st.session_state.active_agent}**")
    
    # API Status
    if check_api_status():
        st.success("✅ API Online")
    else:
        st.error("❌ API Offline")
        st.info("💡 Run `make api` in terminal to start")
    
    st.markdown("---")
    
    # Conversation Management
    col1, col2 = st.columns([2, 1])
    with col1:
        st.write("**Conversations**")
    with col2:
        if st.button("➕", help="New Chat"):
            create_new_conversation()
            st.rerun()
    
    # Display conversation list from PostgreSQL
    try:
        conversations = get_conversation_threads()
        if conversations:
            for conv in conversations:
                thread_id = str(conv['thread_id'])
                title = conv['title']
                is_current = thread_id == st.session_state.current_conversation_id
                
                # Highlight current conversation
                if is_current:
                    st.markdown(f"**🗨️ {title}**")
                else:
                    if st.button(f"💬 {title}", key=f"thread_{thread_id}"):
                        load_conversation_from_db(thread_id)
                        st.rerun()
        else:
            postgres_url = os.getenv("POSTGRES_URL")
            if postgres_url:
                st.write("*No conversations found*")
                st.caption("Start chatting to create conversations!")
            else:
                st.write("*PostgreSQL not configured*")
                st.caption("Set POSTGRES_URL for persistent conversations")
    except Exception as e:
        st.error(f"Error loading conversations: {e}")
        st.write("*Using session-only conversations*")
    
    st.markdown("---")
    
    # Clear current chat button
    if st.button("🗑️ Clear Current Chat"):
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
if prompt := st.chat_input("Type a message or @ an agent..."):
    send_message(prompt)
    st.rerun()


