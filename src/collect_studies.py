import json
import time
from pathlib import Path

import pandas as pd
import requests

SEARCH_URL = "https://osdr.nasa.gov/osdr/data/search"
PAGE_SIZE = 100          # results per request
SOURCE_TYPE = "cgene"    # OSDR's own studies (excludes GEO, PRIDE etc.)
RAW_DIR = Path("data/raw")
CLEAN_DIR = Path("data/clean")


def fetch_page(page: int) -> dict:
    """Fetch one page of search results, using a local cache if present."""
    cache_file = RAW_DIR / f"search_page_{page:03d}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())

    params = {
        "type": SOURCE_TYPE,
        "size": PAGE_SIZE,
        "from": page * PAGE_SIZE,   # offset; see check in main() if this is wrong
    }
    for attempt in range(3):
        try:
            r = requests.get(SEARCH_URL, params=params, timeout=60)
            r.raise_for_status()
            data = r.json()
            cache_file.write_text(json.dumps(data))
            return data
        except requests.RequestException as e:
            print(f"  page {page}, attempt {attempt + 1} failed: {e}")
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"Could not fetch page {page}")


def extract_hits(data: dict) -> tuple[list[dict], int | None]:
    """Return (list of study records, total count) from a search response."""
    hits = data.get("hits", {})
    total = hits.get("total")
    if isinstance(total, dict):          # Elasticsearch style {"value": n}
        total = total.get("value")
    records = []
    for h in hits.get("hits", []):
        rec = dict(h.get("_source", {}))
        rec["_id"] = h.get("_id")
        records.append(rec)
    return records, total


def main():
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    CLEAN_DIR.mkdir(parents=True, exist_ok=True)

    all_records, seen_ids = [], set()
    total, page = None, 0
    while True:
        data = fetch_page(page)
        records, page_total = extract_hits(data)
        total = total or page_total
        new = [r for r in records if r["_id"] not in seen_ids]
        if not new:
            break
        seen_ids.update(r["_id"] for r in new)
        all_records.extend(new)
        print(f"page {page}: {len(new)} new studies (total so far {len(all_records)} / {total})")
        page += 1
        time.sleep(0.5)  # be polite to the API

    if total and len(all_records) < total:
        print(f"WARNING: collected {len(all_records)} of {total} studies. "
              "The 'from' parameter may be a page number rather than an offset; "
              "try 'from': page instead of page * PAGE_SIZE.")

    df = pd.json_normalize(all_records)
    # list/dict cells can't be stored directly in parquet -> keep them as JSON strings
    for col in df.columns:
        if df[col].map(lambda v: isinstance(v, (list, dict))).any():
            df[col] = df[col].map(lambda v: json.dumps(v) if isinstance(v, (list, dict)) else v)
        # mixed numbers/strings in one column break parquet -> store as text for now
        if df[col].dtype == object:
            df[col] = df[col].astype("string")

    out = CLEAN_DIR / "studies_raw.parquet"
    df.to_parquet(out, index=False)
    print(f"\nSaved {len(df)} studies with {df.shape[1]} fields to {out}")
    print("\nFields (non-missing share):")
    print(df.notna().mean().sort_values(ascending=False).round(2).to_string())


if __name__ == "__main__":
    main()