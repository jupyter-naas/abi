from lib.abi.models.Model import ChatModel
from langchain_anthropic import ChatAnthropic
from src import secret
from pydantic import SecretStr

ID = "claude-sonnet-4-5-20250929"
NAME = "Anthropic: Claude Sonnet 4.5"
DESCRIPTION = (
    "Claude Sonnet 4.5 is Anthropic’s most advanced Sonnet model to date, optimized for real-world agents and coding workflows. "
    "It delivers state-of-the-art performance on coding benchmarks such as SWE-bench Verified, with improvements across system design, code security, and specification adherence. "
    "The model is designed for extended autonomous operation, maintaining task continuity across sessions and providing fact-based progress tracking.\n\n"
    "Sonnet 4.5 also introduces stronger agentic capabilities, including improved tool orchestration, speculative parallel execution, and more efficient context and memory management. "
    "With enhanced context tracking and awareness of token usage across tool calls, it is particularly well-suited for multi-context and long-running workflows. Use cases span software engineering, cybersecurity, financial analysis, research agents, and other domains requiring sustained reasoning and tool use."
)
IMAGE = "https://assets.anthropic.com/m/0edc05fa8e30f2f9/original/Anthropic_Glyph_Black.svg"
CONTEXT_WINDOW = 1_000_000
OWNER = "anthropic"
TEMPERATURE = 1
MAX_TOKENS = 64_000
MAX_RETRIES = 2

model: ChatModel = ChatModel(
    model_id=ID,
    name=NAME,
    description=DESCRIPTION,
    image=IMAGE,
    owner=OWNER,
    model=ChatAnthropic(
        model_name=ID,
        temperature=TEMPERATURE,
        max_tokens_to_sample=MAX_TOKENS,
        timeout=None,
        max_retries=MAX_RETRIES,
        stop=None,
        api_key=SecretStr(secret.get("ANTHROPIC_API_KEY")),
    ),
    context_window=CONTEXT_WINDOW,
)