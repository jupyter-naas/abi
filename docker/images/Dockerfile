FROM python:3.11
WORKDIR /app

# Install CA certificates and LibreOffice (headless) for office-document
# preview conversion (docx/xlsx/pptx -> PDF) used by the Nexus files API.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        libreoffice-core \
        libreoffice-writer \
        libreoffice-calc \
        libreoffice-impress \
        fonts-dejavu \
        fonts-liberation \
    && update-ca-certificates \
    && rm -rf /var/lib/apt/lists/*

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

# Install OpenCode CLI (required by OpencodeAgent)
RUN curl -fsSL https://opencode.ai/install | bash 
