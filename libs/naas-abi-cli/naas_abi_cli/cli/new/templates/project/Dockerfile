FROM python:3.11

WORKDIR /app

COPY . .

# Install CA certificates
RUN apt-get update && apt-get install -y ca-certificates && update-ca-certificates

RUN pip install uv

# Install OpenCode CLI (required by OpencodeAgent)
RUN curl -fsSL https://opencode.ai/install | bash

RUN uv sync --no-dev

CMD ["uv", "run", "python", "-m", "naas_abi_core.apps.api.api"]
