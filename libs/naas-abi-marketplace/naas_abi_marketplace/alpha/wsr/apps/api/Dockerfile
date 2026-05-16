FROM python:3.11-slim

WORKDIR /app

# Install dependencies from pyproject.toml before copying source
# so Docker layer caching avoids re-installing on source-only changes.
COPY pyproject.toml .
RUN pip install --no-cache-dir \
    "fastapi>=0.115" \
    "uvicorn[standard]>=0.30" \
    "httpx>=0.27" \
    "pydantic>=2.7" \
    "pydantic-settings>=2.3" \
    "python-dotenv>=1.0"

COPY . .

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
