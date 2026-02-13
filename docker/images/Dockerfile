FROM python:3.11
WORKDIR /app

# Install CA certificates
RUN apt-get update && apt-get install -y ca-certificates && update-ca-certificates

# Install uv
RUN pip install uv

# Add build argument for architecture
ARG TARGETARCH

# Install AWS CLI based on architecture
RUN if [ "$TARGETARCH" = "arm64" ]; then \
        curl "https://awscli.amazonaws.com/awscli-exe-linux-aarch64.zip" -o "awscliv2.zip"; \
    else \
        curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip"; \
    fi \
    && unzip awscliv2.zip \
    && ./aws/install

# Copy ALL source code (required for editable installs)
COPY . .

# Sync dependencies once during build (this creates .venv with all deps)
RUN uv sync --all-extras --no-dev

# Set Python path to use the venv
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH="/app"

# Default command - direct python (no uv run overhead)
CMD ["python", "-m", "naas_abi_core.apps.api.api"]