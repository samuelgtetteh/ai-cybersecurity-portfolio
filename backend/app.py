import time
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sentence_transformers import SentenceTransformer
import torch
from pathlib import Path
import pandas as pd

from identity_api import router as identity_router
from ics_api import router as ics_router
from decision_api import router as decision_router
from verdict_store import record_verdict_safe, update_verdict_meta, record_request

app = FastAPI(title="RegMap API")
app.include_router(identity_router)
app.include_router(ics_router)
app.include_router(decision_router)


@app.middleware("http")
async def record_traffic(request: Request, call_next):
    """Log every request the live system handles. A scoring endpoint stashes the id of
    the verdict it recorded on request.state; we enrich that row with request metadata
    (latency/status/client/path) and return it as the X-Verdict-Id header so any client
    can later attach ground truth to that exact decision. Non-scored requests (health
    checks, validation/errors) are audited in the requests table so the trail is complete."""
    start = time.perf_counter()
    response = await call_next(request)
    latency_ms = round((time.perf_counter() - start) * 1000, 3)
    client = request.client.host if request.client else None
    verdict_id = getattr(request.state, "verdict_id", None)
    if verdict_id:
        update_verdict_meta(verdict_id, latency_ms=latency_ms,
                            status=response.status_code, client=client,
                            path=request.url.path)
        response.headers["X-Verdict-Id"] = str(verdict_id)
    else:
        record_request(request.method, request.url.path, client,
                       response.status_code, latency_ms)
    return response


@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse(url="/docs")

# Paths are anchored to this file's location (repo_root/backend/app.py), not the
# process working directory, so the service resolves its model/data the same way
# whether launched from backend/, the repo root, or inside the Docker image.
BASE_DIR = Path(__file__).resolve().parent.parent
MODEL_PATH = BASE_DIR / 'models' / 'regmap-embedder'
DATA_FILE = BASE_DIR / 'data' / 'processed' / 'training_pairs.csv'
FALLBACK_DATA_FILE = BASE_DIR / 'data' / 'processed' / 'positive_pairs.csv'

model = SentenceTransformer(str(MODEL_PATH))

# Load the HIPAA corpus, falling back to positive_pairs.csv only if the primary
# file is genuinely absent — a narrow FileNotFoundError catch, so a real problem
# (e.g. a missing 'hipaa_text' column) surfaces instead of being swallowed.
try:
    df = pd.read_csv(DATA_FILE)
except FileNotFoundError:
    df = pd.read_csv(FALLBACK_DATA_FILE)
hipaa_texts = df['hipaa_text'].dropna().unique().tolist()

corpus_embeddings = model.encode(hipaa_texts, convert_to_tensor=True)

class QueryRequest(BaseModel):
    nist_control: str = Field(..., max_length=5000)

class MappingResult(BaseModel):
    hipaa_citation: str
    score: float

@app.post("/map", response_model=list[MappingResult])
def map_control(request: QueryRequest, http_request: Request):
    if not request.nist_control.strip():
        raise HTTPException(status_code=400, detail="Empty control text")
    query_embed = model.encode(request.nist_control.strip(), convert_to_tensor=True)
    cos_scores = torch.nn.functional.cosine_similarity(query_embed, corpus_embeddings)
    top5_idx = torch.topk(cos_scores, k=5).indices
    results = []
    for idx in top5_idx:
        results.append(MappingResult(
            hipaa_citation=hipaa_texts[idx][:200],  # truncate for readability
            score=round(float(cos_scores[idx]), 4)
        ))
    # Record layer: a low top-1 similarity is a low-confidence mapping worth
    # flagging (the same guardrail backend/event_simulator.py simulates).
    top1 = results[0].score if results else 0.0
    http_request.state.verdict_id = record_verdict_safe(
        model="regmap", flagged=top1 < 0.5, score=top1,
        subject=None,
        detail={"query": request.nist_control.strip()[:200],
                "top_citation": results[0].hipaa_citation if results else None},
    )
    return results

# Optional: health check
@app.get("/health")
def health():
    return {"status": "ok"}