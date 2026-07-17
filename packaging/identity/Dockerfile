# Hybrid Identity Anomaly Detector — serving image. Build with the release folder as context:
#   venv/Scripts/python.exe scripts/make_identity_release.py
#   docker build -f packaging/identity/Dockerfile -t ghcr.io/<owner>/identity-anomaly:0.1 dist/identity-anomaly
# Run:
#   docker run -p 8081:8080 ghcr.io/<owner>/identity-anomaly:0.1
FROM python:3.11-slim
LABEL org.opencontainers.image.source="https://github.com/samuelgtetteh/ai-cybersecurity-portfolio"
LABEL org.opencontainers.image.description="Hybrid Identity Anomaly Detector (Isolation Forest) — POST /score"
LABEL org.opencontainers.image.licenses="Apache-2.0"
WORKDIR /app/model
RUN pip install --no-cache-dir scikit-learn==1.9.0 joblib pandas fastapi "uvicorn[standard]"
COPY . /app/model
EXPOSE 8080
CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8080"]
