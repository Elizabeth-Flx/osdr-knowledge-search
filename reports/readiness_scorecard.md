# AI readiness scorecard

OSDR study metadata, Tier 1 fields (13 columns), 576 studies, collected 2026-11-10 from the OSDR search API.
Numbers come from `notebooks/readiness_scorecard.ipynb`.

| | Rating | Why | What would help |
|---|---|---|---|
| Completeness | ok | Material Type missing in 15% of studies. After cleaning only 10 of 322 spaceflight studies have no flight platform, but 4 organisms, 11 space programs and 24 flight platforms had to be added by hand or from mission names | required fields when submitting a study |
| Consistency | bad | ISS is written 9 different ways (typos like "Internation Space Station", program names). Project Type has 11 labels for 5 types. 8 studies only have funders or vehicles under Space Program | controlled vocabularies |
| Validity | ok | release dates are Unix timestamps stored as text, 14 of them are 0 (1970) | proper dates, empty instead of 0 |
| Structure | bad | lists are stored as text with 2+ spaces between values (72% of Study Factor Name). Space and Flight Program use , ; and "and", which also appear inside names | store lists as lists |
| Uniqueness | ok | 1 duplicate (OSD-729 is in the index twice with different release dates) | |
| Text quality | good | descriptions have a median of 192 words, only 18 are under 20 words | |

Overall: the titles and descriptions are good enough for semantic search as they are. The other fields work as filters after cleaning, but not for training models on them (Material Type still has 183 different values).
