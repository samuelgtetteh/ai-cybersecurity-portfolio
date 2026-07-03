from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sentence_transformers import SentenceTransformer
import torch
from pathlib import Path
import pandas as pd

app = FastAPI(title="RegMap API")

# Load model and HIPAA corpus at startup
MODEL_PATH = Path('../models/regmap-embedder')
DATA_FILE = Path('../data/processed/training_pairs.csv')  # or positive_pairs.csv

model = SentenceTransformer(str(MODEL_PATH))

# Load HIPAA texts (same as in your Streamlit app)
try:
    df = pd.read_csv(DATA_FILE)
    hipaa_texts = df['hipaa_text'].dropna().unique().tolist()
except:
    # fallback
    df = pd.read_csv(Path('../data/processed/positive_pairs.csv'))
    hipaa_texts = df['hipaa_text'].dropna().unique().tolist()

corpus_embeddings = model.encode(hipaa_texts, convert_to_tensor=True)

class QueryRequest(BaseModel):
    nist_control: str

class MappingResult(BaseModel):
    hipaa_citation: str
    score: float

@app.post("/map", response_model=list[MappingResult])
def map_control(request: QueryRequest):
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
    return results

# Optional: health check
@app.get("/health")
def health():
    return {"status": "ok"}