"""Examine whether equal account weights change a global or within-room partition."""

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import PathPatch, Rectangle
from matplotlib.path import Path as MplPath
import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge
from sklearn.metrics import adjusted_rand_score
from sklearn.model_selection import GroupKFold
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

from kmeans_baseline import (CLUSTER_COLORS, K_VALUES, cluster_tables, features,
                             fit_kmeans, load_listings, order_labels, save_figure)
from market_checks import BLOCKS, DISTRICT, K, align_to_reference, prices_by_room


def alluvial(transition, output):
    transition = transition.loc[:, [1, 3, 2]]
    fig, ax = plt.subplots(figsize=(11.5, 5.3))
    n = transition.to_numpy().sum()
    gap = .04
    normalizer = n / .88
    left = np.r_[0., np.cumsum(transition.sum(axis=1).to_numpy()[:-1]) / normalizer]
    right = np.r_[0., np.cumsum(transition.sum(axis=0).to_numpy()[:-1]) / normalizer]
    left += gap * np.arange(len(left))
    right += gap * np.arange(len(right))
    used_l, used_r = left.copy(), right.copy()
    for i, row in enumerate(transition.to_numpy()):
        for j, count in enumerate(row):
            if count == 0:
                continue
            size = count / normalizer
            y0, y1 = used_l[i], used_r[j]
            points = [(0, y0), (.43, y0), (.57, y1), (1, y1), (1, y1+size),
                      (.57, y1+size), (.43, y0+size), (0, y0+size), (0, y0)]
            commands = [MplPath.MOVETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4,
                        MplPath.LINETO, MplPath.CURVE4, MplPath.CURVE4, MplPath.CURVE4, MplPath.CLOSEPOLY]
            ax.add_patch(PathPatch(MplPath(points, commands), linewidth=0,
                                   facecolor=CLUSTER_COLORS[i], alpha=.57))
            if count >= 650:
                ax.text(.5, (y0+y1+size)/2, f"{count:,}", ha="center", va="center", fontsize=10,
                        color="#163047", fontweight="semibold",
                        bbox={"facecolor":"white", "alpha":.75, "edgecolor":"none", "pad":2})
            used_l[i] += size
            used_r[j] += size
    metadata = [
        (-.025, left, transition.sum(axis=1), ["Mostly entire homes", "Private rooms · 29 nights",
                                             "Private rooms · 1 night"]),
        (1.0, right, transition.sum(axis=0), ["Entire homes · 2 guests",
                                             "Entire homes · 6 guests", "Mostly private rooms"]),
    ]
    for x, positions, sizes, labels in metadata:
        for i, (position, size, label) in enumerate(zip(positions, sizes, labels)):
            h = size / normalizer
            ax.add_patch(Rectangle((x, position), .025, h,
                                   color=CLUSTER_COLORS[i] if x < 0 else "#263d53"))
            ax.text(x - .016 if x < 0 else x + .042, position+h/2, f"{label}\n{size:,} listings",
                    ha="right" if x < 0 else "left", va="center", fontsize=9, color="#142b43")
    ax.text(0, -.07, "Each listing counts equally", ha="center", fontsize=11, fontweight="bold")
    ax.text(1, -.07, "Each host account counts equally", ha="center", fontsize=11, fontweight="bold")
    ax.set(xlim=(-.31, 1.32), ylim=(1.00, -.14))
    ax.axis("off")
    fig.suptitle("Who gets split when every host account counts equally?",
                 fontsize=17, fontweight="bold", color="#142b43", x=.12, ha="left")
    fig.text(.12, .87, "Same listings, features and k=3  ·  Flows count listings  ·  Minimum nights and guests shown as medians",
             fontsize=9.5, color="#40566c")
    fig.subplots_adjust(top=.81, bottom=.07, left=.025, right=.975)
    save_figure(fig, output / "listing_to_account_weights")


def held_out_prices(frame, output):
    """Compare price predictors within the observed-price subset of each host split."""
    predictions = []
    targets = frame["price_hkd"].to_numpy()
    for fold, (train, test) in enumerate(GroupKFold(n_splits=5).split(frame, groups=frame["host_id"]), 1):
        if set(frame.iloc[train]["host_id"]) & set(frame.iloc[test]["host_id"]):
            raise ValueError("Host accounts must be disjoint between folds.")
        encoded = features(frame, BLOCKS, train)
        km = fit_kmeans(encoded[train], K)
        assigned = km.predict(encoded)
        keys = frame[["room_type", DISTRICT]].assign(cluster=assigned.astype(str))
        priced_train = train[np.isfinite(targets[train])]
        priced_test = test[np.isfinite(targets[test])]
        baseline = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        baseline.fit(keys.iloc[priced_train][["room_type", DISTRICT]])
        original = baseline.transform(keys[["room_type", DISTRICT]])
        labels = OneHotEncoder(handle_unknown="ignore", sparse_output=False)
        labels.fit(keys.iloc[priced_train][["cluster"]])
        clusters = labels.transform(keys[["cluster"]])
        minimum_nights = frame[["minimum_nights"]].fillna(frame.iloc[priced_train]["minimum_nights"].median())
        log_nights = np.log1p(minimum_nights)
        nights = StandardScaler().fit(log_nights.iloc[priced_train]).transform(log_nights)
        options = {
            "Room type + district": original,
            "Room type + district + minimum nights": np.column_stack([original, nights]),
            "Room type + district + cluster": np.column_stack([original, clusters]),
            "Room type + district + minimum nights + cluster": np.column_stack([original, nights, clusters]),
        }
        for name, matrix in options.items():
            model = Ridge(alpha=10).fit(matrix[priced_train], np.log1p(targets[priced_train]))
            log_prediction = model.predict(matrix[priced_test])
            records = keys.iloc[priced_test][["room_type"]].rename_axis("row").reset_index()
            records["fold"] = fold
            records["model"] = name
            records["abs_error_hkd"] = np.abs(np.expm1(log_prediction) - targets[priced_test])
            records["abs_error_log1p"] = np.abs(log_prediction - np.log1p(targets[priced_test]))
            predictions.append(records)
    all_rows = pd.concat(predictions)
    summaries = []
    for subset, rows in (("All room types", all_rows), ("Private room", all_rows[all_rows["room_type"] == "Private room"])):
        for grouping, keys in (("Pooled", ["model"]), ("By fold", ["model", "fold"])):
            summary = rows.groupby(keys).agg(priced_n=("row", "size"), mae_hkd=("abs_error_hkd", "mean"),
                                             mae_log1p=("abs_error_log1p", "mean")).reset_index()
            summaries.append(summary.assign(subset=subset, aggregation=grouping))
    pd.concat(summaries).to_csv(output / "price_prediction_held_out_hosts.csv", index=False)


def run(source, baseline, output):
    output.mkdir(parents=True, exist_ok=True)
    frame = load_listings(source)
    reference = pd.read_csv(baseline / "labels.csv.gz", dtype={"id": "string"}).set_index("id").loc[
        frame["id"], "k3"
    ].to_numpy()
    frame["cluster"] = reference
    counts = frame["host_id"].map(frame["host_id"].value_counts()).to_numpy(dtype=float)
    matrix = features(frame, BLOCKS)
    private = frame[frame["room_type"].eq("Private room")].copy()
    private_matrix = features(private, ("numeric", "amenities"))
    private_counts = private["host_id"].map(private["host_id"].value_counts()).to_numpy(dtype=float)
    private_reference = private["cluster"].to_numpy()
    within_unweighted = fit_kmeans(private_matrix, 2).labels_
    weighted_profiles = []
    for k in K_VALUES:
        profile, _ = cluster_tables(frame, order_labels(fit_kmeans(matrix, k, weights=1 / counts).labels_))
        profile.insert(0, "k", k)
        weighted_profiles.append(profile)
    pd.concat(weighted_profiles).to_csv(output / "account_weighted_k_sweep_profiles.csv", index=False)
    path = []
    for power in np.linspace(0, 1, 11):
        global_labels = fit_kmeans(matrix, K, weights=counts ** -power).labels_
        aligned = align_to_reference(reference, global_labels)
        private_global_labels = aligned[private.index]
        restricted = fit_kmeans(private_matrix, 2, weights=private_counts ** -power).labels_
        path.append({
            "alpha": power,
            "global_ari_vs_unweighted": adjusted_rand_score(reference, global_labels),
            "private_ari_global_fit_vs_original": adjusted_rand_score(private_reference, private_global_labels),
            "private_ari_private_only_fit_vs_original": adjusted_rand_score(private_reference, restricted),
            "private_ari_private_only_fit_vs_private_only_unweighted": adjusted_rand_score(within_unweighted, restricted),
            "effective_account_weight_ess": np.square(np.sum(np.power(counts, -power))) /
                np.sum(np.square(pd.Series(counts ** -power).groupby(frame["host_id"]).sum())),
        })
    pd.DataFrame(path).to_csv(output / "account_weight_path.csv", index=False)
    transition = pd.crosstab(reference, aligned)
    alluvial(transition, output)

    records = []
    for fit, labels in (("private-only listing-weighted", within_unweighted), ("private-only account-weighted", restricted)):
        stable_ids = align_to_reference(private_reference, labels)
        profile, _ = cluster_tables(private, stable_ids)
        profile.insert(0, "fit", fit)
        records.append(profile)
    pd.concat(records).to_csv(output / "private_only_profiles.csv", index=False)

    observed = private[private["minimum_nights"].notna()].copy()
    observed["minimum_nights_28_plus"] = observed["minimum_nights"] >= 28
    by_rule = pd.crosstab(observed["cluster"], observed["minimum_nights_28_plus"])
    by_rule.to_csv(output / "private_rooms_28_night_rule.csv")
    print("ARI of 28-night rule vs. exploratory partition (observed stay rules only): "
          f"{adjusted_rand_score(observed['cluster'], observed['minimum_nights_28_plus']):.4f}", flush=True)
    frame["weight_alpha_1"] = aligned
    prices_by_room(frame, "weight_alpha_1").to_csv(output / "account_weighted_prices_by_room.csv", index=False)
    print(pd.DataFrame(path).round(3).to_string(index=False), flush=True)
    held_out_prices(frame, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("listings", "baseline", "output"):
        parser.add_argument(f"--{option}", type=Path, required=True)
    args = parser.parse_args()
    with threadpool_limits(limits=2):
        run(args.listings, args.baseline, args.output)
