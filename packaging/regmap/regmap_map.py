"""
RegMap inference wrapper — map a NIST SP 800-53 control to the most relevant HIPAA Security Rule
provisions. Loads the bundled fine-tuned embedder + the bundled HIPAA corpus and returns the top-k
citations by cosine similarity.

Usage:
    from regmap_map import map_control
    map_control("Enforce multi-factor authentication for remote access.", top_k=5)

    # or from the command line:
    python regmap_map.py "Employ integrity verification tools to detect unauthorized changes."

This file lives inside the model directory, so the model, this wrapper, and hipaa_corpus.csv all
sit together and the package works out of the box.
"""
import csv
import json
import os
import sys
from functools import lru_cache

_HERE = os.path.dirname(os.path.abspath(__file__))
_CORPUS = os.path.join(_HERE, "hipaa_corpus.csv")


@lru_cache(maxsize=1)
def _load():
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(_HERE)          # model files are in this directory
    citations, texts = [], []
    with open(_CORPUS, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("hipaa_text"):
                citations.append(row.get("hipaa_citation", ""))
                texts.append(row["hipaa_text"])
    emb = model.encode(texts, convert_to_tensor=True, normalize_embeddings=True)
    return model, citations, texts, emb


def map_control(control_text: str, top_k: int = 5):
    """Return the top-k HIPAA provisions for a NIST control description:
    [{"hipaa_citation", "hipaa_text", "score"}], most similar first."""
    from sentence_transformers import util
    import torch
    model, citations, texts, emb = _load()
    q = model.encode(control_text.strip(), convert_to_tensor=True, normalize_embeddings=True)
    scores = util.cos_sim(q, emb)[0]
    k = min(top_k, len(citations))
    idx = torch.topk(scores, k=k).indices.tolist()
    return [{"hipaa_citation": citations[i], "hipaa_text": texts[i],
             "score": round(float(scores[i]), 4)} for i in idx]


if __name__ == "__main__":
    query = " ".join(sys.argv[1:]) or "Enforce multi-factor authentication for remote access."
    print(json.dumps(map_control(query), indent=2))
