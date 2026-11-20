"""Compare categorical-mode and one-hot Euclidean prototypes on a fixed snapshot."""

import argparse
from pathlib import Path

from kmodes.kprototypes import KPrototypes
import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score, silhouette_score
from threadpoolctl import threadpool_limits

from kmeans_baseline import AMENITIES, SEED, cluster_tables, features, fit_kmeans, load_listings, order_labels
from market_checks import BLOCKS


def run(source, output):
    output.mkdir(parents=True, exist_ok=True)
    frame = load_listings(source)
    numeric = features(frame, ("numeric",))
    categorical = frame[["room_type", *AMENITIES]]
    mixed = np.column_stack([numeric.astype(object), categorical.to_numpy(dtype=object)])
    category_columns = list(range(numeric.shape[1], mixed.shape[1]))
    room_share = frame["room_type"].value_counts(normalize=True).to_numpy()
    amenity_share = frame[list(AMENITIES)].mean().to_numpy()
    category_weight = np.r_[1 / (1 - np.square(room_share).sum()),
                            np.repeat(1 / (2 * amenity_share * (1 - amenity_share)).sum(), len(AMENITIES))]

    def matching_cost(centroids, sample, **_unused):
        return np.sum((centroids != sample) * category_weight, axis=1)

    one_hot_matrix = features(frame, BLOCKS)
    sample = np.sort(np.random.default_rng(SEED).choice(len(frame), 3000, replace=False))
    private = frame["room_type"].eq("Private room").to_numpy()
    account_size = frame["host_id"].map(frame["host_id"].value_counts()).to_numpy(dtype=float)
    rows, profiles = [], []
    for k in (3, 4):
        unweighted_reference = fit_kmeans(one_hot_matrix, k).labels_
        for weighting, weights in (("listing", None), ("account", 1 / account_size)):
            matched_reference = (unweighted_reference if weights is None
                                 else fit_kmeans(one_hot_matrix, k, weights=weights).labels_)
            for gamma in (.5, 1., 2.):
                model = KPrototypes(n_clusters=k, gamma=gamma, cat_dissim=matching_cost, init="Cao", n_init=4,
                                    max_iter=60, random_state=SEED, n_jobs=1)
                labels = order_labels(model.fit(mixed, categorical=category_columns, sample_weight=weights).labels_)
                profile, _ = cluster_tables(frame, labels)
                rows.append({
                    "k": k, "weighting": weighting, "gamma": gamma, "iterations": model.n_iter_,
                    "mixed_objective": model.cost_,
                    "silhouette_on_common_euclidean_space": silhouette_score(
                        one_hot_matrix[sample], labels[sample]),
                    "ari_vs_matched_kmeans": adjusted_rand_score(matched_reference, labels),
                    "private_room_ari_vs_matched_kmeans": adjusted_rand_score(
                        matched_reference[private], labels[private]),
                    "private_room_ari_vs_listing_weighted_kmeans": adjusted_rand_score(
                        unweighted_reference[private], labels[private]),
                    "mostly_private_clusters": int((profile["Private room (%)"] >= 80).sum()),
                    "min_cluster_n": int(profile["listings"].min()),
                })
                profile.insert(0, "gamma", gamma)
                profile.insert(0, "weighting", weighting)
                profile.insert(0, "k", k)
                profiles.append(profile)
                print(f"k={k} {weighting} gamma={gamma:g} "
                      f"ARI vs. matched K-Means={rows[-1]['ari_vs_matched_kmeans']:.3f} "
                      f"mostly-private clusters={rows[-1]['mostly_private_clusters']}", flush=True)
    pd.DataFrame(rows).to_csv(output / "kprototypes_summary.csv", index=False)
    pd.concat(profiles).to_csv(output / "kprototypes_profiles.csv", index=False)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--listings", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    with threadpool_limits(limits=2):
        run(args.listings, args.output)
