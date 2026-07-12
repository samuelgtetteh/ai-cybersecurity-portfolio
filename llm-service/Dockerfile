# Shared LLM service. The Qwen model is MOUNTED at runtime, NOT copied into the image, so the
# existing models/qwen2.5-1.5b-instruct is reused with nothing re-downloaded and the image stays
# lean. Build from this directory:
#   docker build -t llm-service llm-service
# Run (mount the model read-only; expose on host port 2600):
#   docker run -d --name llm-service -p 2600:8000 \
#     -v "<repo>/models/qwen2.5-1.5b-instruct:/model:ro" -e MODEL_PATH=/model llm-service
# Then point the backend at it: -e LLM_SERVICE_URL=http://host.docker.internal:2600
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app.py .
EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
