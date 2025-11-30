#!/usr/bin/env python3
"""
Test the chat interface using Streamlit's app testing framework
Located in src/core/user-interfaces/chat-mode/ as it should be
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from streamlit.testing.v1 import AppTest

# Load environment first
load_dotenv()

# Environment setup - go to project root (abi directory)
# From chat-mode: go up 4 levels to reach /Users/jrvmac/abi
project_root = Path(__file__).parent.parent.parent.parent
sys.path.insert(0, str(project_root))
os.chdir(str(project_root))

# Set environment for development
os.environ["ENV"] = "dev"
os.environ["LOG_LEVEL"] = "ERROR"


def test_chat_interface_initialization():
    """Test that the chat interface initializes properly"""
    print("🔍 Testing chat interface initialization...")

    # Initialize the app test from the chat interface file (in same directory)
    at = AppTest.from_file("chat_interface.py")

    # Run the app with extended timeout
    at.run(timeout=30)

    # Check if there are any exceptions
    if at.exception:
        print(f"❌ Exception occurred: {at.exception}")
        return False

    # Check if the title is rendered
    if at.title:
        print(f"✅ Title found: {at.title[0].value}")
    else:
        print("❌ No title found")

    # Check for success/error messages
    if at.success:
        for success in at.success:
            print(f"✅ Success message: {success.value}")

    if at.error:
        for error in at.error:
            print(f"❌ Error message: {error.value}")

    # Check for debug output in text elements
    if hasattr(at, "text"):
        for text in at.text:
            if "Debug:" in str(text.value):
                print(f"🔍 Debug text: {text.value}")

    print(f"🔍 App state: Exception={at.exception is not None}")
    return at.exception is None


def test_module_loading_step_by_step():
    """Test module loading with detailed step-by-step output"""
    print("\n🔍 Testing module loading step by step...")

    # Create a detailed test app
    detailed_test_app = """
import streamlit as st
import os
import sys
from pathlib import Path

st.set_page_config(page_title="ABI Module Loading Test", page_icon="🔍", layout="wide")
st.title("🔍 ABI Module Loading Test")

try:
    st.write("**Step 1:** Testing basic imports...")
    from naas_abi import modules
    st.success("✅ Successfully imported modules")
    
    st.write("**Step 2:** Triggering module loading...")
    loaded_modules = modules  # This triggers the LazyLoader
    st.success(f"✅ Successfully loaded {len(loaded_modules)} modules")
    
    st.write("**Step 3:** Analyzing loaded modules...")
    abi_agent = None
    module_details = []
    
    for module in loaded_modules:
        agent_count = len(module.agents)
        module_info = f"📦 {module.module_import_path}: {agent_count} agents"
        module_details.append(module_info)
        st.write(module_info)
        
        for agent in module.agents:
            agent_name = agent.__class__.__name__
            st.write(f"   - {agent_name}")
            if agent_name == "AbiAgent":
                abi_agent = agent
                st.success(f"🎯 Found AbiAgent: {type(agent)}")
    
    if abi_agent:
        st.success("🎉 AbiAgent loaded successfully!")
        st.write(f"**Agent Details:**")
        st.write(f"- Name: {getattr(abi_agent, 'name', 'No name')}")
        st.write(f"- Type: {type(abi_agent)}")
        st.write(f"- Class: {abi_agent.__class__.__name__}")
    else:
        st.error("❌ AbiAgent not found in any module")
        st.write("**Available modules:**")
        for detail in module_details:
            st.write(detail)
        
except Exception as e:
    st.error(f"❌ Error during module loading: {str(e)}")
    import traceback
    st.code(traceback.format_exc())
"""

    at = AppTest.from_string(detailed_test_app)
    at.run(timeout=60)  # Longer timeout for detailed analysis

    # Print all outputs
    print("📝 Detailed test outputs:")

    if at.success:
        for success in at.success:
            print(f"✅ {success.value}")

    if at.error:
        for error in at.error:
            print(f"❌ {error.value}")

    if hasattr(at, "text"):
        for text in at.text:
            print(f"📝 {text.value}")

    if hasattr(at, "code"):
        for code in at.code:
            print(f"💻 Code block: {code.value}")

    return at.exception is None


def test_agent_invocation():
    """Test if we can actually invoke the agent once loaded"""
    print("\n🔍 Testing agent invocation...")

    # This will only run if we successfully load the agent
    invocation_test_app = """
import streamlit as st

st.title("🤖 Agent Invocation Test")

try:
    # Try to load agent using the same method as chat interface
    from naas_abi import modules
    loaded_modules = modules
    
    abi_agent = None
    for module in loaded_modules:
        for agent in module.agents:
            if agent.__class__.__name__ == "AbiAgent":
                abi_agent = agent
                break
        if abi_agent:
            break
    
    if abi_agent:
        st.success("✅ AbiAgent loaded for invocation test")
        
        # Test a simple invocation
        st.write("Testing simple invocation...")
        response = abi_agent.invoke("Hello, what is your name?")
        
        if response:
            st.success("✅ Agent responded successfully")
            st.write(f"Response type: {type(response)}")
        else:
            st.warning("⚠️ Agent returned no response")
    else:
        st.error("❌ Cannot test invocation - AbiAgent not loaded")
        
except Exception as e:
    st.error(f"❌ Invocation test failed: {str(e)}")
    import traceback
    st.code(traceback.format_exc())
"""

    at = AppTest.from_string(invocation_test_app)
    at.run(timeout=60)

    # Print results
    if at.success:
        for success in at.success:
            print(f"✅ {success.value}")

    if at.error:
        for error in at.error:
            print(f"❌ {error.value}")

    if at.warning:
        for warning in at.warning:
            print(f"⚠️ {warning.value}")

    return True


if __name__ == "__main__":
    print("🚀 Starting comprehensive chat interface testing...")
    print(f"📍 Running from: {Path(__file__).parent}")
    print(f"📁 Project root: {Path(__file__).parent.parent.parent.parent}")

    try:
        # Test 1: Basic initialization
        success = test_chat_interface_initialization()

        if success:
            print("\n✅ Basic initialization successful")
        else:
            print("\n❌ Basic initialization failed")

        # Test 2: Detailed module loading
        test_module_loading_step_by_step()

        # Test 3: Agent invocation (if possible)
        test_agent_invocation()

    except Exception as e:
        print(f"❌ Test suite failed with exception: {e}")
        import traceback

        traceback.print_exc()
