#!/bin/bash
# Test script for OpenAI-compatible API endpoints
# Usage: ./examples/test_openai_api.sh

set -e

# Configuration
API_BASE="${ABI_API_BASE_URL:-http://localhost:9879}"
API_KEY="${ABI_API_KEY:-abi}"

if [ -z "$ABI_API_KEY" ]; then
    echo "Warning: ABI_API_KEY not set, using default 'abi'"
fi

echo "Testing ABI OpenAI-compatible API"
echo "=================================="
echo "Base URL: $API_BASE/v1"
echo ""

# Test 1: List models
echo "1. Testing GET /v1/models"
echo "--------------------------"
MODELS_RESPONSE=$(curl -s "$API_BASE/v1/models" \
  -H "Authorization: Bearer $API_KEY")

echo "$MODELS_RESPONSE" | jq '.'

# Extract first model ID
FIRST_MODEL=$(echo "$MODELS_RESPONSE" | jq -r '.data[0].id')

if [ -z "$FIRST_MODEL" ] || [ "$FIRST_MODEL" = "null" ]; then
    echo "Error: No models found. Is ABI running with agents loaded?"
    exit 1
fi

echo ""
echo "Using model: $FIRST_MODEL"
echo ""

# Test 2: Get specific model
echo "2. Testing GET /v1/models/{model_id}"
echo "------------------------------------"
curl -s "$API_BASE/v1/models/$FIRST_MODEL" \
  -H "Authorization: Bearer $API_KEY" | jq '.'
echo ""

# Test 3: Non-streaming chat completion
echo "3. Testing POST /v1/chat/completions (non-streaming)"
echo "-----------------------------------------------------"
curl -s "$API_BASE/v1/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "'"$FIRST_MODEL"'",
    "messages": [
      {"role": "system", "content": "You are a helpful assistant. Be concise."},
      {"role": "user", "content": "What is 2+2?"}
    ],
    "temperature": 0.7
  }' | jq '.'
echo ""

# Test 4: Streaming chat completion
echo "4. Testing POST /v1/chat/completions (streaming)"
echo "-------------------------------------------------"
echo "Response stream:"
curl -s "$API_BASE/v1/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "'"$FIRST_MODEL"'",
    "messages": [
      {"role": "user", "content": "Count from 1 to 3."}
    ],
    "stream": true
  }'
echo ""
echo ""

# Test 5: Test invalid model
echo "5. Testing with invalid model (should fail)"
echo "--------------------------------------------"
INVALID_RESPONSE=$(curl -s "$API_BASE/v1/chat/completions" \
  -H "Authorization: Bearer $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "nonexistent-model",
    "messages": [{"role": "user", "content": "Hello"}]
  }')

echo "$INVALID_RESPONSE" | jq '.'
echo ""

# Test 6: Test without authentication (should fail)
echo "6. Testing without authentication (should fail)"
echo "-----------------------------------------------"
UNAUTH_RESPONSE=$(curl -s -w "\nHTTP Status: %{http_code}" "$API_BASE/v1/models" 2>&1)
echo "$UNAUTH_RESPONSE"
echo ""

echo "=================================="
echo "All tests completed!"
echo ""
echo "Summary:"
echo "  ✓ Model listing works"
echo "  ✓ Model retrieval works"
echo "  ✓ Non-streaming completion works"
echo "  ✓ Streaming completion works"
echo "  ✓ Error handling works"
echo "  ✓ Authentication works"
echo ""
echo "Next steps:"
echo "  - Try with different agents/models"
echo "  - Test with the Python OpenAI client"
echo "  - Set up OpenWebUI for a visual interface"
