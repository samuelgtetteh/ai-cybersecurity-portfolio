"""Minimal RegMap inference server (used by the Docker image).

POST /map {"control": "...", "top_k": 5}  -> top-k HIPAA provisions for a NIST SP 800-53 control.
GET  /health                              -> {"status": "ok"}

The model, corpus, and regmap_map.py wrapper all sit in this directory (the image copies the
release folder here), so we import the wrapper directly.
"""
import os
import sys

from fastapi import FastAPI
from pydantic import BaseModel, Field

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from regmap_map import map_control  # noqa: E402  (bundled alongside this file)

app = FastAPI(title="RegMap — NIST 800-53 → HIPAA")


class Query(BaseModel):
    control: str = Field(..., description="a NIST SP 800-53 control description")
    top_k: int = Field(5, ge=1, le=20)


@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/map")
def do_map(q: Query):
    return {"control": q.control, "matches": map_control(q.control, q.top_k)}
