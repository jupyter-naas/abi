#!/usr/bin/env python3
"""Example script demonstrating OpenAI-compatible API usage with ABI.

This script shows how to use the standard OpenAI Python client with ABI's
OpenAI-compatible endpoints.

Usage:
    export ABI_API_KEY="your-api-key"
    python examples/openai_api_example.py
"""

import os
import sys

try:
    from openai import OpenAI
except ImportError:
    print("Error: openai package not installed")
    print("Install it with: pip install openai")
    sys.exit(1)


def main():
    # Get API key from environment
    api_key = os.environ.get("ABI_API_KEY")
    if not api_key:
        print("Error: ABI_API_KEY environment variable not set")
        sys.exit(1)

    # Get API base URL (default to localhost)
    base_url = os.environ.get("ABI_API_BASE_URL", "http://localhost:9879/v1")

    print(f"Connecting to ABI at: {base_url}")
    print("=" * 60)

    # Initialize OpenAI client with ABI endpoint
    client = OpenAI(api_key=api_key, base_url=base_url)

    # Example 1: List available models (agents)
    print("\n1. Listing available models (ABI agents):")
    print("-" * 60)
    try:
        models = client.models.list()
        if not models.data:
            print("No models found. Make sure ABI is running with loaded agents.")
            sys.exit(1)

        for model in models.data:
            print(f"  - {model.id} (created: {model.created})")

        # Use the first model for examples
        selected_model = models.data[0].id
        print(f"\nUsing model: {selected_model}")
    except Exception as e:
        print(f"Error listing models: {e}")
        sys.exit(1)

    # Example 2: Non-streaming chat completion
    print("\n2. Non-streaming chat completion:")
    print("-" * 60)
    try:
        response = client.chat.completions.create(
            model=selected_model,
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful AI assistant. Keep responses concise.",
                },
                {"role": "user", "content": "What is the capital of France?"},
            ],
            temperature=0.7,
        )

        print(f"Response: {response.choices[0].message.content}")
        print(f"Finish reason: {response.choices[0].finish_reason}")
        print(
            f"Tokens used: {response.usage.total_tokens} "
            f"(prompt: {response.usage.prompt_tokens}, "
            f"completion: {response.usage.completion_tokens})"
        )
    except Exception as e:
        print(f"Error in chat completion: {e}")

    # Example 3: Streaming chat completion
    print("\n3. Streaming chat completion:")
    print("-" * 60)
    print("Response: ", end="", flush=True)
    try:
        stream = client.chat.completions.create(
            model=selected_model,
            messages=[
                {"role": "user", "content": "Count from 1 to 5 slowly."},
            ],
            stream=True,
        )

        for chunk in stream:
            if chunk.choices[0].delta.content:
                print(chunk.choices[0].delta.content, end="", flush=True)

        print()  # New line after stream
    except Exception as e:
        print(f"\nError in streaming: {e}")

    # Example 4: Multi-turn conversation
    print("\n4. Multi-turn conversation:")
    print("-" * 60)
    try:
        messages = [
            {"role": "system", "content": "You are a helpful math tutor."},
            {"role": "user", "content": "What is 5 + 3?"},
        ]

        # First turn
        response1 = client.chat.completions.create(
            model=selected_model, messages=messages, temperature=0
        )

        first_response = response1.choices[0].message.content
        print(f"User: What is 5 + 3?")
        print(f"Assistant: {first_response}")

        # Add to conversation history
        messages.append({"role": "assistant", "content": first_response})
        messages.append({"role": "user", "content": "Now multiply that by 2."})

        # Second turn
        response2 = client.chat.completions.create(
            model=selected_model, messages=messages, temperature=0
        )

        second_response = response2.choices[0].message.content
        print(f"User: Now multiply that by 2.")
        print(f"Assistant: {second_response}")
    except Exception as e:
        print(f"Error in conversation: {e}")

    # Example 5: Get specific model details
    print("\n5. Retrieving model details:")
    print("-" * 60)
    try:
        model = client.models.retrieve(selected_model)
        print(f"Model ID: {model.id}")
        print(f"Created: {model.created}")
        print(f"Owned by: {model.owned_by}")
    except Exception as e:
        print(f"Error retrieving model: {e}")

    print("\n" + "=" * 60)
    print("Examples completed successfully!")
    print(
        "\nNext steps:"
        "\n- Try different models/agents"
        "\n- Integrate with your applications"
        "\n- Set up OpenWebUI for a visual interface"
    )


if __name__ == "__main__":
    main()
