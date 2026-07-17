# RegMap model-serving image. Build with the release folder as the context:
#   venv/Scripts/python.exe scripts/make_regmap_release.py
#   docker build -f packaging/regmap/Dockerfile -t ghcr.io/<owner>/regmap-embedder:0.1 dist/regmap-embedder
# Run:
#   docker run -p 8080:8080 ghcr.io/<owner>/regmap-embedder:0.1
#   curl -s localhost:8080/map -H 'Content-Type: application/json' -d '{"control":"Enforce MFA for remote access."}'
FROM python:3.11-slim
WORKDIR /app/model

# CPU-only torch keeps the image lean, then the rest of the inference stack.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu \
 && pip install --no-cache-dir "sentence-transformers>=2.2" fastapi "uvicorn[standard]"

# Context is the release folder (dist/regmap-embedder): model files + hipaa_corpus.csv +
# regmap_map.py + serve.py + card.
COPY . /app/model

ENV HF_HUB_OFFLINE=1 TRANSFORMERS_OFFLINE=1
EXPOSE 8080
CMD ["uvicorn", "serve:app", "--host", "0.0.0.0", "--port", "8080"]
