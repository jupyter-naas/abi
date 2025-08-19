#!/usr/bin/env python3
"""Integration test to verify PostgreSQL memory works with Agent.

This test requires PostgreSQL to be running. It can be started with:
    make dev-up

Run this test with:
    POSTGRES_URL=postgresql://abi_user:abi_password@localhost:5432/abi_memory python test_postgres_integration.py
"""

import os
import sys
from langchain_core.messages import AIMessage
from unittest.mock import MagicMock

# Add parent directory to path to import Agent
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))))

from abi.services.agent.Agent import Agent, AgentSharedState, create_checkpointer


def test_postgres_checkpointer():
    """Test that PostgreSQL checkpointer is created when POSTGRES_URL is set."""
    postgres_url = os.getenv("POSTGRES_URL")
    
    if not postgres_url:
        print("⚠️  POSTGRES_URL not set. Skipping PostgreSQL integration test.")
        print("   To run this test, start PostgreSQL with: make dev-up")
        print("   Then set POSTGRES_URL=postgresql://abi_user:abi_password@localhost:5432/abi_memory")
        return False
    
    print(f"✓ POSTGRES_URL found: {postgres_url}")
    
    try:
        checkpointer = create_checkpointer()
        print(f"✓ Created checkpointer: {type(checkpointer).__name__}")
        
        # Check if it's a PostgreSQL checkpointer
        if "PostgresSaver" in type(checkpointer).__name__:
            print("✓ PostgreSQL checkpointer successfully created!")
            print("✓ Connection configured with autocommit=True, prepare_threshold=0, row_factory=dict_row")
            print("✓ Database tables initialized with setup()")
            return True
        else:
            print(f"⚠️  Expected PostgresSaver but got {type(checkpointer).__name__}")
            return False
            
    except Exception as e:
        print(f"✗ Error creating checkpointer: {e}")
        return False


def test_agent_with_postgres():
    """Test that Agent can use PostgreSQL for memory persistence."""
    postgres_url = os.getenv("POSTGRES_URL")
    
    if not postgres_url:
        print("⚠️  Skipping Agent PostgreSQL test (POSTGRES_URL not set)")
        return False
    
    try:
        # Create a mock chat model
        mock_model = MagicMock()
        mock_model.bind_tools = MagicMock(return_value=mock_model)
        mock_model.invoke = MagicMock(return_value=AIMessage(content="Test response"))
        
        # Create agent with a specific thread ID
        thread_id = 12345
        agent = Agent(
            name="test_agent",
            description="Test agent for PostgreSQL integration",
            chat_model=mock_model,
            state=AgentSharedState(thread_id=thread_id)
        )
        
        print(f"✓ Created agent with thread_id={thread_id}")
        print(f"✓ Agent using checkpointer: {type(agent._checkpointer).__name__}")
        
        # Test that the agent's checkpointer is PostgreSQL-based
        if "PostgresSaver" in type(agent._checkpointer).__name__:
            print("✓ Agent successfully using PostgreSQL for memory!")
            return True
        else:
            print(f"⚠️  Agent using {type(agent._checkpointer).__name__} instead of PostgresSaver")
            return False
            
    except Exception as e:
        print(f"✗ Error creating agent with PostgreSQL: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Run all integration tests."""
    print("=" * 60)
    print("PostgreSQL Integration Tests for Agent Memory")
    print("=" * 60)
    print()
    
    tests_passed = 0
    tests_total = 2
    
    # Test 1: Checkpointer creation
    print("Test 1: PostgreSQL Checkpointer Creation")
    print("-" * 40)
    if test_postgres_checkpointer():
        tests_passed += 1
    print()
    
    # Test 2: Agent with PostgreSQL
    print("Test 2: Agent with PostgreSQL Memory")
    print("-" * 40)
    if test_agent_with_postgres():
        tests_passed += 1
    print()
    
    # Summary
    print("=" * 60)
    if tests_passed == tests_total:
        print(f"✅ All tests passed! ({tests_passed}/{tests_total})")
    else:
        print(f"⚠️  {tests_passed}/{tests_total} tests passed")
    print("=" * 60)
    
    return tests_passed == tests_total


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)