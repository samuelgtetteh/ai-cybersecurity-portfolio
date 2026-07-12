# Build from the repo root so this can COPY the model + data alongside the app:
#   docker build -f backend/Dockerfile -t regmap-api .
#   docker run -p 8000:8000 regmap-api
FROM python:3.11-slim

WORKDIR /app

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app.py backend/app.py
COPY backend/identity_api.py backend/identity_api.py
COPY backend/ics_api.py backend/ics_api.py
COPY backend/verdict_store.py backend/verdict_store.py
COPY backend/decision_api.py backend/decision_api.py
COPY backend/policy.py backend/policy.py
COPY models/regmap-embedder models/regmap-embedder
COPY data/processed/training_pairs.csv data/processed/training_pairs.csv
COPY data/processed/isolation_forest_model.pkl data/processed/isolation_forest_model.pkl
COPY data/processed/scaler.pkl data/processed/scaler.pkl
COPY data/processed/autoencoder_hai.pth data/processed/autoencoder_hai.pth
COPY data/processed/scaler_hai.pkl data/processed/scaler_hai.pkl
COPY data/processed/autoencoder_hai_meta.txt data/processed/autoencoder_hai_meta.txt

# Mirrors the local dev layout (repo_root/backend, repo_root/models, repo_root/data)
# so app.py's existing "../models" / "../data" relative paths resolve unchanged.
WORKDIR /app/backend

EXPOSE 8000
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
