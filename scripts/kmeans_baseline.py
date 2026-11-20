"""Explore Hong Kong Airbnb listing clusters with K-Means, k=2 through 8."""

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.cluster import KMeans
from sklearn.metrics import (
    adjusted_rand_score,
    davies_bouldin_score,
    normalized_mutual_info_score,
    silhouette_score,
)
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

SEED = 3111
K_VALUES = range(2, 9)
ROOM_TYPES = ("Private room", "Entire home/apt", "Shared room", "Hotel room")
AMENITIES = {
    "Kitchen": ("kitchen",),
    "Washer": ("washer",),
    "Elevator": ("elevator",),
    "Workspace": ("dedicated workspace",),
    "Refrigerator": ("refrigerator",),
    "TV": ("tv",),
    "Dryer": ("dryer",),
    "Self check-in": ("self check-in", "lockbox", "keypad", "smart lock"),
}
NUMERIC = ("accommodates", "bedrooms", "minimum_nights")
RESAMPLES = 20
CLUSTER_COLORS = ("#287b8e", "#d77535", "#6556a4", "#637f42", "#a44c76",
                  "#917140", "#66748b", "#387b63")


def load_listings(path):
    columns = ["id", "host_id", "last_scraped", "room_type", "source",
               "neighbourhood_cleansed", "property_type", "price", "amenities",
               "calculated_host_listings_count", *NUMERIC]
    frame = pd.read_csv(path, usecols=columns, dtype={"id": "string", "host_id": "string"})
    if frame["id"].isna().any() or frame["id"].duplicated().any():
        raise ValueError("Listing IDs must be present and unique.")
    if frame["room_type"].isna().any() or set(frame["room_type"]) - set(ROOM_TYPES):
        raise ValueError("Unexpected room types in the snapshot.")
    frame["price_hkd"] = pd.to_numeric(
        frame["price"].str.replace(r"[$,]", "", regex=True), errors="coerce"
    )
    frame.loc[frame["price_hkd"] <= 0, "price_hkd"] = np.nan
    tokens = frame["amenities"].map(lambda value: {item.casefold().strip() for item in json.loads(value)})
    for name, matches in AMENITIES.items():
        frame[name] = tokens.map(lambda items: bool(items.intersection(matches)))
    return frame.sort_values("id").reset_index(drop=True)


def features(frame, blocks, fit_index=None):
    """Fit transformation parameters on fit_index and transform every row."""
    fit_index = slice(None) if fit_index is None else fit_index
    if "numeric" in blocks:
        all_numeric = frame[list(NUMERIC)].astype(float).where(lambda column: column >= 0)
        numeric = all_numeric.fillna(all_numeric.iloc[fit_index].median())
        numeric = np.log1p(numeric)
        limits = numeric.iloc[fit_index].quantile([0.01, 0.99])
        # Rare long minimum-stay rules remain in the profiles, with a bounded impact on distance.
        numeric["minimum_nights"] = numeric["minimum_nights"].clip(
            limits.loc[0.01, "minimum_nights"], limits.loc[0.99, "minimum_nights"]
        )
    encoded = []
    for block in blocks:
        if block == "numeric":
            matrix = StandardScaler().fit(numeric.iloc[fit_index]).transform(numeric)
        elif block == "room":
            matrix = (frame["room_type"].to_numpy()[:, None] == np.array(ROOM_TYPES)).astype(float)
        elif block == "amenities":
            matrix = frame[list(AMENITIES)].to_numpy(dtype=float)
        elif block == "district":
            matrix = pd.get_dummies(frame["neighbourhood_cleansed"], dtype=float).to_numpy()
        elif block == "host_count":
            matrix = np.log1p(frame[["calculated_host_listings_count"]].to_numpy(dtype=float))
        else:
            raise ValueError(f"Unknown feature block: {block}")
        # Squared Euclidean distance between two randomly drawn training rows
        # has expectation 2 * sum of column variances in each block.
        scale = np.sqrt(2.0 * np.var(matrix[fit_index], axis=0).sum())
        if scale > 0:
            encoded.append(matrix / scale)
    if not encoded:
        raise ValueError("At least one feature block with variation is required.")
    return np.column_stack(encoded)


def fit_kmeans(matrix, k, seed=SEED, weights=None):
    return KMeans(n_clusters=k, n_init=20, random_state=seed).fit(matrix, sample_weight=weights)


def order_labels(labels):
    """Give the largest observed group ID 1, then descend by listing count."""
    counts = Counter(labels)
    rank = sorted(counts, key=lambda label: (-counts[label], int(label)))
    mapping = {label: index + 1 for index, label in enumerate(rank)}
    return np.array([mapping[label] for label in labels], dtype=int)


def resample_pairs(frame, host_blocks=False):
    rng = np.random.default_rng(SEED + int(host_blocks))
    if host_blocks:
        hosts = frame["host_id"].unique()
        return [
            np.flatnonzero(frame["host_id"].isin(rng.choice(hosts, int(len(hosts) * 0.8), replace=False)))
            for _ in range(RESAMPLES)
        ]
    return [np.sort(rng.choice(len(frame), int(len(frame) * 0.8), replace=False)) for _ in range(RESAMPLES)]


def stability(frame, blocks, k, reference, pairs):
    sample_labels = [
        fit_kmeans(features(frame, blocks, ix)[ix], k, SEED + j).labels_
        for j, ix in enumerate(pairs)
    ]
    aris = []
    for j in range(0, len(pairs), 2):
        _, i1, i2 = np.intersect1d(pairs[j], pairs[j+1], return_indices=True)
        aris.append(adjusted_rand_score(sample_labels[j][i1], sample_labels[j+1][i2]))
    best_jaccards = {}
    for cluster in np.unique(reference):
        overlap = []
        for ix, labels in zip(pairs, sample_labels):
            mask = reference[ix] == cluster
            if mask.any():
                overlap.append(max(
                    np.count_nonzero(mask & (labels == current)) /
                    np.count_nonzero(mask | (labels == current))
                    for current in np.unique(labels)
                ))
        best_jaccards[int(cluster)] = float(np.median(overlap)) if overlap else np.nan
    return np.quantile(aris, [0.25, 0.5, 0.75]), best_jaccards


def cluster_tables(frame, labels):
    labeled = frame.assign(cluster=labels)
    records, coverage = [], []
    for group, members in labeled.groupby("cluster"):
        room_mix = members["room_type"].value_counts(normalize=True).reindex(ROOM_TYPES, fill_value=0)
        amenities = members[list(AMENITIES)].mean()
        price = members["price_hkd"].dropna()
        hosts = members["host_id"].value_counts()
        records.append({
            "cluster": group, "listings": len(members), "unique_hosts": len(hosts),
            "top_host_share_pct": 100 * hosts.max() / len(members),
            **{f"{r} (%)": 100 * room_mix[r] for r in ROOM_TYPES},
            "Guests (median)": members["accommodates"].median(),
            "Bedrooms (median)": members["bedrooms"].median(),
            "Min. nights (median)": members["minimum_nights"].median(),
            **{f"{a} (%)": 100 * amenities[a] for a in AMENITIES},
        })
        coverage.append({
            "cluster": group, "listings": len(members), "priced": len(price),
            "missing_price": len(members) - len(price), "coverage_pct": 100 * len(price) / len(members),
            "median_hkd": price.median(), "q25_hkd": price.quantile(0.25), "q75_hkd": price.quantile(0.75),
        })
    return pd.DataFrame(records), pd.DataFrame(coverage)


def save_figure(fig, stem):
    fig.savefig(stem.with_suffix(".png"), dpi=180, bbox_inches="tight", facecolor="white")
    fig.savefig(stem.with_suffix(".pdf"), bbox_inches="tight", facecolor="white")
    plt.close(fig)


def plot_profiles(profile, coverage, k, directory):
    percent_fields = [col for col in profile.columns if col.endswith("(%)")]
    numeric_fields = [col for col in profile.columns if col.endswith("(median)")]
    labels = [f"C{int(row.cluster)}  ·  n={int(row.listings):,}" for row in profile.itertuples()]
    fig, (ax, side) = plt.subplots(1, 2, figsize=(14.6, 3.3 + 0.29 * k),
                                 gridspec_kw={"width_ratios": [4, 1.66]})
    tile = ax.imshow(profile[percent_fields], cmap="Blues", vmin=0, vmax=100, aspect="auto")
    ax.set_xticks(range(len(percent_fields)), [name.replace(" (%)", "") for name in percent_fields],
                  rotation=39, ha="right", fontsize=9)
    ax.set_yticks(range(k), labels)
    ax.tick_params(length=0)
    for row, values in enumerate(profile[percent_fields].to_numpy()):
        for col, value in enumerate(values):
            ax.text(col, row, f"{value:.0f}", ha="center", va="center",
                    fontsize=9, color="white" if value > 62 else "#142b43")
    ax.axvline(len(ROOM_TYPES)-0.5, color="white", linewidth=2.6)
    cbar = fig.colorbar(tile, ax=ax, shrink=.84, pad=.02)
    cbar.set_label("Share of cluster (%)")
    ax.set_title("Room type and amenities", loc="left", fontweight="bold", pad=9)
    side.set(xlim=(0, len(numeric_fields)), ylim=(k-.5, -.5), yticks=[])
    side.set_xticks(np.arange(len(numeric_fields))+.5,
                    [name.replace(" (median)", "") for name in numeric_fields], fontsize=9)
    side.tick_params(length=0)
    side.set_title("Cluster medians", loc="left", fontweight="bold", pad=9)
    for row, values in enumerate(profile[numeric_fields].to_numpy()):
        if row % 2 == 0:
            side.axhspan(row-.5, row+.5, color="#e9f0f5", zorder=-1)
        for col, value in enumerate(values):
            side.text(col+.5, row, f"{value:g}", ha="center", va="center", fontsize=10)
    for axis in (ax, side):
        axis.spines[:].set_visible(False)
    fig.suptitle(f"Hong Kong Airbnb  /  K-Means listing profiles, k={k}",
                 x=.08, y=.98, ha="left", va="top", fontsize=18, fontweight="bold", color="#142b43")
    fig.text(.08, .865, f"{profile['listings'].sum():,} listings · Inside Airbnb, Sep 2026 · Price and location held out of clustering",
             va="top", color="#40566c", fontsize=10)
    fig.subplots_adjust(top=.74, bottom=.24, left=.11, right=.96, wspace=.09)
    save_figure(fig, directory / "cluster_profiles")

    fig, ax = plt.subplots(figsize=(8.5, 2.8 + .45*k))
    y = np.arange(k)
    observed = coverage["coverage_pct"]
    ax.barh(y, observed, color="#287b8e", height=.58, label="Price observed")
    ax.barh(y, 100-observed, left=observed, color="#dbe5eb", height=.58, label="Price missing")
    for row, result in enumerate(coverage.itertuples()):
        ax.text(103, row, f"{result.coverage_pct:.1f}%   {result.priced:,}/{result.listings:,}",
                va="center", color="#142b43", fontweight="semibold")
    ax.set(xlim=(0, 128), yticks=y, yticklabels=[f"C{c}" for c in coverage["cluster"]],
           xticks=np.arange(0, 101, 20), xlabel="Share of listings (%)")
    ax.invert_yaxis()
    ax.spines[["top", "right", "left"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), frameon=False, ncol=2)
    fig.suptitle(f"Listing price coverage by cluster  /  k={k}", x=.11, ha="left",
                 fontweight="bold", fontsize=17, color="#142b43")
    fig.subplots_adjust(top=.80)
    save_figure(fig, directory / "price_coverage")


def run(source, output):
    output.mkdir(parents=True, exist_ok=True)
    frame = load_listings(source)
    blocks = ("numeric", "room", "amenities")
    matrix = features(frame, blocks)
    sample = np.sort(np.random.default_rng(SEED).choice(len(frame), min(3000, len(frame)), replace=False))
    pairs = resample_pairs(frame)
    score_rows, profiles, coverage = [], {}, {}
    labels = frame[["id"]].copy()
    for k in K_VALUES:
        model = fit_kmeans(matrix, k)
        labels[f"k{k}"] = assigned = order_labels(model.labels_)
        quartiles, jaccard = stability(frame, blocks, k, assigned, pairs)
        profile, prices = cluster_tables(frame, assigned)
        profiles[k], coverage[k] = profile, prices
        score_rows.append({
            "k": k, "silhouette_fixed_sample": silhouette_score(matrix[sample], assigned[sample]),
            "davies_bouldin_full": davies_bouldin_score(matrix, assigned),
            "stability_ari_q25": quartiles[0], "stability_ari_median": quartiles[1],
            "stability_ari_q75": quartiles[2], "min_cluster_jaccard": min(jaccard.values()),
            "min_cluster_n": int(profile["listings"].min()),
            "room_type_nmi": normalized_mutual_info_score(frame["room_type"], assigned),
        })
        profile.insert(0, "k", k)
        prices.insert(0, "k", k)
        profile["resample_jaccard_median"] = profile["cluster"].map(jaccard)
        print(f"k={k}  silhouette={score_rows[-1]['silhouette_fixed_sample']:.3f}  "
              f"ARI={quartiles[1]:.3f}  min_n={score_rows[-1]['min_cluster_n']}", flush=True)
    scores = pd.DataFrame(score_rows)
    eligible = scores[(scores["stability_ari_median"] >= .65) &
                      (scores["min_cluster_n"] >= .01 * len(frame))]
    ranked = scores if eligible.empty else eligible
    chosen = int(ranked.sort_values(["silhouette_fixed_sample", "k"], ascending=[False, True]).iloc[0]["k"])
    finer = ranked[ranked["k"] > chosen]
    candidate = None if finer.empty else int(finer.sort_values(
        ["silhouette_fixed_sample", "k"], ascending=[False, True]
    ).iloc[0]["k"])
    scores.to_csv(output / "k_sweep.csv", index=False)
    labels.to_csv(output / "labels.csv.gz", index=False, compression={"method": "gzip", "mtime": 0})
    pd.concat(profiles.values()).to_csv(output / "cluster_profiles_all_k.csv", index=False)
    pd.concat(coverage.values()).to_csv(output / "price_coverage_all_k.csv", index=False)
    for k in [chosen, *([] if candidate is None else [candidate])]:
        figure_dir = output / f"k{k}"
        figure_dir.mkdir(exist_ok=True)
        plot_profiles(profiles[k], coverage[k], k, figure_dir)
    summary = {
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "listing_count": len(frame), "priced_count": int(frame["price_hkd"].count()),
        "scrape_dates": frame["last_scraped"].value_counts().to_dict(),
        "seed": SEED, "k_values": list(K_VALUES), "n_init": 20, "blocks": blocks,
        "numeric_features": NUMERIC, "amenity_tokens": AMENITIES,
        "silhouette_sample_n": len(sample), "resamples": RESAMPLES,
        "selection": "Max silhouette among median paired ARI >= .65 and minimum cluster >= 1%; all k if empty.",
        "selected_k": chosen, "finer_k": candidate,
        "library_versions": {"scikit-learn": sklearn.__version__, "numpy": np.__version__,
                             "pandas": pd.__version__, "matplotlib": matplotlib.__version__},
    }
    (output / "run.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(f"Selected k={chosen}; finer candidate k={candidate}", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with threadpool_limits(limits=2):
        run(args.listings, args.output)
