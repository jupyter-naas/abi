FROM python:3.9
WORKDIR /app

COPY . .

RUN pip install poetry
RUN poetry config virtualenvs.in-project true

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