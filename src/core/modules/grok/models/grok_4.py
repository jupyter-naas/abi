from src import secret
from pydantic import SecretStr

# Grok Model Configuration using proper LangChain xAI integration
# Based on: https://python.langchain.com/docs/integrations/chat/xai/

NAME = "grok-beta"  # Using proper model name from xAI
ID = "grok-beta"
TEMPERATURE = 0.1
MAX_TOKENS = 4096

# Try to use proper xAI integration with langchain_xai, fallback gracefully
try:
    from langchain_xai import ChatXAI  # type: ignore
    
    # Check if XAI_API_KEY is available
    xai_api_key = secret.get("XAI_API_KEY")
    if xai_api_key and xai_api_key != "placeholder_key":
        # Use real xAI API
        model = ChatXAI(
            model=ID,
            temperature=TEMPERATURE,
            max_tokens=MAX_TOKENS,
            api_key=SecretStr(xai_api_key),
            # Enable Live Search for real-time information
            search_parameters={
                "mode": "auto",
                "max_search_results": 5,
            },
        )
        print("✅ Using xAI Grok with langchain-xai integration")
    else:
        raise ValueError("XAI_API_KEY not found")
        
except (ImportError, ValueError) as e:
    # Fallback to OpenAI for development
    print(f"⚠️ Using OpenAI fallback for Grok agent: {e}")
    from langchain_openai import ChatOpenAI
    
    model = ChatOpenAI(
        model="gpt-4o-mini",  # Temporary fallback
        temperature=TEMPERATURE,
        max_completion_tokens=MAX_TOKENS,
        api_key=SecretStr(secret.get("OPENAI_API_KEY", "placeholder_key"))
    )