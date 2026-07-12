"""
Shared LLM service (sidecar). Loads ONE Qwen instance and serves it over HTTP to every part
of the project that needs a local LLM — the decision layer's triage/prioritization, and
(prospectively) Control Advisor — so the model is loaded once and reused, not re-instantiated
per component. The model is MOUNTED at runtime (MODEL_PATH), never copied into the image, so the
existing models/qwen2.5-1.5b-instruct is reused as-is with nothing re-downloaded.

Endpoints:
  GET  /health    -> {status, model_loaded, model_path}
  POST /generate  -> {text}   body: {messages: [...chat...], max_new_tokens: int}

The model loads lazily on the first /generate (so /health is instant and reflects liveness).
"""
import os
from threading import Lock

import torch
from fastapi import FastAPI
from pydantic import BaseModel
from transformers import AutoModelForCausalLM, AutoTokenizer

MODEL_PATH = os.environ.get("MODEL_PATH", "/model")

app = FastAPI(title="Shared LLM Service (Qwen)")
_lock = Lock()
_model = None
_tok = None


def _load():
    global _model, _tok
    if _model is not None:
        return
    with _lock:
        if _model is not None:
            return
        _tok = AutoTokenizer.from_pretrained(MODEL_PATH)
        _model = AutoModelForCausalLM.from_pretrained(MODEL_PATH, dtype=torch.float32)
        _model.eval()


class GenerateRequest(BaseModel):
    messages: list
    max_new_tokens: int = 160


@app.get("/health")
def health():
    return {"status": "ok", "model_loaded": _model is not None, "model_path": MODEL_PATH}


@app.post("/generate")
def generate(req: GenerateRequest):
    _load()
    text = _tok.apply_chat_template(req.messages, tokenize=False, add_generation_prompt=True)
    inputs = _tok(text, return_tensors="pt")
    with torch.no_grad():
        out = _model.generate(**inputs, max_new_tokens=req.max_new_tokens, do_sample=False)
    completion = _tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    return {"text": completion}
