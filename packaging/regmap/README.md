---
license: apache-2.0
base_model: sentence-transformers/all-MiniLM-L6-v2
library_name: sentence-transformers
pipeline_tag: sentence-similarity
tags:
- sentence-transformers
- sentence-similarity
- feature-extraction
- compliance
- nist-800-53
- hipaa
- cybersecurity
---

# RegMap — NIST SP 800-53 → HIPAA Security Rule mapping model

**RegMap** is a fine-tuned sentence-embedding model that maps a **NIST SP 800-53** security control
to the most relevant **HIPAA Security Rule** provisions. Given a control description, it retrieves
the HIPAA citations whose meaning is closest — helping compliance teams cross-walk a NIST-based
control set onto HIPAA without manual, line-by-line mapping.

- **Base model:** `sentence-transformers/all-MiniLM-L6-v2` (6-layer MiniLM, 384-dim embeddings)
- **Fine-tuning:** `MultipleNegativesRankingLoss` on curated NIST↔HIPAA control/provision pairs
- **Task:** semantic retrieval (embed a control, cosine-rank against the HIPAA corpus, return top-k)

## Intended use — an *assistive* retriever, not an authoritative classifier
RegMap returns the **top-k most similar HIPAA provisions** for a human to review and confirm. It is
designed to accelerate an expert's mapping work, not to make a final compliance determination on its
own. Always have a qualified person verify the suggested citations.

## How to use

### Quick start (bundled wrapper — includes the HIPAA corpus)
```bash
pip install -r requirements.txt
python example.py
# or:
python regmap_map.py "Enforce multi-factor authentication for remote access."
```
```python
from regmap_map import map_control
for r in map_control("Employ integrity verification tools to detect unauthorized changes.", top_k=5):
    print(f"{r['score']:.3f}  {r['hipaa_citation']}")
```

### Use the raw embedder (sentence-transformers)
```python
from sentence_transformers import SentenceTransformer, util
m = SentenceTransformer("path/to/regmap-embedder")
q = m.encode("The organization enforces multi-factor authentication for remote access.",
             convert_to_tensor=True, normalize_embeddings=True)
# encode your HIPAA provision texts and cosine-rank against q
```

## Evaluation
Measured on a held-out set of positive NIST↔HIPAA pairs (small, domain-specific dataset):

| Metric | Value |
|---|---|
| Recall@1 | 0.265 |
| Recall@3 | 0.559 |
| Recall@5 | 0.735 |
| MRR | 0.463 |
| Positive pairs | 222 |

Read this as: the correct HIPAA provision is in the **top-5 about 74%** of the time — appropriate
for a top-k assistive tool where a human confirms the result. Top-1 accuracy is modest (~26%), so it
should **not** be used as a single-answer classifier.

## Training data
Curated NIST SP 800-53 control texts paired with HIPAA Security Rule provisions (`hipaa_citation` +
`hipaa_text`). The bundled `hipaa_corpus.csv` is the HIPAA provision corpus used for retrieval.

## Limitations
- Small, HIPAA-specific training set → best treated as an assistive top-k retriever.
- Covers the HIPAA Security Rule provisions in the bundled corpus; other frameworks (PCI, GDPR)
  are out of scope for this release.
- Semantic similarity ≠ legal equivalence; a suggested citation still needs expert confirmation.

## License
Apache-2.0 (inherited from the base model `all-MiniLM-L6-v2`). See `LICENSE`.

## Citation
Tetteh, S. G. *RegMap: Semantic mapping of NIST SP 800-53 controls to HIPAA Security Rule
provisions.* Jarvis College of Computing and Digital Media, DePaul University.

If you use this model, please cite the RegMap work above.
