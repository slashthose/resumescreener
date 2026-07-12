FROM python:3.11-slim

# Install Ollama
RUN apt-get update && apt-get install -y curl zstd procps && \
    curl -fsSL https://ollama.com/install.sh | sh && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .


RUN ollama serve & \
    sleep 5 && \
    ollama pull llama3 && \
    (pkill ollama || true)

EXPOSE 8000


CMD ollama serve & \
    sleep 3 && \
    uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
