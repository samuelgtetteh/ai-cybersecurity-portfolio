# OT/ICS Intrusion Detector — serving image. Build with the release folder as context:
#   venv/Scripts/python.exe scripts/make_otics_release.py
#   docker build -f packaging/otics/Dockerfile -t ghcr.io/<owner>/otics-anomaly:0.1 dist/otics-anomaly
# Run:
#   docker run -p 8082:8080 ghcr.io/<owner>/otics-anomaly:0.1
FROM python:3.11-slim
LABEL org.opencontainers.image.source="https://github.com/samuelgtetteh/ai-cybersecurity-portfolio"
LABEL org.opencontainers.image.description="OT/ICS Intrusion Detector (autoencoder on HAI) — POST /score"
LABEL org.opencontainers.image.licenses="Apache-2.0"
WORKDIR /app/model
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir scikit-learn==1.9.0 joblib numpy fastapi "uvicorn[standard]"
COPY . /app/model
EXPOSE 8080
CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8080"]
