FROM python:3.9
WORKDIR /app

COPY . .

RUN pip install poetry
RUN poetry config virtualenvs.in-project true

RUN curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o "awscliv2.zip" \
    && unzip awscliv2.zip \
    && ./aws/install

CMD ["poetry", "run", "chat-single-assistant"]