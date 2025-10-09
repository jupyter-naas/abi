import ExecutionEnvironment from '@docusaurus/ExecutionEnvironment';
import { GEMINI_API_KEY } from '../../../env';

// System instruction for ABI
const SYSTEM_INSTRUCTION = `You are ABI (Agentic Brain Infrastructure), an intelligent, ontology-powered assistant that helps users build and interact with custom AI systems. Your purpose is to provide transparent, evidence-based, and strategic responses based on structured knowledge about AI capabilities, domain expertise, and system architecture.

Core Identity:
- System: ABI (Agentic Brain Infrastructure)
- Purpose: Custom AI creation and management platform
- Context: Helping users build domain-specific AI assistants
- Knowledge Sources: Semantic Knowledge Graphs, Ontologies, Module documentation

Key Behaviors:
- Ground answers in structured, verifiable data about AI capabilities
- Identify user intent and select relevant knowledge to answer
- Use natural but precise language
- Cite evidence when relevant about AI models and domain experts
- Adapt tone to the user's technical level
- Never make speculative claims about AI capabilities
- Format responses using proper markdown for readability
- Use line breaks and spacing for clear structure

Voice:
- Clear, confident, and helpful
- Technical but accessible
- Always evidence-based
- Focus on practical AI implementation`;

// Initialize variables
let ai = null;
let GenAI = null;
let currentChat = null;

// Dynamic import of the Gemini SDK
if (ExecutionEnvironment.canUseDOM) {
  import('@google/genai').then((module) => {
    GenAI = module.GoogleGenAI;
    ai = new GenAI({ apiKey: GEMINI_API_KEY });
    initializeChat();
  }).catch((error) => {
    console.error('Error loading Gemini SDK:', error);
  });
}

function formatResponse(text) {
  // Ensure proper line breaks between sections
  let formatted = text
    .replace(/\*\*/g, '**')  // Preserve bold markdown
    .replace(/\n\*/g, '\n\n*') // Add extra line break before bullet points
    .replace(/\n(?=[A-Z])/g, '\n\n') // Add extra line break before new sentences
    .trim(); // Remove extra whitespace

  // Ensure proper spacing after bullet points
  formatted = formatted.replace(/\* /g, '* ');
  
  return formatted;
}

async function initializeChat() {
  if (!ai) return;

  currentChat = ai.chats.create({
    model: "gemini-2.0-flash",
    history: [
      {
        role: "user",
        parts: [{ text: SYSTEM_INSTRUCTION }],
      },
      {
        role: "model",
        parts: [{ text: "I understand and will operate according to these instructions as BOB, ready to assist Orange stakeholders." }],
      }
    ],
    config: {
      temperature: 0.7,
      topK: 40,
      topP: 0.95,
      maxOutputTokens: 1024,
    },
  });
}

export async function generateResponse(message, onChunk = null) {
  try {
    if (!ExecutionEnvironment.canUseDOM) {
      throw new Error('Gemini API can only be used in browser environment');
    }

    if (!GEMINI_API_KEY) {
      throw new Error('Gemini API key not found. Please configure your environment variables.');
    }

    // Wait for SDK to load if it hasn't already
    if (!ai || !currentChat) {
      const module = await import('@google/genai');
      GenAI = module.GoogleGenAI;
      ai = new GenAI({ apiKey: GEMINI_API_KEY });
      await initializeChat();
    }

    // If streaming is requested
    if (onChunk) {
      const response = await currentChat.sendMessageStream({
        message: message,
      });

      let fullText = '';
      for await (const chunk of response) {
        const formattedChunk = formatResponse(chunk.text);
        fullText += chunk.text;
        onChunk(formattedChunk);
      }
      return formatResponse(fullText);
    }

    // Non-streaming version
    const response = await currentChat.sendMessage({
      message: message,
    });

    return formatResponse(response.text);
  } catch (error) {
    console.error('Error generating response:', error);
    // If there's an error with the chat, try to reinitialize it
    if (error.message.includes('chat') || error.message.includes('conversation')) {
      currentChat = null;
      await initializeChat();
    }
    throw error;
  }
}