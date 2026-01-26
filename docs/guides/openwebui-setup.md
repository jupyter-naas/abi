# Setting Up OpenWebUI with ABI

This guide walks you through setting up [OpenWebUI](https://github.com/open-webui/open-webui) to work with ABI's OpenAI-compatible API.

## Overview

OpenWebUI is a feature-rich web interface for interacting with LLMs. With ABI's new OpenAI-compatible API, you can use OpenWebUI to chat with any ABI agent through an intuitive web interface.

## Prerequisites

- Docker installed and running
- ABI installed and configured
- At least one ABI agent configured with necessary API keys

## Quick Start

### Step 1: Start ABI API

First, make sure ABI's API is running:

```bash
# Navigate to your ABI directory
cd /path/to/abi

# Start the API
make api
```

The API should start on `http://localhost:9879`. You can verify it's running:

```bash
curl http://localhost:9879/v1/models -H "Authorization: Bearer $ABI_API_KEY"
```

You should see a list of available agents.

### Step 2: Run OpenWebUI

Start OpenWebUI using Docker:

```bash
docker run -d \
  -p 3000:8080 \
  -v open-webui:/app/backend/data \
  --name open-webui \
  ghcr.io/open-webui/open-webui:main
```

OpenWebUI will be available at `http://localhost:3000`.

### Step 3: Create OpenWebUI Account

1. Open your browser to `http://localhost:3000`
2. Click "Sign up" to create an account (this is stored locally in Docker)
3. Choose a username and password
4. Sign in with your new credentials

### Step 4: Configure ABI Connection

Now, connect OpenWebUI to ABI:

1. **Open Settings**:
   - Click your profile icon in the bottom left
   - Select "Settings"

2. **Navigate to Connections**:
   - Click on "Connections" in the settings sidebar
   - Look for the "OpenAI API" section

3. **Add ABI Connection**:
   - **API Base URL**: 
     - If running both locally: `http://localhost:9879/v1`
     - If OpenWebUI in Docker: `http://host.docker.internal:9879/v1`
   - **API Key**: Your ABI API key (the value of `ABI_API_KEY`)
   
4. **Save Settings**:
   - Click "Save" or "Update"
   - You should see a success message

### Step 5: Verify Connection

To verify the connection is working:

1. **Check Models**:
   - In OpenWebUI settings, under Connections
   - You should see your ABI agents listed as models

2. **Test Connection**:
   - Some versions have a "Test Connection" button
   - Click it to verify connectivity

### Step 6: Start Chatting

1. **Return to Chat**:
   - Click the chat icon or navigate back to the main interface

2. **Select an ABI Agent**:
   - Click the model dropdown at the top
   - You should see all your ABI agents listed
   - Select the agent you want to use

3. **Start Conversation**:
   - Type your message in the input box
   - Press Enter or click Send
   - The ABI agent will respond!

## Advanced Configuration

### Environment Variables

You can customize OpenWebUI's Docker deployment:

```bash
docker run -d \
  -p 3000:8080 \
  -v open-webui:/app/backend/data \
  -e OPENAI_API_BASE_URLS="http://host.docker.internal:9879/v1" \
  -e OPENAI_API_KEYS="$ABI_API_KEY" \
  --name open-webui \
  ghcr.io/open-webui/open-webui:main
```

This pre-configures the connection for all users.

### Using Docker Compose

Create a `docker-compose.yml`:

```yaml
version: '3.8'

services:
  open-webui:
    image: ghcr.io/open-webui/open-webui:main
    ports:
      - "3000:8080"
    volumes:
      - open-webui:/app/backend/data
    environment:
      - OPENAI_API_BASE_URLS=http://host.docker.internal:9879/v1
      - OPENAI_API_KEYS=${ABI_API_KEY}
    restart: unless-stopped

volumes:
  open-webui:
```

Then run:
```bash
docker-compose up -d
```

### Multiple Agent Profiles

You can configure different agents for different use cases:

1. Create separate "models" in OpenWebUI
2. Each can point to a different ABI agent
3. Switch between them based on your task

## Features You Can Use

OpenWebUI provides many features that work with ABI:

- **Multi-turn Conversations**: OpenWebUI manages conversation history
- **Markdown Rendering**: Responses are beautifully formatted
- **Code Highlighting**: Code blocks are syntax-highlighted
- **Model Switching**: Easily switch between different ABI agents
- **Conversation Management**: Save, search, and organize conversations
- **Dark/Light Mode**: Customize the appearance
- **Export Conversations**: Download chat history

## Troubleshooting

### Connection Issues

**Problem**: "Connection failed" or "Cannot connect to API"

**Solutions**:

1. **Check ABI API is running**:
   ```bash
   curl http://localhost:9879/v1/models -H "Authorization: Bearer $ABI_API_KEY"
   ```

2. **Use correct URL**:
   - OpenWebUI in Docker → `http://host.docker.internal:9879/v1`
   - Both local → `http://localhost:9879/v1`
   - Different machines → `http://<abi-host-ip>:9879/v1`

3. **Verify API Key**:
   ```bash
   echo $ABI_API_KEY
   ```

4. **Check Docker networking**:
   ```bash
   docker exec -it open-webui curl http://host.docker.internal:9879/v1/models
   ```

### No Models Showing

**Problem**: Model dropdown is empty or shows no ABI agents

**Solutions**:

1. **Verify agents are loaded**:
   ```bash
   curl http://localhost:9879/v1/models -H "Authorization: Bearer $ABI_API_KEY" | jq
   ```

2. **Check API key in OpenWebUI**:
   - Settings → Connections → Check API key is correct

3. **Refresh OpenWebUI**:
   - Hard refresh browser (Ctrl+Shift+R or Cmd+Shift+R)
   - Or restart OpenWebUI container

4. **Check agent configuration**:
   - Some agents need external API keys (e.g., OpenAI, Claude)
   - Ensure those are set in your `.env` file

### Authentication Errors

**Problem**: 401 Unauthorized errors in browser console

**Solutions**:

1. **Verify API key matches**:
   - The key in OpenWebUI must match `ABI_API_KEY` in your environment

2. **Check for spaces/special characters**:
   - Copy-paste API key carefully
   - No leading/trailing spaces

3. **Restart both services**:
   ```bash
   # Restart ABI API
   # (stop and restart with 'make api')
   
   # Restart OpenWebUI
   docker restart open-webui
   ```

### Slow Responses

**Problem**: Responses take a long time to appear

**Solutions**:

1. **Use streaming**:
   - OpenWebUI should automatically use streaming
   - Check network tab for SSE connections

2. **Check agent performance**:
   - Some agents may be slower depending on their underlying model
   - Try a different agent

3. **Network latency**:
   - If ABI is on a different machine, check network speed
   - Consider running both on the same machine

### Docker Networking Issues

**Problem**: `host.docker.internal` doesn't resolve

**Solutions**:

1. **Linux users**:
   ```bash
   docker run -d \
     -p 3000:8080 \
     --add-host=host.docker.internal:host-gateway \
     -v open-webui:/app/backend/data \
     --name open-webui \
     ghcr.io/open-webui/open-webui:main
   ```

2. **Use network_mode host** (Linux only):
   ```bash
   docker run -d \
     --network host \
     -v open-webui:/app/backend/data \
     --name open-webui \
     ghcr.io/open-webui/open-webui:main
   ```
   Then use `http://localhost:9879/v1`

3. **Get host IP**:
   ```bash
   # macOS/Linux
   ipconfig getifaddr en0  # or en1, wlan0, etc.
   
   # Then use http://<ip>:9879/v1
   ```

## Tips and Best Practices

### Conversation Management

- **Name your conversations**: Click the title to rename
- **Use folders**: Organize conversations by topic/agent
- **Archive old chats**: Keep your workspace clean

### Model Selection

- **Choose the right agent**: Different agents have different capabilities
- **Switch agents mid-conversation**: You can change agents during a chat
- **Create templates**: Save common prompts for reuse

### Performance

- **Enable streaming**: For better UX with long responses
- **Use appropriate agents**: Don't use heavy agents for simple tasks
- **Monitor API load**: Keep an eye on ABI's performance

### Security

- **Use strong passwords**: For OpenWebUI accounts
- **Protect API keys**: Don't share your `ABI_API_KEY`
- **Regular updates**: Keep OpenWebUI and ABI up to date
- **Network security**: Consider using HTTPS/TLS in production

## Comparison with Direct ABI Chat

| Feature | OpenWebUI | Direct ABI CLI |
|---------|-----------|----------------|
| User Interface | Web-based GUI | Terminal CLI |
| Conversation History | Persistent, searchable | Session-based |
| Model Switching | Visual dropdown | Command restart |
| Markdown Rendering | Rich formatting | Plain text |
| Code Highlighting | Yes | Basic |
| Multi-user | Yes (with accounts) | No |
| Ease of Use | Very easy | Requires CLI familiarity |
| Customization | Limited to UI settings | Full control |
| Performance | Slight overhead | Direct |

## Alternative UI Options

If OpenWebUI doesn't work for you, consider these alternatives:

1. **Chatbot UI** - Similar web interface
   ```bash
   docker run -d \
     -p 3000:3000 \
     -e OPENAI_API_KEY=$ABI_API_KEY \
     -e OPENAI_API_HOST=http://host.docker.internal:9879 \
     mckaywrigley/chatbot-ui:latest
   ```

2. **LibreChat** - Feature-rich alternative
   - Supports multiple providers
   - User management
   - Advanced configuration

3. **BetterChatGPT** - Lightweight option
   - Simple and fast
   - No backend required
   - Client-side only

## Next Steps

Now that you have OpenWebUI connected to ABI:

1. **Explore different agents**: Try various ABI agents for different tasks
2. **Customize your experience**: Adjust OpenWebUI settings to your liking
3. **Integrate with workflows**: Use OpenWebUI as part of your daily workflow
4. **Share with team**: Set up for multiple users if needed

## Resources

- [OpenWebUI Documentation](https://docs.openwebui.com/)
- [OpenWebUI GitHub](https://github.com/open-webui/open-webui)
- [ABI Documentation](../../README.md)
- [OpenAI API Compatibility Guide](../api/openai-compatibility.md)

## Getting Help

If you encounter issues:

1. Check this troubleshooting section
2. Review ABI logs: Check console output when running `make api`
3. Review OpenWebUI logs: `docker logs open-webui`
4. Open an issue on GitHub with:
   - ABI version
   - OpenWebUI version
   - Error messages
   - Steps to reproduce

Happy chatting with ABI through OpenWebUI! 🎉
