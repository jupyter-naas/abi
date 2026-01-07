FROM python:3.11

WORKDIR /app

COPY . .

RUN pip install uv

RUN uv sync --no-dev

CMD ["uv", "run", "python", "-m", "naas_abi_core.apps.api.api"]