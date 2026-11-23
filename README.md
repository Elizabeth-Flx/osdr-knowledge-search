# OSDR Knowledge Search

Search NASA's [Open Science Data Repository (OSDR)](https://osdr.nasa.gov/bio/) by meaning, not only by keyword. The project collects the metadata of 576 space biology studies, cleans and harmonises it, rates how ready the metadata is for AI use, and puts it behind a small web app with semantic, keyword and hybrid search.

Example: *"bone loss in microgravity"* also finds studies that talk about "skeletal deterioration during spaceflight", and *"OSD-48"* or *"Trp53"* still find the exact study or gene.

## Features

- **Hybrid search**: sentence embeddings (`all-MiniLM-L6-v2` + FAISS) combined with BM25 keyword ranking through reciprocal rank fusion. Each mode can also be used on its own.
- **Filters** for organism group, project type, space agency, flight platform and assay technology (multi-select).
- **Details panel**: click a result to see its metadata and full description, with a link to the study on OSDR.
- **AI-readiness scorecard** for the OSDR metadata: [reports/readiness_scorecard.md](reports/readiness_scorecard.md).

## Quick start

The collected data and the search index are included in the repository, so the app runs without re-downloading anything.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

shiny run --launch-browser app/app.py
```

The first start downloads the embedding model (~90 MB) and takes a few seconds.

## Pipeline

| Step | File | Output |
|---|---|---|
| 1. Collect study metadata from the OSDR search API | [src/collect_studies.py](src/collect_studies.py) | `data/raw/*.json`, `data/clean/studies_raw.parquet` |
| 2. Explore the data and select the Tier 1 fields | [notebooks/data_eda.ipynb](notebooks/data_eda.ipynb) | `data/clean/studies_subset_t1.parquet` |
| 3. Clean and harmonise the fields | [notebooks/data_cleanup.ipynb](notebooks/data_cleanup.ipynb) | `data/clean/studies_subset_t1_cleaned.parquet` |
| 4. Rate the AI-readiness of the metadata | [notebooks/readiness_scorecard.ipynb](notebooks/readiness_scorecard.ipynb) | [reports/readiness_scorecard.md](reports/readiness_scorecard.md) |
| 5. Build the embedding index | [src/create_index.py](src/create_index.py) | `data/index/` |
| 6. Search app | [app/app.py](app/app.py), [app/shared.py](app/shared.py) | |

To rebuild everything from scratch, delete `data/raw/` and run the steps in order. Scripts are run from the project root (`python src/collect_studies.py`), the notebooks from `notebooks/`.

## Data cleaning

The OSDR metadata is rich but inconsistent. The main problems and what the cleanup does about them:

- **Multi-valued fields stored as text.** Organisms, assays, factors and missions are packed into one string, separated by two or more spaces (or `,` `;` `and` in some fields). They are split into real lists.
- **Many spellings for the same thing.** The ISS appears as 9 different raw values (typos like "Internation Space Station", abbreviations, program names), project type has 11 labels for 5 types. Mapping dicts in the cleanup notebook reduce these to one name each; anything not in a map is printed, so new spellings don't get lost.
- **Wrong field.** Space Program mixes space agencies with funders (NIH, NSF) and vehicles (Space Shuttle). Only agencies are kept.
- **Missing values.** Organisms, space agencies and flight platforms are recovered by hand where the description or another field makes them clear, and flight platforms are inferred from mission names (e.g. SpaceX-21 → ISS). Every recovered value is marked in a `*_source` column.
- **Placeholders.** Release dates of `0` (1970) become missing; "Not Applicable" is removed.
- **One duplicate study** (OSD-729, indexed twice by OSDR with different release dates).

## How the search works

**Semantic.** The embedding model only reads 256 tokens, but 72% of the study texts are longer. Each description is therefore split into chunks of 128 words (16 words overlap), and every chunk starts with the study title and a metadata header (organism, material, assay, factors, missions). This gives 1,184 chunks for 576 studies. A study's score is the cosine similarity of its best-matching chunk.

**Keyword.** BM25 over one document per study (accession, title, full description and metadata). The tokenizer keeps hyphenated terms such as `osd-48`, `trp53-null` or `rna-seq` together, which is where keyword search beats embeddings.

**Hybrid** (default). Both rankings are combined with reciprocal rank fusion, `1 / (60 + rank_semantic) + 1 / (60 + rank_bm25)`, since the two scores are on different scales.

Filters are applied before ranking, so a narrow filter still returns all matching studies. The score column is only comparable within one search and one mode.

## AI-readiness scorecard

Summary of [reports/readiness_scorecard.md](reports/readiness_scorecard.md):

| | Rating |
|---|---|
| Completeness | ok |
| Consistency | bad |
| Validity | ok |
| Structure | bad |
| Uniqueness | ok |
| Text quality | good |

The titles and descriptions are ready for semantic search as they are (median description length: 192 words). The structured fields need harmonisation before they can be used as filters, and are not ready for ML on structured labels without further cleaning. The main fix on the data side would be controlled vocabularies and real list fields at submission time.

## Project structure

```
app/          Shiny web app (app.py: UI, shared.py: data loading and search)
data/raw/     cached API responses
data/clean/   raw, Tier 1 and cleaned study tables (parquet)
data/index/   FAISS index, embeddings and chunk table
notebooks/    exploration, cleanup and readiness scorecard
reports/      generated scorecard
src/          data collection and index building
```

## Limitations and next steps

- **Evaluation**: the three search modes have not been formally compared yet. Next step is a set of 15–20 test questions with known relevant studies.
- Only OSDR's own studies (`cgene`) are included, not linked GEO or PRIDE datasets.
- About a third of the chunks are still longer than the model's 256-token limit and lose their last few words (scientific text needs more tokens per word than expected). A smaller chunk size reduces this, at the cost of more chunks.
- No stemming in BM25, so "mice" does not match "mouse" in keyword mode (the semantic part covers this in hybrid mode).
- Material Type is only lightly cleaned (183 distinct values); tissues are not grouped yet.

## Data source

Study metadata from the [NASA Open Science Data Repository](https://osdr.nasa.gov/bio/), collected on 2026-11-10 through its public search API.
