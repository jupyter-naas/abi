#!/bin/bash

# Navigate to the directory containing the app
cd "$(dirname "$0")"

# Set the Streamlit server port (default 8501)
PORT=8501

# Check if OpenAI is installed
if ! pip list | grep -q "openai"; then
    echo "Installing openai package..."
    pip install openai
fi

# Check if streamlit is installed
if ! pip list | grep -q "streamlit"; then
    echo "Installing streamlit package..."
    pip install streamlit
fi

# Run the Streamlit app directly
echo "Starting ABI Streamlit Chat on port $PORT..."
streamlit run app.py 