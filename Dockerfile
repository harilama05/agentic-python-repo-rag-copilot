FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PIP_DISABLE_PIP_VERSION_CHECK=1
ENV PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        build-essential \
        git \
        curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

RUN grep -Ev '^(pywin32|torchaudio|torchvision)==' requirements.txt > /tmp/requirements-linux.txt \
    && python -m pip install --upgrade pip \
    && python -m pip install \
        --extra-index-url https://download.pytorch.org/whl/cpu \
        -r /tmp/requirements-linux.txt

COPY . .

RUN mkdir -p data/runtime data/repos data/indexes logs

EXPOSE 8000

CMD ["python", "-m", "uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
