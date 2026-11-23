FROM python:3.11-slim

WORKDIR /app

# Install dependencies before copying source so Docker layer caching avoids
# re-installing on source-only changes. requirements.txt is `uv export` of
# uv.lock: every package at the locked version, with its hashes.
COPY requirements.txt .
RUN pip install --no-cache-dir --require-hashes -r requirements.txt

COPY . .

USER nobody

EXPOSE 8080

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080", "--workers", "1"]
