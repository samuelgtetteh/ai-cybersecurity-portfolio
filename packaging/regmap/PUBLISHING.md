# Publishing the RegMap model

The release is built by `scripts/make_regmap_release.py` into `dist/regmap-embedder/`
(self-contained: model + `README.md` model card + `LICENSE` + `hipaa_corpus.csv` +
`regmap_map.py` + `example.py`) and `dist/regmap-embedder-release.zip`.

Build it:
```bash
venv/Scripts/python.exe scripts/make_regmap_release.py
```

## Option A — Hugging Face Hub (recommended; requires YOUR HF account/token)
```bash
pip install -U huggingface_hub
huggingface-cli login                       # paste your HF write token
huggingface-cli upload <your-username>/regmap-embedder dist/regmap-embedder . --repo-type model
```
Then anyone can use it:
```python
from sentence_transformers import SentenceTransformer
m = SentenceTransformer("<your-username>/regmap-embedder")
```
(The model card `README.md` renders automatically on the model page.)

> The push needs your credentials, so this step is done by you — nothing is uploaded on your behalf.

## Option B — Zip / GitHub Release (no account needed)
Distribute `dist/regmap-embedder-release.zip`. A user unzips and runs:
```bash
pip install -r requirements.txt
python example.py
# or
python regmap_map.py "Enforce multi-factor authentication for remote access."
```

## Notes
- License: Apache-2.0 (matches the base model `all-MiniLM-L6-v2`).
- `dist/` is git-ignored (the model already lives in `models/regmap-embedder`); the release is
  reproducible from this repo, so it isn't committed.
