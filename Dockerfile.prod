FROM python:3.9
WORKDIR /app

COPY . .

RUN pip install poetry
RUN poetry config virtualenvs.in-project true


CMD ["poetry", "run", "chat-single-assistant"]