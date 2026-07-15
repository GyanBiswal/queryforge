FROM python:3.12-slim

WORKDIR /app

# System deps kept minimal — add here only when a future phase needs them
# (e.g. libmagic for file-type detection, poppler-utils for PDF parsing)
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

EXPOSE 8000

CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]