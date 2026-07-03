import streamlit as st
import pandas as pd
import torch
from pathlib import Path
from sentence_transformers import SentenceTransformer

# ---------- Paths (relative to repo root when launched from there) ----------
MODEL_PATH = Path(__file__).parent.parent / 'models' / 'regmap-embedder'
CORPUS_CSV = Path(__file__).parent.parent / 'data' / 'raw' / 'nist_800_53_rev5_hipaa_crosswalk_full.csv'

EXAMPLE_QUERIES = [
    "Develop, document, and disseminate access control policies and procedures.",
    "Enforce approved authorizations for logical access to information and system resources.",
    "Employ the principle of least privilege, allowing only authorized accesses necessary to accomplish assigned tasks.",
    "Identify and authenticate users, processes, or devices before allowing access to the system.",
    "Audit and review system activity to detect unauthorized access or anomalies.",
]

# ---------- Loaders ----------
@st.cache_resource(show_spinner="Loading model...")
def load_model():
    try:
        return SentenceTransformer(str(MODEL_PATH), local_files_only=True)
    except Exception:
        return SentenceTransformer(str(MODEL_PATH))

@st.cache_data(show_spinner="Loading HIPAA corpus...")
def load_corpus():
    df = pd.read_csv(CORPUS_CSV)
    df.columns = (
        df.columns
        .str.replace('\n', ' ', regex=False)
        .str.replace(r'\s+', ' ', regex=True)
        .str.strip()
    )
    df = df.rename(columns={
        'Reference Document Element': 'hipaa_citation',
        'Reference Document Element Description': 'hipaa_text',
    })
    df = df[['hipaa_citation', 'hipaa_text']].dropna()
    df['hipaa_text'] = df['hipaa_text'].astype(str).str.strip()
    df = df.drop_duplicates(subset=['hipaa_citation']).reset_index(drop=True)
    return df

# ---------- Page config ----------
st.set_page_config(
    page_title="RegMap – NIST to HIPAA Mapper",
    page_icon="🔗",
    layout="wide",
)

st.title("🔗 RegMap – Automated NIST‑to‑HIPAA Compliance Mapping")
st.markdown(
    "This tool uses a fine‑tuned **Sentence‑BERT** model to map "
    "NIST SP 800‑53 controls to the most relevant HIPAA Security Rule citations."
)
st.divider()

# ---------- Load ----------
model = load_model()
corpus_df = load_corpus()
corpus_embeddings = model.encode(corpus_df['hipaa_text'].tolist(), convert_to_tensor=True)

# ---------- Input ----------
col1, col2 = st.columns([2, 1])

with col1:
    query = st.text_area(
        "Enter a NIST SP 800‑53 control description:",
        height=120,
        placeholder="Paste or type a control description here...",
    )

with col2:
    st.markdown("**Or pick an example:**")
    for ex in EXAMPLE_QUERIES:
        if st.button(ex[:60] + "...", key=ex):
            query = ex

# ---------- Search ----------
if st.button("Find HIPAA Mappings", type="primary", disabled=not query.strip()):
    with st.spinner("Searching..."):
        query_embed = model.encode(query.strip(), convert_to_tensor=True)
        cos_scores = torch.nn.functional.cosine_similarity(query_embed, corpus_embeddings)
        top5 = torch.topk(cos_scores, k=min(5, len(corpus_df)))

    st.subheader("Top 5 HIPAA Matches")
    for rank, (score, idx) in enumerate(zip(top5.values, top5.indices), start=1):
        row = corpus_df.iloc[idx.item()]
        with st.expander(f"#{rank}  ·  {row['hipaa_citation']}  ·  Score: {score.item():.4f}"):
            st.write(row['hipaa_text'])

    st.caption(
        f"Model: all-MiniLM-L6-v2 fine‑tuned on {len(corpus_df)} NIST‑HIPAA pairs  "
        f"· Recall@5 = 0.735 on held‑out test set"
    )
