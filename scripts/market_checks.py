"""Check the exploratory k=3 split against room labels, hosts and an earlier quarter."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PatchCollection
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import PathPatch
from matplotlib.path import Path as MplPath
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cut_tree, linkage
from scipy.optimize import linear_sum_assignment
from sklearn.metrics import (adjusted_rand_score, davies_bouldin_score,
                             normalized_mutual_info_score, silhouette_score)
from sklearn.mixture import GaussianMixture
from threadpoolctl import threadpool_limits

from kmeans_baseline import (CLUSTER_COLORS, K_VALUES, ROOM_TYPES, SEED, cluster_tables,
                             features, fit_kmeans, load_listings, order_labels,
                             resample_pairs, save_figure, stability)

K = 3
BLOCKS = ("numeric", "room", "amenities")
DISTRICT = "neighbourhood_cleansed"


def align_to_reference(reference, labels):
    table = pd.crosstab(reference, labels)
    rows, columns = linear_sum_assignment(-table.to_numpy())
    mapping = dict(zip(table.columns[columns], table.index[rows]))
    return np.array([mapping[label] for label in labels])


def prices_by_room(frame, column="cluster"):
    grouped = frame.groupby(["room_type", column], observed=True)
    prices = grouped["price_hkd"].agg(listings="size", priced="count", median_hkd="median")
    prices["q25_hkd"] = grouped["price_hkd"].quantile(.25)
    prices["q75_hkd"] = grouped["price_hkd"].quantile(.75)
    prices["coverage_pct"] = 100 * prices["priced"] / prices["listings"]
    prices["hosts"] = grouped["host_id"].nunique()
    return prices.reset_index()


def district_residuals(frame, label_col):
    room_mix = pd.crosstab(frame[DISTRICT], frame["room_type"])
    cluster_mix = pd.crosstab(frame["room_type"], frame[label_col], normalize="index")
    observed = pd.crosstab(frame[DISTRICT], frame[label_col])
    total = observed.sum(axis=1)
    expected = room_mix @ cluster_mix.reindex(room_mix.columns)
    rows = []
    for district, sample_count in total.items():
        for cluster in observed.columns:
            real = observed.loc[district, cluster]
            est = expected.loc[district, cluster]
            rows.append({"district": district, "cluster": cluster, "district_n": sample_count,
                         "observed_n": real, "expected_n": est,
                         "excess_pp": 100 * (real - est) / sample_count})
    return pd.DataFrame(rows)


def cluster_source_table(frame):
    source = frame["source"].fillna("(blank)")
    return (frame.assign(listing_source=source)
            .groupby(["cluster", "listing_source"])["price_hkd"]
            .agg(listings="size", priced="count").reset_index()
            .assign(coverage_pct=lambda cell: 100 * cell["priced"] / cell["listings"]))


def explore_algorithms(frame, reference, output):
    matrix = features(frame, BLOCKS)
    sub = np.sort(np.random.default_rng(SEED).choice(len(frame), 3000, replace=False))
    tree = linkage(matrix, method="ward")
    ward_labels = cut_tree(tree, n_clusters=list(K_VALUES))
    rows = []
    for column, k in enumerate(K_VALUES):
        gmm = GaussianMixture(n_components=k, covariance_type="diag", reg_covar=1e-5,
                              n_init=5, random_state=SEED).fit(matrix)
        for name, labels, converged in (
            ("Ward", ward_labels[:, column], True), ("Diagonal GMM", gmm.predict(matrix), bool(gmm.converged_)),
        ):
            rows.append({
                "method": name, "k": k, "converged": converged,
                "silhouette_fixed_sample": silhouette_score(matrix[sub], labels[sub]),
                "davies_bouldin_full": davies_bouldin_score(matrix, labels),
                "min_cluster_n": np.bincount(labels).min(),
                "room_type_nmi": normalized_mutual_info_score(frame["room_type"], labels),
                "ari_vs_reference_k3": adjusted_rand_score(reference, labels) if k == K else np.nan,
            })
    pd.DataFrame(rows).to_csv(output / "alternative_models.csv", index=False)


def plot_room_splits(frame, output):
    fig, (left, right) = plt.subplots(1, 2, figsize=(12.4, 4.0),
                                     gridspec_kw={"width_ratios": [1.05, 1]}, layout="constrained")
    room_types = ROOM_TYPES[:2]
    table = pd.crosstab(frame["room_type"], frame["cluster"]).reindex(room_types, fill_value=0)
    totals = table.sum(axis=1)
    widths = table.div(totals, axis=0).mul(100)
    offset = np.zeros(len(table))
    for cluster in widths:
        values = widths[cluster].to_numpy()
        color = CLUSTER_COLORS[cluster-1]
        left.barh(np.arange(len(table)), values, left=offset, color=color, label=f"C{cluster}", height=.54)
        for i, value in enumerate(values):
            if value >= 8:
                left.text(offset[i]+value/2, i, f"{value:.1f}%", ha="center", va="center",
                          color="white", fontweight="bold")
        offset += values
    left.set(yticks=[0, 1], yticklabels=[f"{room_type}\n(n={n:,})" for room_type, n in totals.items()],
             xlim=(0, 100), xlabel="Share of room type (%)")
    left.invert_yaxis()
    left.set_title("A   Where the two main room types split", loc="left", fontweight="bold")
    left.legend(frameon=False, ncol=3, loc="lower center", bbox_to_anchor=(.5, -.28))
    price = prices_by_room(frame)
    private = price[price["room_type"] == "Private room"].reset_index(drop=True)
    for i, p in enumerate(private.itertuples()):
        color = CLUSTER_COLORS[p.cluster-1]
        right.hlines(i, p.q25_hkd, p.q75_hkd, color=color, linewidth=5, alpha=.62)
        right.scatter(p.median_hkd, i, s=73, c=color, zorder=3)
        right.annotate(f"{p.median_hkd:,.0f}", (p.median_hkd, i), xytext=(0, 13),
                       textcoords="offset points", ha="center", va="bottom", color=color, fontweight="bold")
    right.set(yticks=range(len(private)),
              yticklabels=[f"C{p.cluster}  {p.priced:,}/{p.listings:,} priced" for p in private.itertuples()],
              ylim=(len(private)-.5, -.55), xlim=(0, max(private["q75_hkd"]) * 1.1),
              xlabel="Observed listing price (HKD/night)  ·  Median and IQR")
    right.set_title("B   Listing prices within private rooms", loc="left", fontweight="bold")
    right.grid(True, axis="x", alpha=.2)
    for axis in (left, right):
        axis.spines[["top", "right", "left"]].set_visible(False)
        axis.tick_params(axis="y", length=0)
    fig.suptitle("What the private-room label leaves out", fontweight="bold", color="#142b43", fontsize=17)
    save_figure(fig, output / "within_room_story")


def plot_geo(geojson, spatial, output):
    features_geo = json.loads(geojson.read_text())["features"]
    selected = spatial[spatial["cluster"] == 2].set_index("district")
    enough = selected["district_n"] >= 50
    bound = max(10, 5 * np.ceil(selected.loc[enough, "excess_pp"].abs().max() / 5))
    norm = TwoSlopeNorm(vmin=-bound, vcenter=0, vmax=bound)
    fig, ax = plt.subplots(figsize=(9.3, 7.2), layout="constrained")
    cmap = plt.get_cmap("PuOr_r")
    patches, colors = [], []
    for entry in features_geo:
        name = entry["properties"]["neighbourhood"]
        geometry = entry["geometry"]
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        color = cmap(norm(selected.loc[name, "excess_pp"])) if enough.loc[name] else "#cbd5df"
        for polygon in polygons:
            points, codes = [], []
            for ring in polygon:
                points.extend(ring)
                codes.extend([MplPath.MOVETO, *([MplPath.LINETO] * (len(ring)-2)), MplPath.CLOSEPOLY])
            patches.append(PathPatch(MplPath(points, codes)))
            colors.append(color)
    ax.add_collection(PatchCollection(patches, facecolors=colors, edgecolor="white", linewidth=.7))
    ax.autoscale_view()
    mid_latitude = np.mean(ax.get_ylim())
    ax.set_aspect(1 / np.cos(np.deg2rad(mid_latitude)))
    ax.set_axis_off()
    names = {
        "Yau Tsim Mong": ("Yau Tsim Mong", (114.25, 22.36)),
        "Wan Chai": ("Wan Chai", (114.26, 22.255)),
        "Central & Western": ("Central & Western", (114.05, 22.218)),
    }
    for district, (label, anchor) in names.items():
        if district not in selected.index:
            continue
        entry = next(entry for entry in features_geo if entry["properties"]["neighbourhood"] == district)
        geometry = entry["geometry"]
        polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
        main = max(polygons, key=lambda rings: len(rings[0]))[0]
        center = np.mean(main, axis=0)
        info = selected.loc[district]
        ax.annotate(f"{label}\n{info.excess_pp:+.1f} pp · n={int(info.district_n):,}",
                    xy=center, xytext=anchor, fontsize=9, ha="center", va="center",
                    arrowprops={"arrowstyle": "-", "color": "#465569", "lw": 0.8},
                    bbox={"facecolor": "white", "edgecolor": "none", "alpha": .88, "pad": 3})
    sm = matplotlib.cm.ScalarMappable(norm=norm, cmap=cmap)
    fig.colorbar(sm, ax=ax, orientation="horizontal", shrink=.62, pad=.015,
                 label="C2 observed minus expected (percentage points)")
    ax.set_title("Where longer-minimum-stay listings are overrepresented", loc="left", pad=23,
                 fontsize=14, fontweight="bold", color="#142b43")
    ax.text(0, 1.012, "Listing-weighted k=3 · Expected share from district room-type mix · Grey: n < 50",
            transform=ax.transAxes, fontsize=8.5, color="#40566c")
    save_figure(fig, output / "room_adjusted_map")


def cross_quarter(earlier_path, september, reference, output):
    june = load_listings(earlier_path)
    pooled = pd.concat([june, september], ignore_index=True)
    june_index = np.arange(len(june))
    matrix = features(pooled, BLOCKS, fit_index=june_index)
    model = fit_kmeans(matrix[june_index], K)
    ids = pd.DataFrame({"id": june["id"], "june_cluster": model.labels_})
    transferred = model.predict(matrix[len(june):])
    september_labels = align_to_reference(reference, transferred)
    scored = september.assign(transfer_cluster=september_labels)
    transfer_profile, transfer_coverage = cluster_tables(scored, scored["transfer_cluster"])
    transfer_profile.to_csv(output / "june_model_september_profiles.csv", index=False)
    transfer_coverage.to_csv(output / "june_model_september_price_coverage.csv", index=False)
    prices_by_room(scored, "transfer_cluster").to_csv(output / "june_model_september_prices_by_room.csv", index=False)
    shared = scored[["id", "transfer_cluster"]].merge(ids, on="id")
    is_new_listing = ~september["id"].isin(june["id"])
    is_new_host = ~september["host_id"].isin(june["host_id"])
    subgroup_scores = []
    for name, keep in {"all September": np.ones(len(september), dtype=bool),
                       "ID in both snapshots": ~is_new_listing,
                       "ID absent in June": is_new_listing,
                       "host absent in June": is_new_host,
                       "ID and host absent in June": is_new_listing & is_new_host}.items():
        subgroup_scores.append({"subset": name, "listings": int(keep.sum()),
                                "ari_frozen_vs_september_refit": adjusted_rand_score(reference[keep], transferred[keep]),
                                "aligned_agreement_pct": 100 * np.mean(reference[keep] == september_labels[keep])})
    pd.DataFrame(subgroup_scores).to_csv(output / "cross_quarter.csv", index=False)
    return {
        "june_listings": len(june), "june_sha256": hashlib.sha256(earlier_path.read_bytes()).hexdigest(),
        "june_scrape_dates": june["last_scraped"].value_counts().to_dict(),
        "shared_listing_ids": len(shared),
        "shared_id_ari_same_june_model_over_time": adjusted_rand_score(
            shared["june_cluster"], shared["transfer_cluster"]
        ),
    }


def run(listings, baseline, geojson, output, earlier):
    output.mkdir(parents=True, exist_ok=True)
    frame = load_listings(listings)
    known = pd.read_csv(baseline / "labels.csv.gz", usecols=["id", f"k{K}"], dtype={"id": "string"})
    frame = frame.merge(known, on="id", validate="one_to_one")
    reference = frame.pop(f"k{K}").to_numpy()
    frame["cluster"] = reference
    matrix = features(frame, BLOCKS)
    counts = frame["host_id"].map(frame["host_id"].value_counts()).to_numpy(dtype=float)
    weights = 1 / counts
    wt_labels = align_to_reference(reference, fit_kmeans(matrix, K, weights=weights).labels_)
    frame["host_weighted"] = wt_labels
    weights_ari = adjusted_rand_score(reference, wt_labels)
    pair_quartiles, group_jaccard = stability(frame, BLOCKS, K, reference, resample_pairs(frame, host_blocks=True))
    pd.crosstab(frame["cluster"], frame["host_weighted"]).to_csv(output / "host_weight_transitions.csv")
    pd.crosstab(frame["room_type"], frame["cluster"]).to_csv(output / "room_to_cluster.csv")
    wt_profile, wt_coverage = cluster_tables(frame, wt_labels)
    wt_profile.to_csv(output / "host_weighted_profiles.csv", index=False)
    wt_coverage.to_csv(output / "host_weighted_price_coverage.csv", index=False)
    prices = prices_by_room(frame)
    prices.to_csv(output / "prices_within_room_type.csv", index=False)
    cluster_source_table(frame).to_csv(output / "price_coverage_by_source.csv", index=False)
    prices_by_room(frame[~frame["source"].eq("previous scrape")]).to_csv(
        output / "prices_within_room_type_excluding_previous_scrape.csv", index=False
    )
    district = district_residuals(frame, "cluster")
    district.to_csv(output / "district_room_adjusted.csv", index=False)
    district_residuals(frame, "host_weighted").to_csv(output / "district_room_adjusted_host_weighted.csv", index=False)
    plot_room_splits(frame, output)
    plot_geo(geojson, district, output)

    variants = {
        "numeric+room": ("numeric", "room"),
        "numeric+room+district": ("numeric", "room", "district"),
        "numeric+room+district+amenities": (*BLOCKS, "district"),
        "numeric+room+district+amenities+host_count": (*BLOCKS, "district", "host_count"),
        "numeric+amenities (no room or property type)": ("numeric", "amenities"),
    }
    variant_rows, variant_labels = [], {}
    previous = None
    for name, blocks in variants.items():
        data = features(frame, blocks)
        labels = order_labels(fit_kmeans(data, K).labels_)
        variant_labels[name] = labels
        variant_rows.append({
            "feature_blocks": name, "smallest_cluster_n": int(np.bincount(labels)[1:].min()),
            "ari_vs_september_baseline": adjusted_rand_score(reference, labels),
            "ari_vs_previous_in_sequence": adjusted_rand_score(previous, labels)
                if previous is not None and "no room" not in name else np.nan,
            "room_type_nmi": normalized_mutual_info_score(frame["room_type"], labels),
            "private_room_ari_vs_baseline": adjusted_rand_score(
                reference[frame["room_type"] == "Private room"], labels[frame["room_type"] == "Private room"]
            ),
        })
        previous = labels
    pd.DataFrame(variant_rows).to_csv(output / "feature_ablation.csv", index=False)
    no_room = variant_labels["numeric+amenities (no room or property type)"]
    nr_profile, _ = cluster_tables(frame, no_room)
    nr_profile.to_csv(output / "without_room_label_profiles.csv", index=False)

    top_five = frame["host_id"].value_counts().head(5).index
    keep = np.flatnonzero(~frame["host_id"].isin(top_five))
    top5_removed = fit_kmeans(features(frame, BLOCKS, keep)[keep], K).labels_
    summary = {
        "k": K, "listings": len(frame), "host_accounts": int(frame["host_id"].nunique()),
        "top_five_host_listings": int(len(frame) - len(keep)),
        "top_ten_host_listings": int(frame["host_id"].value_counts().head(10).sum()),
        "host_weight_ari": weights_ari, "host_weight_agreement_pct": 100 * np.mean(reference == wt_labels),
        "host_weight_private_room_ari": adjusted_rand_score(
            reference[frame["room_type"] == "Private room"], wt_labels[frame["room_type"] == "Private room"]),
        "host_resample_ari_q25_median_q75": pair_quartiles.tolist(),
        "host_resample_min_median_cluster_jaccard": min(group_jaccard.values()),
        "host_resample_cluster_jaccard": group_jaccard,
        "remove_top_five_host_ari": adjusted_rand_score(reference[keep], top5_removed),
    }
    if earlier is not None:
        summary["cross_quarter"] = cross_quarter(earlier, frame, reference, output)
    (output / "checks.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps(summary, indent=2), flush=True)
    explore_algorithms(frame, reference, output)
    print("Ward and diagonal GMM sweep finished.", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("listings", "baseline", "geojson", "output"):
        parser.add_argument(f"--{option}", type=Path, required=True)
    parser.add_argument("--earlier", type=Path)
    args = parser.parse_args()
    with threadpool_limits(limits=2):
        run(args.listings, args.baseline, args.geojson, args.output, args.earlier)
