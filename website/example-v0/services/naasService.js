export async function generateResponse(message, onChunk = null, threadId = 123) {
  const myHeaders = new Headers();
  myHeaders.append("Authorization", "Bearer naas2025!");
  myHeaders.append("Content-Type", "application/json");

  const raw = JSON.stringify({
    "thread_id": threadId,
    "prompt": message
  });

  const requestOptions = {
    method: "POST",
    headers: myHeaders,
    body: raw,
    redirect: "follow"
  };

  try {
    const response = await fetch("https://abi-healthyphases-api.default.space.naas.ai/agents/elo/completion", requestOptions);
    
    if (!response.ok) {
      throw new Error(`HTTP error! status: ${response.status}`);
    }
    
    const result = await response.json();
    console.log('API response:', result);
    
    // Extract the message from the JSON response
    const messageContent = result.message || result.content || result.text || result;
    
    if (onChunk) {
      onChunk(messageContent);
    }
    
    return messageContent;
  } catch (error) {
    console.error("Naas service error:", error);
    throw error;
  }
}

function parseSSEResponse(response) {
  const messages = [];
  
  const parser = createParser({
    onEvent: (event) => {
      console.log('SSE event:', event);
      if (event.type === 'event' && event.event === 'message' && event.data) {
        // Only include actual message content, not system messages or [DONE]
        if (!event.data.includes('SYSTEM MESSAGE') && event.data !== '[DONE]' && event.data.trim()) {
          console.log('Adding message to array:', event.data);
          messages.push(event.data);
        }
      }
    }
  });
  
  // Feed the response to the parser
  parser.feed(response);
  
  const result = messages.join(' ');
  console.log('SSE messages array:', messages);
  console.log('SSE final result:', result);
  return result;
}

function parseFallback(response) {
  console.log('Using fallback parser for:', response);
  
  // Handle SSE-like format: "event: message data: [MESSAGE] event: done data:"
  const messageStart = response.indexOf('event: message data:');
  const doneStart = response.indexOf('event: done data:');
  
  if (messageStart !== -1 && doneStart !== -1) {
    const messageContent = response.substring(messageStart + 20, doneStart).trim();
    console.log('Extracted message from SSE fallback:', messageContent);
    return messageContent;
  }
  
  // Handle the format: "map_intent I don't know what to do with this prompt. [MESSAGE] [DONE]"
  const promptIndex = response.indexOf('prompt.');
  const doneIndex = response.indexOf('[DONE]');
  
  if (promptIndex !== -1 && doneIndex !== -1) {
    const messageContent = response.substring(promptIndex + 7, doneIndex).trim();
    console.log('Extracted message from fallback:', messageContent);
    return messageContent;
  }
  
  // Last resort: try to find any meaningful text that's not system data
  const lines = response.split('\n');
  const messages = [];
  
  for (const line of lines) {
    if (line.startsWith('data: ') && 
        !line.includes('SYSTEM MESSAGE') && 
        !line.includes('[DONE]') && 
        !line.includes('map_intent') &&
        line.length > 10) {
      const data = line.substring(6).trim();
      if (data) {
        messages.push(data);
      }
    }
  }
  
  if (messages.length > 0) {
    const result = messages.join(' ');
    console.log('Extracted messages from lines:', result);
    return result;
  }
  
  // Ultimate fallback: clean up the response
  let cleaned = response
    .replace('map_intent', '')
    .replace('I don\'t know what to do with this prompt.', '')
    .replace('[DONE]', '')
    .replace(/event:.*?data:/g, '')
    .replace(/SYSTEM MESSAGE.*?\]/g, '')
    .trim();
  
  cleaned = cleaned.replace(/\s+/g, ' ');
  console.log('Cleaned fallback result:', cleaned);
  return cleaned;
} 