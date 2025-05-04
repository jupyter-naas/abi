import streamlit as st
from openai import OpenAI
import json
import os
from pathlib import Path

# Constants
DB_FILE = Path(__file__).parent / 'db.json'
APP_TITLE = "ABI - Advanced Terminal Assistant"
CSS_FILE = Path(__file__).parent / 'style.css'

# Function to load and apply custom CSS
def load_css():
    if CSS_FILE.exists():
        with open(CSS_FILE) as f:
            st.markdown(f'<style>{f.read()}</style>', unsafe_allow_html=True)

# Apply the CSS
load_css()

# Function to create OpenAI client
def create_openai_client(api_key):
    """Create an OpenAI client with the given API key"""
    try:
        # Check if the key starts with "sk-" (standard OpenAI key format)
        if api_key.startswith('sk-'):
            return OpenAI(api_key=api_key)
        # For Azure OpenAI or other formats, we might need different initialization
        else:
            st.warning("API key doesn't match expected format. If using Azure OpenAI, additional configuration may be needed.")
            return OpenAI(api_key=api_key)
    except Exception as e:
        st.error(f"Error creating OpenAI client: {str(e)}")
        return None

# Simple mock agent for now, we'll connect it to the real agent later
class SimpleAgent:
    def __init__(self, api_key=None):
        self.api_key = api_key
        self.openai_client = create_openai_client(api_key)
        
    def invoke(self, prompt):
        """Process a prompt through OpenAI"""
        if not self.openai_client:
            return "Error: Could not initialize OpenAI client. Please check your API key."
            
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.7,
            )
            return response.choices[0].message.content
        except Exception as e:
            return f"Error: {str(e)}\n\nThis may be due to an invalid API key or configuration issue."
    
    def on_tool_usage(self, callback):
        # Mock method for compatibility
        pass
        
    def on_tool_response(self, callback):
        # Mock method for compatibility
        pass


def initialize_db():
    """Initialize the database file if it doesn't exist"""
    if not DB_FILE.exists():
        with open(DB_FILE, 'w') as file:
            db = {
                'openai_api_keys': [],
                'chat_history': []
            }
            json.dump(db, file)
    else:
        with open(DB_FILE, 'r') as file:
            db = json.load(file)
    return db


def save_to_db(db):
    """Save the current database state to the file"""
    with open(DB_FILE, 'w') as file:
        json.dump(db, file)


def login_page():
    """Display the login page and handle API key entry"""
    st.title(APP_TITLE)
    
    # Display logo or welcome message
    st.markdown("""
    <div style='text-align: center; margin-bottom: 30px;'>
        <h3>Welcome to ABI Streamlit Chat</h3>
        <p>Please log in with your OpenAI API key to continue</p>
    </div>
    """, unsafe_allow_html=True)
    
    # Load the database
    db = initialize_db()
    
    # Create columns for layout
    col1, col2 = st.columns([1, 1])
    
    with col1:
        # Display existing API keys dropdown
        selected_key = st.selectbox(
            label="Existing OpenAI API Keys", 
            options=db['openai_api_keys'],
            index=0 if db['openai_api_keys'] else None
        )
    
    with col2:
        # Input for new API key
        new_key = st.text_input(
            label="New OpenAI API Key", 
            type="password",
            help="Enter your OpenAI API key (starts with 'sk-')"
        )
    
    # Login button
    login = st.button("Login")
    
    if login:
        if new_key:
            # Test the API key before saving
            test_client = create_openai_client(new_key)
            if test_client:
                try:
                    # Make a simple API call to validate the key
                    test_client.models.list()
                    # If successful, save the key
                    if new_key not in db['openai_api_keys']:
                        db['openai_api_keys'].append(new_key)
                        save_to_db(db)
                    st.success("Key validated and saved successfully.")
                    st.session_state['openai_api_key'] = new_key
                    st.rerun()
                except Exception as e:
                    st.error(f"Invalid API key: {str(e)}")
            else:
                st.error("Could not initialize OpenAI client with the provided key.")
        else:
            if selected_key:
                st.success(f"Logged in with existing key")
                st.session_state['openai_api_key'] = selected_key
                st.rerun()
            else:
                st.error("API Key is required to login")
    
    # Add helpful information
    st.markdown("""
    <div style='margin-top: 50px; padding: 20px; background-color: #f8f9fa; border-radius: 10px;'>
        <h4>About OpenAI API Keys</h4>
        <p>You can get an API key from <a href="https://platform.openai.com/api-keys" target="_blank">OpenAI's website</a>.</p>
        <p>OpenAI API keys typically start with 'sk-' followed by a string of characters.</p>
        <p>Your API key is stored locally on your device and is never sent to any server except OpenAI.</p>
    </div>
    """, unsafe_allow_html=True)


def initialize_agent():
    """Initialize the agent with the OpenAI API key"""
    if 'agent' not in st.session_state:
        # Initialize a simple agent (we'll connect to ABI agent later)
        try:
            st.session_state.agent = SimpleAgent(api_key=st.session_state.openai_api_key)
            if not st.session_state.agent.openai_client:
                st.error("Could not initialize OpenAI client. Please check your API key.")
                return None
        except Exception as e:
            st.error(f"Error initializing agent: {e}")
            return None
    return st.session_state.agent


def main():
    """Main application logic after successful login"""
    st.title(APP_TITLE)
    
    # Initialize OpenAI client
    client = create_openai_client(st.session_state.openai_api_key)
    if not client:
        st.error("Could not initialize OpenAI client. Please check your API key.")
        # Add a logout button to allow user to try again
        if st.button('Logout'):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        return
    
    # Initialize agent if needed
    agent = initialize_agent()
    if not agent:
        st.error("Could not initialize agent. Please check your API key.")
        # Add a logout button to allow user to try again
        if st.button('Logout'):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        return
    
    # List of models
    models = ["gpt-4o-mini", "gpt-4o", "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo"]
    
    # Sidebar configuration
    with st.sidebar:
        st.title("Settings")
        
        # Model selection
        st.session_state["openai_model"] = st.selectbox(
            "Select OpenAI model", 
            models, 
            index=0
        )
        
        # Toggle between agent mode and direct API mode
        st.session_state["use_agent"] = st.checkbox(
            "Use Agent", 
            value=st.session_state.get("use_agent", True),
            help="Toggle between using the Agent and direct OpenAI API calls"
        )
        
        # Add a "Clear Chat" button
        if st.button('Clear Chat'):
            # Clear chat history in db.json
            db = initialize_db()
            db['chat_history'] = []
            save_to_db(db)
            # Clear chat messages in session state
            st.session_state.messages = []
            st.rerun()
        
        # Add logout button
        if st.button('Logout'):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()
        
        # Display the current mode
        st.info(f"Current mode: {'Agent' if st.session_state.get('use_agent', True) else 'Direct API'}")
    
    # Load chat history from db.json
    db = initialize_db()
    if 'messages' not in st.session_state:
        st.session_state.messages = db.get('chat_history', [])
    
    # Display chat messages from history
    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])
    
    # Accept user input
    if prompt := st.chat_input("What can I help you with?"):
        # Add user message to chat history
        st.session_state.messages.append({"role": "user", "content": prompt})
        
        # Display user message
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Display assistant response
        with st.chat_message("assistant"):
            try:
                if st.session_state.get("use_agent", True):
                    # Use the agent for processing
                    with st.spinner("Thinking..."):
                        response = agent.invoke(prompt)
                        st.markdown(response)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                else:
                    # Use direct OpenAI API call
                    try:
                        stream = client.chat.completions.create(
                            model=st.session_state["openai_model"],
                            messages=[
                                {"role": m["role"], "content": m["content"]}
                                for m in st.session_state.messages
                            ],
                            stream=True,
                        )
                        response = st.write_stream(stream)
                        st.session_state.messages.append({"role": "assistant", "content": response})
                    except Exception as e:
                        error_message = f"OpenAI API Error: {str(e)}"
                        st.error(error_message)
                        st.session_state.messages.append({"role": "assistant", "content": error_message})
            except Exception as e:
                error_msg = f"Error processing request: {str(e)}"
                st.error(error_msg)
                st.session_state.messages.append({"role": "assistant", "content": error_msg})
        
        # Store chat history to db.json
        db['chat_history'] = st.session_state.messages
        save_to_db(db)


if __name__ == '__main__':
    if 'openai_api_key' in st.session_state and st.session_state.openai_api_key:
        main()
    else:
        login_page() 