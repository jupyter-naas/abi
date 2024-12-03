import streamlit as st
import yaml
import os

def load_config():
    """Load configuration from config.yaml"""
    try:
        with open("config.yaml", "r") as file:
            return yaml.safe_load(file)
    except FileNotFoundError:
        return {"config": {}}

def save_config(config):
    """Save configuration to config.yaml"""
    with open("config.yaml", "w") as file:
        yaml.dump(config, file, default_flow_style=False)

def main():
    # Set page title
    st.title("ABI Admin")
    
    # Add a header
    st.header("Welcome to ABI Config Manager")
    
    # Load current configuration
    config = load_config()
    
    # Create form for configuration
    with st.form("config_form"):
        # Storage name input
        storage_name = st.text_input(
            "Storage Name",
            value=config.get("config", {}).get("storage_name", "")
        )
        
        # Workspace ID input
        workspace_id = st.text_input(
            "Workspace ID",
            value=config.get("config", {}).get("workspace_id", "")
        )
        
        # Workspace name input
        workspace_name = st.text_input(
            "Workspace Name",
            value=config.get("config", {}).get("workspace_name", "")
        )
        
        # Workspace description input
        workspace_description = st.text_area(
            "Workspace Description",
            value=config.get("config", {}).get("workspace_description", ""),
            height=100
        )
        
        # Submit button
        submitted = st.form_submit_button("Save Configuration")
        
        if submitted:
            # Update configuration
            new_config = {
                "config": {
                    "storage_name": storage_name,
                    "workspace_id": workspace_id,
                    "workspace_name": workspace_name,
                    "workspace_description": workspace_description
                }
            }
            
            # Save to file
            save_config(new_config)
            st.success("Configuration saved successfully!")
    
    # Display current configuration in sidebar
    st.sidebar.header("Documentation")
    st.sidebar.header("Current Configuration")
    st.sidebar.json(config)

    

if __name__ == "__main__":
    main()