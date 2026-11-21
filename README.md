# Beyond Room Type

AIAA3111 Introduction to Data Mining · Group 3

This project compares two ways to segment Hong Kong Airbnb supply. Under listing weighting each listing has weight 1. Under account weighting each listing has weight `1 / n`, where `n` is the number of listings from that account in the snapshot. The main comparison uses the same input features and three clusters. Prices and geography are used to interpret the clusters after fitting.

## Setup

Use Python 3.12. Run these commands from the repository root.

```sh
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

Download the fixed Hong Kong snapshots and district boundaries from [Inside Airbnb](https://insideairbnb.com/get-the-data/).

```sh
mkdir -p data
curl -fL 'https://data.insideairbnb.com/china/hk/hong-kong/2026-09-20/data/listings.csv.gz' \
  -o data/hong-kong-2026-09-20-listings.csv.gz
curl -fL 'https://data.insideairbnb.com/china/hk/hong-kong/2026-06-27/data/listings.csv.gz' \
  -o data/hong-kong-2026-06-27-listings.csv.gz
curl -fL 'https://data.insideairbnb.com/china/hk/hong-kong/2026-09-20/visualisations/neighbourhoods.geojson' \
  -o data/hong-kong-2026-09-20-neighbourhoods.geojson
```

The September snapshot contains 6,614 listings. The June snapshot contains 6,734. Inside Airbnb releases the datasets under CC BY 4.0. The dates in the paths identify the downloads and can differ from the per-listing scrape dates.

## Run the analyses

```sh
sept=data/hong-kong-2026-09-20-listings.csv.gz
june=data/hong-kong-2026-06-27-listings.csv.gz
geo=data/hong-kong-2026-09-20-neighbourhoods.geojson
results=experiments/2026-11-19

python scripts/kmeans_baseline.py --listings "$sept" --output "$results"

python scripts/market_checks.py --listings "$sept" --baseline "$results" \
  --geojson "$geo" --earlier "$june" --output "$results/market_checks"

python scripts/account_sensitivity.py --listings "$sept" --baseline "$results" \
  --output "$results/market_checks"

python scripts/mixed_type_check.py --listings "$sept" --output "$results/market_checks"

followups=experiments/2026-11-21
python scripts/followup_checks.py --listings "$sept" --baseline "$results" \
  --geojson "$geo" --output "$followups"

python scripts/render_poster.py --followups "$followups" \
  --pdf poster/Group3_Poster_Updated.pdf --preview poster/Group3_Poster_Updated.png
```

| Script | Outputs |
| --- | --- |
| `kmeans_baseline.py` | K-Means sweep over `k=2–8`, listing labels, cluster profiles, and price coverage |
| `market_checks.py` | Ward and GMM comparisons, feature ablations, host stability, June-to-September transfer, within-room-type prices, and district maps |
| `account_sensitivity.py` | Account-weight sweep, cluster flows, and price comparisons on held-out host accounts |
| `mixed_type_check.py` | K-prototypes comparisons with three categorical cost weights and two account-weighting settings |
| `followup_checks.py` | Minimum-stay ablation at `k=3,4` with fixed scaling, paired maps for fixed C2 with 2,000 account-bootstrap draws, and a reproducible 45-night shortlist example |
| `render_poster.py` | A vector PDF at 80 × 100 cm and a PNG preview in `poster/` |

The two experiment folders record the input hashes and settings. `run.json` also logs the feature blocks and library versions. Input snapshots and generated artifacts are local to each checkout.

## Product direction

The intended audience is visiting students and interns comparing districts for a 4–12 week stay in Hong Kong. A district shortlisting tool would filter historical listings by stay length, budget, occupancy and required amenities, then show the number of matching listings, distinct host accounts and the observed price range. Listing counts and account counts answer different questions about the same pool of matches. Exact quotes and availability are checked separately at booking time.
