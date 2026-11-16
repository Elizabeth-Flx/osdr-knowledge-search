from pathlib import Path

import faiss
import pandas as pd
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).parent.parent
INDEX = ROOT / "data/index"

# load everything once when the app starts
model = SentenceTransformer("all-MiniLM-L6-v2")
index = faiss.read_index(str(INDEX / "studies.faiss"))
chunks = pd.read_parquet(INDEX / "chunks.parquet")  # row i = vector i in the index
studies = pd.read_parquet(ROOT / "data/clean/studies_subset_t1_cleaned.parquet")


def search(query, k=10):
    query_vec = model.encode([query], normalize_embeddings=True)
    scores, ids = index.search(query_vec, k * 5)  # more chunks than needed, a study can match several times

    # keep the best chunk per study
    hits = chunks.iloc[ids[0]].assign(score=scores[0])
    best = hits.sort_values("score", ascending=False).drop_duplicates("Accession").head(k)

    results = best.merge(studies, on="Accession")
    results["organism"] = results["organism_list"].map(", ".join)
    results["score"] = results["score"].round(3)
    return results[["Accession", "Study Title", "organism", "project_type", "score"]]
