from pathlib import Path
import numpy as np
import pandas as pd
import faiss
from sentence_transformers import SentenceTransformer

# paths relative to the project root, so the script works from any folder
ROOT = Path(__file__).resolve().parent.parent
CLEAN = ROOT / "data/clean/studies_subset_t1_cleaned.parquet"
OUT = ROOT / "data/index"; OUT.mkdir(parents=True, exist_ok=True)
MODEL = "all-MiniLM-L6-v2"

df = pd.read_parquet(CLEAN)

def list_str(v):
    # parquet gives list columns back as numpy arrays
    return ", ".join(v) if isinstance(v, (list, tuple, np.ndarray)) and len(v) else ""

# the model only reads 256 tokens, most descriptions are longer
# -> split the description into chunks, every chunk gets the title + header in front
CHUNK_WORDS = 128   # ~150 tokens, leaves room for title + header
OVERLAP = 16        # words shared between chunks so sentences aren't cut in half

def build_header(r):
    return "; ".join(f"{label}: {val}" for label, val in [
        ("Organism", list_str(r["organism_list"])),
        ("Material", list_str(r["material_types"])),
        ("Assay", list_str(r["assay_measurement"])),
        ("Technology", list_str(r["assay_technology"])),
        ("Factors", list_str(r["factors"])),
        ("Mission", list_str(r["missions"])),
    ] if val)

def split_words(text, size=CHUNK_WORDS, overlap=OVERLAP):
    words = (text or "").split()
    if not words:
        return [""]
    step = size - overlap
    return [" ".join(words[i:i + size]) for i in range(0, max(len(words) - overlap, 1), step)]

chunks = []
for _, r in df.iterrows():
    prefix = f"{r['Study Title']}. {build_header(r)}."
    for n, part in enumerate(split_words(r["Study Description"])):
        chunks.append({"Accession": r["Accession"], "chunk": n, "text": f"{prefix} {part}"})
chunks = pd.DataFrame(chunks)

model = SentenceTransformer(MODEL)

# check how many chunks are still longer than the model can read
n_tokens = chunks["text"].map(lambda t: len(model.tokenizer(t)["input_ids"]))
print(f"{len(chunks)} chunks for {len(df)} studies, "
      f"{(n_tokens > model.max_seq_length).sum()} still over {model.max_seq_length} tokens")

emb = model.encode(chunks["text"].tolist(), batch_size=32, show_progress_bar=True,
                   normalize_embeddings=True).astype("float32")

index = faiss.IndexFlatIP(emb.shape[1])   # inner product = cosine on normalized vectors
index.add(emb)

faiss.write_index(index, str(OUT / "studies.faiss"))
np.save(OUT / "embeddings.npy", emb)
# row i in the index = row i here, search results map back to a study through Accession
chunks.to_parquet(OUT / "chunks.parquet", index=False)
print(f"indexed {index.ntotal} chunks with {MODEL}")