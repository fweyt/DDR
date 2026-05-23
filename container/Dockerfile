FROM debian:12-slim

RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    sqlite3 \
    curl \
    docker.io \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

RUN python3 -m venv /venv && \
    /venv/bin/pip install --no-cache-dir -r requirements.txt

EXPOSE 5000

CMD ["/venv/bin/python", "-m", "uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "5000"]
