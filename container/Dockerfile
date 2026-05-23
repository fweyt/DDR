FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY src/ src/
COPY static/ static/
COPY prompts/ prompts/
COPY config.json.example /app/config.json.example

EXPOSE 5000

CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "5000"]
