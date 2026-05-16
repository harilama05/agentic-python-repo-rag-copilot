FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Create data directories
RUN mkdir -p data/repos data/uploads data/indexes/chroma data/indexes/bm25 data/indexes/metadata data/eval data/logs

EXPOSE 8000 8501

# Default: run the API
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
