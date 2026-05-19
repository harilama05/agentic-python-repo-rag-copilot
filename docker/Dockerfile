FROM python:3.11-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    HF_HOME=/app/data/cache/huggingface \
    SENTENCE_TRANSFORMERS_HOME=/app/data/cache/sentence-transformers

RUN apt-get update \
    && apt-get install -y --no-install-recommends git curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY . .

# Create data directories
RUN mkdir -p \
    data/repos/github \
    data/uploads/zip_repositories \
    data/indexes/chroma \
    data/indexes/bm25 \
    data/indexes/metadata \
    data/indexes/graph \
    data/eval \
    data/logs \
    data/cache

EXPOSE 8000 8501

# Default: run Streamlit. docker-compose overrides this for the API service.
CMD ["streamlit", "run", "app/streamlit_app.py", "--server.port", "8501", "--server.address", "0.0.0.0"]
