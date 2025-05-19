FROM python:3.10
WORKDIR /app

# Install CA certificates
RUN apt-get update && apt-get install -y ca-certificates && update-ca-certificates

COPY . .

RUN pip install uv

# RUN pip install poetry
# RUN poetry config virtualenvs.in-project true

# # Install Rust toolchain
# RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | bash -s -- -y
# RUN . "$HOME/.cargo/env"
# RUN pip install maturin[patchelf]


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

CMD ["poetry", "run", "chat-single-assistant"]
