# Chat Interface - Standard Operating Procedure

## Purpose
Clean, minimal chat interface for direct interaction with ABI agents.

## Architecture
- **Single file**: `chat_interface.py` (150 lines vs previous 391)
- **Clean separation**: UI logic, agent initialization, message handling
- **Proper error handling**: Graceful failures with clear feedback
- **Session management**: Persistent chat history and agent state

## Key Features

### Agent Integration
- Direct ABI agent creation via `create_agent()`
- Proper callback setup for response handling
- Active agent context preservation
- Clean error handling and fallbacks

### User Experience
- Real-time chat interface with message history
- @mention system for agent switching (`@claude`, `@gemini`, etc.)
- Active agent indicator in UI
- Clear controls (clear chat, reset agent)

### Message Processing
- Automatic @mention detection and routing
- Content filtering (removes `<think>` tags)
- Timestamp tracking for all messages
- Agent attribution for responses

## Usage

### Running the Interface
```bash
cd /path/to/abi
streamlit run src/core/user-interfaces/chat-mode/chat_interface.py --server.port 8510
```

### Agent Switching
```
@claude analyze this code
@gemini create an image
@mistral help with python
@abi return to supervisor
```

### Environment Requirements
- `ENV=dev` (automatically set)
- `LOG_LEVEL=CRITICAL` (reduces noise)
- Valid ABI module structure
- Working agent configurations

## Technical Details

### Session State
- `messages`: Chat history array
- `agent`: ABI agent instance
- `active_agent`: Currently active agent name

### Error Handling
- Agent initialization failures → Clear error messages
- Message sending errors → User feedback
- Missing dependencies → Graceful degradation

### Performance
- Lazy agent initialization
- Minimal session state
- Efficient message rendering
- Clean resource management

## Maintenance

### Code Quality
- Single responsibility functions
- Clear variable names
- Minimal dependencies
- Proper error boundaries

### Monitoring
- Agent initialization success/failure
- Message processing errors
- User interaction patterns
- Performance metrics

This interface prioritizes **functionality over complexity** - it works reliably with minimal code.