"""
AI triage layer (Track E): a per-alert analyst summary, grounded by retrieval (RAG) over the
compliance corpus, optionally written by the local Qwen LLM.

For a given Decide-layer alert this returns:
  - related_controls: the top HIPAA provisions retrieved for the alert via the fine-tuned RegMap
    embedder (models/regmap-embedder) over the same corpus as /map — i.e. "which compliance
    obligations does this security event touch";
  - summary: a concise SOC-analyst triage. Written by the local Qwen model
    (models/qwen2.5-1.5b-instruct, the same one Control Advisor uses) when available; otherwise a
    deterministic templated summary.

Everything here is LAZY, GATED, and BEST-EFFORT by design, so the core Record->Decide->Act pipeline
never depends on these heavy models:
  * heavy imports (sentence_transformers / transformers / torch) happen inside the load functions,
    so importing this module is cheap;
  * models load on the first triage call only;
  * env gates: AI_TRIAGE_ENABLED (default on), AI_TRIAGE_LLM (default on, and only if the Qwen dir
    is present — e.g. it is NOT shipped in the RedMap container, so triage there is RAG + templated).
  A failure in retrieval or generation degrades to the templated summary rather than raising.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
QWEN_PATH = BASE_DIR / "models" / "qwen2.5-1.5b-instruct"
EMBED_PATH = BASE_DIR / "models" / "regmap-embedder"
CORPUS_CSV = BASE_DIR / "data" / "processed" / "training_pairs.csv"

TRIAGE_ENABLED = os.environ.get("AI_TRIAGE_ENABLED", "1").lower() not in ("0", "false", "")
LLM_ENABLED = (os.environ.get("AI_TRIAGE_LLM", "1").lower() not in ("0", "false", "")
               and QWEN_PATH.exists())
TOP_K = int(os.environ.get("AI_TRIAGE_TOPK", "3"))

# lazy singletons
_embedder = None
_corpus = None
_corpus_emb = None
_llm = None
_tok = None


def _load_retriever():
    global _embedder, _corpus, _corpus_emb
    if _embedder is not None:
        return
    import pandas as pd
    from sentence_transformers import SentenceTransformer
    _embedder = SentenceTransformer(str(EMBED_PATH))
    df = pd.read_csv(CORPUS_CSV)
    _corpus = df["hipaa_text"].dropna().unique().tolist()
    _corpus_emb = _embedder.encode(_corpus, convert_to_tensor=True)


def _retrieve(query: str, k: int = TOP_K) -> list[dict]:
    _load_retriever()
    import torch
    qe = _embedder.encode(query, convert_to_tensor=True)
    scores = torch.nn.functional.cosine_similarity(qe, _corpus_emb)
    idx = torch.topk(scores, k=min(k, len(_corpus))).indices.tolist()
    return [{"provision": _corpus[i][:240], "score": round(float(scores[i]), 4)} for i in idx]


def _load_llm():
    global _llm, _tok
    if _llm is not None:
        return
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    _tok = AutoTokenizer.from_pretrained(str(QWEN_PATH))
    _llm = AutoModelForCausalLM.from_pretrained(str(QWEN_PATH), dtype=torch.float32)
    _llm.eval()


def _generate(messages, max_new_tokens: int = 160) -> str:
    import torch
    _load_llm()
    text = _tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
    inputs = _tok(text, return_tensors="pt")
    with torch.no_grad():
        out = _llm.generate(**inputs, max_new_tokens=max_new_tokens, do_sample=False)
    return _tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()


def _reason(alert: dict) -> str:
    d = alert.get("detail") or {}
    if isinstance(d, dict) and d.get("reason"):
        return d["reason"]
    return f"{alert.get('verdict_count')} contributing verdict(s)"


def _query_for(alert: dict) -> str:
    return (f"{alert.get('rule')} {alert.get('model')} "
            f"{alert.get('subject') or ''} {_reason(alert)}").strip()


def _templated_summary(alert: dict, context: list[dict]) -> str:
    prov = context[0]["provision"] if context else "n/a"
    return (f"{str(alert.get('severity', '?')).upper()} {alert.get('rule')} on "
            f"{alert.get('model')}/{alert.get('subject')}: {_reason(alert)}. "
            f"Most relevant control context: {prov}")


def triage(alert: dict) -> dict:
    if not (TRIAGE_ENABLED and alert):
        return {"enabled": False, "summary": None, "related_controls": [], "llm_used": False}

    try:
        context = _retrieve(_query_for(alert))
    except Exception:
        context = []

    summary, llm_used = None, False
    if LLM_ENABLED:
        try:
            ctx_block = "\n".join(f"- {c['provision']}" for c in context) or "- (none)"
            messages = [
                {"role": "system",
                 "content": ("You are a SOC analyst assistant. Given a security alert and the "
                             "related compliance controls, write a concise 2-3 sentence triage: "
                             "what happened, why it matters, and a recommended next action. Be "
                             "specific and factual; do not invent details.")},
                {"role": "user",
                 "content": (f"ALERT: {_templated_summary(alert, context)}\n\n"
                             f"RELATED COMPLIANCE CONTROLS:\n{ctx_block}")},
            ]
            summary = _generate(messages)
            llm_used = bool(summary)
        except Exception:
            summary, llm_used = None, False

    if not summary:
        summary = _templated_summary(alert, context)

    return {"enabled": True, "summary": summary, "related_controls": context, "llm_used": llm_used}
