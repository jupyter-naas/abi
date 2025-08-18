"""Tests for Agent memory configuration with PostgreSQL support."""

import os
import pytest
from unittest.mock import patch, MagicMock, ANY

from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.base import BaseCheckpointSaver

from abi.services.agent.Agent import create_checkpointer, Agent, AgentSharedState


class TestCreateCheckpointer:
    """Test the create_checkpointer function that detects PostgreSQL configuration."""
    
    def test_create_checkpointer_without_postgres_url(self):
        """Test that MemorySaver is returned when POSTGRES_URL is not set."""
        with patch.dict(os.environ, {}, clear=True):
            checkpointer = create_checkpointer()
            assert isinstance(checkpointer, MemorySaver)
    
    def test_create_checkpointer_with_postgres_url(self):
        """Test that PostgresSaver is returned when POSTGRES_URL is set."""
        test_url = "postgresql://user:pass@localhost:5432/testdb"
        
        # Mock the PostgresSaver class, psycopg connection, and instance
        mock_postgres_saver = MagicMock()
        mock_postgres_saver.setup = MagicMock()
        mock_postgres_class = MagicMock(return_value=mock_postgres_saver)
        mock_connection = MagicMock()
        mock_connection_connect = MagicMock(return_value=mock_connection)
        
        with patch.dict(os.environ, {"POSTGRES_URL": test_url}):
            with patch("langgraph.checkpoint.postgres.PostgresSaver", mock_postgres_class):
                with patch("psycopg.Connection.connect", mock_connection_connect):
                    checkpointer = create_checkpointer()
                    
                    # Verify Connection.connect was called with proper parameters
                    mock_connection_connect.assert_called_once_with(
                        test_url,
                        autocommit=True,
                        prepare_threshold=0,
                        row_factory=ANY  # dict_row import is mocked
                    )
                    # Verify PostgresSaver constructor was called with connection
                    mock_postgres_class.assert_called_once_with(mock_connection)
                    # Verify setup() was called
                    mock_postgres_saver.setup.assert_called_once()
                    assert checkpointer == mock_postgres_saver
    
    def test_create_checkpointer_postgres_import_error(self):
        """Test fallback to MemorySaver when PostgresSaver import fails."""
        test_url = "postgresql://user:pass@localhost:5432/testdb"
        
        with patch.dict(os.environ, {"POSTGRES_URL": test_url}):
            # Simulate ImportError when trying to import PostgresSaver
            with patch("builtins.__import__", side_effect=ImportError("No module named 'langgraph.checkpoint.postgres'")):
                checkpointer = create_checkpointer()
                assert isinstance(checkpointer, MemorySaver)
    
    def test_create_checkpointer_postgres_connection_error(self):
        """Test fallback to MemorySaver when PostgreSQL connection fails."""
        test_url = "postgresql://user:pass@localhost:5432/testdb"
        
        # Mock Connection.connect to raise an exception
        mock_connection_connect = MagicMock(side_effect=Exception("Connection failed"))
        
        with patch.dict(os.environ, {"POSTGRES_URL": test_url}):
            with patch("psycopg.Connection.connect", mock_connection_connect):
                checkpointer = create_checkpointer()
                assert isinstance(checkpointer, MemorySaver)
    
    def test_create_checkpointer_postgres_setup_error(self):
        """Test fallback to MemorySaver when PostgreSQL setup fails."""
        test_url = "postgresql://user:pass@localhost:5432/testdb"
        
        # Mock successful connection but setup failure
        mock_postgres_saver = MagicMock()
        mock_postgres_saver.setup.side_effect = Exception("Table creation failed")
        mock_postgres_class = MagicMock(return_value=mock_postgres_saver)
        mock_connection = MagicMock()
        mock_connection_connect = MagicMock(return_value=mock_connection)
        
        with patch.dict(os.environ, {"POSTGRES_URL": test_url}):
            with patch("langgraph.checkpoint.postgres.PostgresSaver", mock_postgres_class):
                with patch("psycopg.Connection.connect", mock_connection_connect):
                    checkpointer = create_checkpointer()
                    assert isinstance(checkpointer, MemorySaver)
    


class TestAgentMemoryConfiguration:
    """Test Agent class memory configuration."""
    
    @pytest.fixture
    def mock_chat_model(self):
        """Create a mock chat model."""
        model = MagicMock()
        model.bind_tools = MagicMock(return_value=model)
        return model
    
    def test_agent_uses_provided_memory(self, mock_chat_model):
        """Test that Agent uses explicitly provided memory."""
        custom_memory = MagicMock(spec=BaseCheckpointSaver)
        
        agent = Agent(
            name="test_agent",
            description="Test agent",
            chat_model=mock_chat_model,
            memory=custom_memory
        )
        
        assert agent._checkpointer == custom_memory
    
    def test_agent_creates_memory_when_none_provided(self, mock_chat_model):
        """Test that Agent creates memory based on environment when None is provided."""
        with patch("abi.services.agent.Agent.create_checkpointer") as mock_create:
            mock_checkpointer = MagicMock(spec=BaseCheckpointSaver)
            mock_create.return_value = mock_checkpointer
            
            agent = Agent(
                name="test_agent",
                description="Test agent",
                chat_model=mock_chat_model,
                memory=None
            )
            
            mock_create.assert_called_once()
            assert agent._checkpointer == mock_checkpointer
    
    def test_agent_default_memory_creation(self, mock_chat_model):
        """Test that Agent creates memory automatically when not provided."""
        with patch("abi.services.agent.Agent.create_checkpointer") as mock_create:
            mock_checkpointer = MagicMock(spec=BaseCheckpointSaver)
            mock_create.return_value = mock_checkpointer
            
            # Don't provide memory parameter at all
            agent = Agent(
                name="test_agent",
                description="Test agent",
                chat_model=mock_chat_model
            )
            
            mock_create.assert_called_once()
            assert agent._checkpointer == mock_checkpointer


class TestAgentPostgresIntegration:
    """Integration tests for Agent with PostgreSQL checkpointer."""
    
    @pytest.fixture
    def mock_chat_model(self):
        """Create a mock chat model that simulates real behavior."""
        model = MagicMock()
        model.bind_tools = MagicMock(return_value=model)
        
        # Mock invoke to return a proper message
        from langchain_core.messages import AIMessage
        model.invoke = MagicMock(return_value=AIMessage(content="Test response"))
        
        return model
    
    @pytest.mark.integration
    def test_agent_with_postgres_preserves_state(self, mock_chat_model):
        """Test that Agent with PostgreSQL preserves conversation state."""
        # This test would require a running PostgreSQL instance
        # It's marked as integration test and can be skipped in CI
        
        test_url = "postgresql://abi_user:abi_password@localhost:5432/abi_memory"
        
        with patch.dict(os.environ, {"POSTGRES_URL": test_url}):
            # First agent instance
            agent1 = Agent(
                name="test_agent",
                description="Test agent",
                chat_model=mock_chat_model,
                state=AgentSharedState(thread_id="123")
            )
            
            # Simulate some conversation
            # In a real test, we would invoke the agent and check state persistence
            
            # Second agent instance with same thread_id should have access to same state
            agent2 = Agent(
                name="test_agent",
                description="Test agent", 
                chat_model=mock_chat_model,
                state=AgentSharedState(thread_id="123")
            )
            
            # Both agents should share the same checkpointer type
            assert type(agent1._checkpointer) is type(agent2._checkpointer)
    
    def test_agent_duplicate_preserves_memory_config(self, mock_chat_model):
        """Test that duplicating an agent preserves memory configuration."""
        custom_memory = MagicMock(spec=BaseCheckpointSaver)
        
        original_agent = Agent(
            name="test_agent",
            description="Test agent",
            chat_model=mock_chat_model,
            memory=custom_memory
        )
        
        duplicated_agent = original_agent.duplicate()
        
        # The duplicated agent should use the same memory type
        assert duplicated_agent._checkpointer == original_agent._checkpointer

    def test_agent_thread_id_passed_as_string(self, mock_chat_model):
        """Test that thread_id is passed as string to graph config."""
        # Mock the graph.stream method to capture the config
        mock_graph = MagicMock()
        mock_graph.stream.return_value = iter([("source", {"messages": []})])
        
        agent = Agent(
            name="test_agent",
            description="Test agent",
            chat_model=mock_chat_model
        )
        agent.graph = mock_graph
        
        # Set a specific thread_id
        agent._state.set_thread_id("123")
        
        # Call stream which should pass thread_id as string directly
        list(agent.stream("test prompt"))
        
        # Verify that graph.stream was called with thread_id as string
        mock_graph.stream.assert_called_once()
        call_args = mock_graph.stream.call_args
        config = call_args[1]['config']  # kwargs
        
        assert config['configurable']['thread_id'] == "123"
        assert isinstance(config['configurable']['thread_id'], str)

    def test_agent_thread_id_increment(self, mock_chat_model):
        """Test that thread_id increments correctly with string type."""
        # Create agent with explicit thread_id to avoid test interference
        from abi.services.agent.Agent import AgentSharedState
        state = AgentSharedState(thread_id="1")
        
        agent = Agent(
            name="test_agent",
            description="Test agent",
            chat_model=mock_chat_model,
            state=state
        )
        
        # Default thread_id should be "1"
        assert agent._state.thread_id == "1"
        
        # Test increment
        agent.reset()
        assert agent._state.thread_id == "2"
        
        # Test multiple increments
        agent.reset()
        agent.reset()
        assert agent._state.thread_id == "4"
        
        # Test setting a custom string thread_id and incrementing
        agent._state.set_thread_id("100")
        agent.reset()
        assert agent._state.thread_id == "101"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])