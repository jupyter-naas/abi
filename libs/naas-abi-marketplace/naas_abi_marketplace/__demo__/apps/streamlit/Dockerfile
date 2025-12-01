FROM abi:latest

# Override the default command to run the Streamlit app
CMD ["uv", "run", "--no-dev", "streamlit", "run", "libs/naas-abi-marketplace/naas_abi_marketplace/__demo__/apps/streamlit/__init__.py", "--server.port=8501", "--server.address=0.0.0.0"]