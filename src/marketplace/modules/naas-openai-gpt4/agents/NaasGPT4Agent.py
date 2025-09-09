"""
Naas GPT-4 Agent - Working implementation using reverse-engineered API
Consolidates all working code from capture_naas_requests.py, chat_gpt4.py, chat_naas.py
"""

import os
import json
import httpx
from typing import Dict, Any
from dotenv import load_dotenv

load_dotenv()

class NaasGPT4Agent:
    """Working Naas GPT-4 agent using reverse-engineered API"""
    
    def __init__(self):
        # Working configuration from reverse engineering
        self.base_url = "https://api.naas.ai"
        self.chat_id = int(os.getenv("NAAS_CHAT_ID", "15349"))  # Configurable chat ID
        self.model_id = "507dbbc5-88a1-4bd7-8c35-28cea3faaf1f"  # GPT-4 model ID
        
        # Get token from environment
        self.token = os.getenv("NAAS_TOKEN")
        if not self.token:
            raise ValueError("NAAS_TOKEN not found in .env - add your JWT token")
        
        # Exact working headers from reverse engineering
        self.headers = {
            "accept": "*/*",
            "accept-language": "fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7",
            "authorization": f"Bearer {self.token}",
            "content-type": "application/json",
            "origin": "https://naas.ai",
            "referer": "https://naas.ai/",
            "sec-ch-ua": '"Chromium";v="140", "Not=A?Brand";v="24", "Google Chrome";v="140"',
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": '"Windows"',
            "sec-fetch-dest": "empty",
            "sec-fetch-mode": "cors",
            "sec-fetch-site": "same-site",
            "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # HTTP client with SSL bypass for corporate environments
        self.client = httpx.Client(
            verify=False,
            headers=self.headers,
            timeout=60.0
        )
        
        # Conversation history
        self.conversation_history = []
    
    def chat(self, message: str) -> Dict[str, Any]:
        """Send message to GPT-4 using working reverse-engineered format"""
        
        try:
            # Add to conversation history
            self.conversation_history.append({"role": "user", "content": message})
            
            # Build context-aware prompt
            context_prompt = self._build_context_prompt(message)
            
            # Exact working format from reverse engineering
            prompt = f"@[openai/gpt-4]{{MODEL::{self.model_id}}} {context_prompt}"
            
            # Working payload structure
            payload = {
                "id": self.chat_id,
                "model_id": self.model_id,
                "payload": json.dumps({
                    "prompt": prompt,
                    "temperature": 0.7
                })
            }
            
            endpoint = f"{self.base_url}/chat/{self.chat_id}/completion"
            
            response = self.client.post(endpoint, json=payload)
            
            if response.status_code == 200:
                data = response.json()
                
                # Extract response content
                content = self._extract_response_content(data)
                
                # Add to conversation history
                self.conversation_history.append({"role": "assistant", "content": content})
                
                return {
                    "success": True,
                    "content": content,
                    "tokens": {
                        "input": data.get("input_tokens", 0),
                        "output": data.get("output_tokens", 0)
                    }
                }
            else:
                return {
                    "success": False,
                    "error": f"API returned {response.status_code}: {response.text}"
                }
                
        except Exception as e:
            return {
                "success": False,
                "error": f"Request failed: {str(e)}"
            }
    
    def _build_context_prompt(self, current_message: str) -> str:
        """Build context-aware prompt with conversation history"""
        
        # Keep last 6 messages for context
        recent_history = self.conversation_history[-6:] if len(self.conversation_history) > 6 else self.conversation_history
        
        if not recent_history:
            return current_message
        
        # Build context
        context_parts = []
        for msg in recent_history:
            role = "User" if msg["role"] == "user" else "Assistant"
            context_parts.append(f"{role}: {msg['content']}")
        
        context_parts.append(f"User: {current_message}")
        context_parts.append("Assistant:")
        
        return "\\n".join(context_parts)
    
    def _extract_response_content(self, api_response: Dict[str, Any]) -> str:
        """Extract GPT-4 response from API response"""
        
        try:
            # Extract from Naas API response structure
            if "completion" in api_response and "messages" in api_response["completion"]:
                messages = api_response["completion"]["messages"]
                # Find the last message from the assistant (from_user: false)
                for message in reversed(messages):
                    if not message.get("from_user", True):  # Assistant message
                        return message.get("message", "").strip()
            
            # Try standard OpenAI format
            if "choices" in api_response and api_response["choices"]:
                choice = api_response["choices"][0]
                if "message" in choice and "content" in choice["message"]:
                    return choice["message"]["content"].strip()
                elif "text" in choice:
                    return choice["text"].strip()
            
            if "response" in api_response:
                return api_response["response"].strip()
            
            if "content" in api_response:
                return api_response["content"].strip()
            
            if "text" in api_response:
                return api_response["text"].strip()
            
            # Fallback - return formatted response
            return f"Response received: {json.dumps(api_response, indent=2)}"
            
        except Exception as e:
            return f"Error extracting response: {str(e)}"
    
    def clear_conversation(self):
        """Clear conversation history"""
        self.conversation_history = []
        return {"success": True, "message": "Conversation cleared"}
    
    def get_conversation_summary(self):
        """Get conversation summary"""
        return {
            "success": True,
            "message_count": len(self.conversation_history),
            "recent_messages": self.conversation_history[-4:] if self.conversation_history else []
        }


def create_agent():
    """Factory function for ABI module system"""
    return NaasGPT4Agent()