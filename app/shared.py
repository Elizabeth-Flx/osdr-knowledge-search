import re
from pathlib import Path

import faiss
import numpy as np
import pandas as pd
from rank_bm25 import BM25Okapi
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


def tokenize(text):
    # lowercase words, keep hyphenated terms like osd-48, trp53-null, rna-seq together
    return re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", text.lower())


# bm25: one document per study with title + metadata + full description (no length limit like the model)
TEXT_COLUMNS = ["organism_list", "material_types", "assay_technology", "factors", "missions"]
docs = (studies["Accession"] + " " + studies["Study Title"] + " " + studies["Study Description"].fillna("") + " "
        + studies[TEXT_COLUMNS].apply(lambda r: " ".join(" ".join(as_list(v)) for v in r), axis=1))
bm25 = BM25Okapi([tokenize(d) for d in docs])


def bm25_scores(query):
    return pd.Series(bm25.get_scores(tokenize(query)), index=studies["Accession"])


def semantic_scores(query):
    # score all chunks (the index is small), then keep the best chunk per study
    query_vec = model.encode([query], normalize_embeddings=True)
    scores, ids = index.search(query_vec, index.ntotal)
    hits = chunks.iloc[ids[0]].assign(score=scores[0])
    return hits.groupby("Accession")["score"].max()


def hybrid_scores(query, k=60):
    # reciprocal rank fusion: combine the ranks, the two scores aren't on the same scale
    sem = semantic_scores(query).rank(ascending=False)
    kw = bm25_scores(query).rank(ascending=False)
    return 1 / (k + sem) + 1 / (k + kw)


SCORERS = {"semantic": semantic_scores, "keyword": bm25_scores, "hybrid": hybrid_scores}


def search(query, filters=None, mode="hybrid", k=100):
    # studies that pass all filters (no selection = no filter)
    keep = pd.Series(True, index=studies.index)
    for column, selected in (filters or {}).items():
        if selected:
            keep &= matches(column, selected)
    allowed = studies.loc[keep, "Accession"]

    scores = SCORERS[mode](query)
    scores = scores[scores.index.isin(allowed)]
    if mode == "keyword":
        scores = scores[scores > 0]  # bm25 gives 0 when no query word is in the study

    best = scores.sort_values(ascending=False).head(k).rename("score").reset_index()
    results = best.merge(studies, on="Accession")
    results["score"] = results["score"].astype(float).round(4)  # faiss gives float32, that rounds badly

    # list columns -> text for showing in the app
    LIST_COLUMNS = {"organism_list": "organism", "material_types": "material", "assay_technology": "assay",
                    "factors": "factors", "missions": "missions", "space_agencies": "space agency",
                    "flight_platforms": "flight platform"}
    for column, name in LIST_COLUMNS.items():
        results[name] = results[column].map(lambda v: ", ".join(as_list(v)))
    results["release date"] = results["release_date"].dt.date

    return results[["Accession", "Study Title", "organism", "project_type", "score",
                    "Study Description", *[n for n in LIST_COLUMNS.values() if n != "organism"], "release date"]]
