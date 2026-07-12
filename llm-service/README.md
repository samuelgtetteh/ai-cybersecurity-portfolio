# Shared LLM Service (Qwen sidecar)

One Qwen instance, loaded once and served over HTTP to every component that needs a local LLM —
so the same model backs multiple parts of the project instead of each loading its own copy.

- **Model is mounted, not baked in.** The image contains only code + deps; the existing
  `models/qwen2.5-1.5b-instruct` is bind-mounted at runtime (`MODEL_PATH`, default `/model`).
  Nothing is re-downloaded and the ~3 GB model is not duplicated into the image.
- **Callers** set `LLM_SERVICE_URL` to reach it. `backend/llm_client.py` already prefers this
  service when the variable is set and falls back to an in-process model otherwise. Control
  Advisor can be pointed here too, so a single instance serves the whole project.

## Endpoints
- `GET /health` → `{status, model_loaded, model_path}` (instant; model loads lazily on first use)
- `POST /generate` → `{text}` — body `{"messages": [...chat...], "max_new_tokens": 160}`

## Run
```bash
docker build -t llm-service llm-service
docker run -d --name llm-service -p 2600:8000 \
  -v "$(pwd)/models/qwen2.5-1.5b-instruct:/model:ro" -e MODEL_PATH=/model llm-service

# point the backend (RedMap) at it, then recreate RedMap:
#   -e LLM_SERVICE_URL=http://host.docker.internal:2600
```
Locally (no container) the backend falls back to loading the model in-process, so the decision
layer works with or without this service running.
