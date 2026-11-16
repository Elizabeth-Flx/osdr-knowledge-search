from pathlib import Path

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer

ROOT = Path(__file__).parent.parent
INDEX = ROOT / "data/index"

# load everything once when the app starts
model = SentenceTransformer("all-MiniLM-L6-v2")
index = faiss.read_index(str(INDEX / "studies.faiss"))
chunks = pd.read_parquet(INDEX / "chunks.parquet")  # row i = vector i in the index
studies = pd.read_parquet(ROOT / "data/clean/studies_subset_t1_cleaned.parquet")

# filter id -> (label, column)
FILTERS = {
    "organism_group": ("Organism group", "organism_group"),
    "project_type": ("Project type", "project_type"),
    "space_agency": ("Space agency", "space_agencies"),
    "flight_platform": ("Flight platform", "flight_platforms"),
    "assay": ("Assay technology", "assay_technology"),
}


def as_list(v):
    # list columns come back from parquet as numpy arrays, project_type is a plain string
    if isinstance(v, (list, np.ndarray)):
        return list(v)
    return [] if pd.isna(v) else [v]


def filter_choices(column):
    return sorted(studies[column].map(as_list).explode().dropna().unique())


def matches(column, selected):
    # a study matches if it has at least one of the selected values
    return studies[column].map(lambda v: bool(set(as_list(v)) & set(selected)))


def search(query, filters=None, k=100):
    # studies that pass all filters (no selection = no filter)
    keep = pd.Series(True, index=studies.index)
    for column, selected in (filters or {}).items():
        if selected:
            keep &= matches(column, selected)
    allowed = studies[keep]

    # score all chunks (the index is small), filters could remove most of the top hits otherwise
    query_vec = model.encode([query], normalize_embeddings=True)
    scores, ids = index.search(query_vec, index.ntotal)

    # keep the best chunk per study
    hits = chunks.iloc[ids[0]].assign(score=scores[0])
    hits = hits[hits["Accession"].isin(allowed["Accession"])]
    best = hits.sort_values("score", ascending=False).drop_duplicates("Accession").head(k)

    results = best.merge(studies, on="Accession")
    results["organism"] = results["organism_list"].map(", ".join)
    results["score"] = results["score"].round(3)
    return results[["Accession", "Study Title", "Study Description", "organism", "project_type", "score"]]
