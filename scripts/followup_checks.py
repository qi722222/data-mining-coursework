"""Test the stay-length feature and compare district estimates for a fixed C2."""

import argparse
import hashlib
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import colormaps
from matplotlib.collections import PatchCollection
from matplotlib.colors import TwoSlopeNorm
from matplotlib.patches import Patch, PathPatch
from matplotlib.path import Path as PlotPath
from sklearn.metrics import adjusted_rand_score
from threadpoolctl import threadpool_limits

from kmeans_baseline import NUMERIC, SEED, cluster_tables, features, fit_kmeans, load_listings, order_labels, save_figure
from market_checks import BLOCKS, DISTRICT, prices_by_room

BOOTSTRAPS = 2000
DISPLAY_MIN_LISTINGS = 50
EXAMPLE_NIGHTS = 45
EXAMPLE_BUDGET_HKD = 250


def stay_length_ablation(listings, references, account_weights, output):
    full = features(listings, BLOCKS)
    # The numeric block comes first in BLOCKS. Removing one transformed column
    # keeps the retained feature values and all their scaling factors fixed.
    reduced = np.delete(full, NUMERIC.index("minimum_nights"), axis=1)
    private_rooms = listings["room_type"].eq("Private room").to_numpy()
    summary, prices, profiles = [], [], []
    for k in (3, 4):
        for mode, weights in (("listing", None), ("account", account_weights)):
            reference = references[f"k{k}"] if weights is None else fit_kmeans(full, k, weights=weights).labels_
            if weights is None:
                refitted = fit_kmeans(full, k).labels_
                if adjusted_rand_score(reference, refitted) < 1 - 1e-12:
                    raise ValueError(f"Published k={k} labels do not match the current baseline.")
            for feature_set, matrix in (("full", full), ("without_minimum_nights", reduced)):
                labels = order_labels(reference if feature_set == "full" else fit_kmeans(matrix, k, weights=weights).labels_)
                tags = {"k": k, "fit_weighting": mode, "features": feature_set}
                matches = adjusted_rand_score(reference, labels)
                private_matches = adjusted_rand_score(reference[private_rooms], labels[private_rooms])
                # Stay rules remain in the output profiles for post-fit interpretation.
                profile, _ = cluster_tables(listings, labels)
                profiles.append(profile.assign(**tags))
                table = prices_by_room(listings.assign(cluster=labels))
                prices.append(table.assign(**tags))
                private_prices = table[table["room_type"] == "Private room"]
                major_private = private_prices[private_prices["listings"] >= 0.05 * private_rooms.sum()]
                counts = major_private["median_hkd"].dropna()
                summary.append({
                    **tags, "listings": len(listings),
                    "ari_vs_full": matches, "private_room_ari_vs_full": private_matches,
                    "private_rooms_by_cluster": "/".join(str(i) for i in private_prices["listings"]),
                    "private_room_clusters_with_at_least_5pct_of_private_rooms": len(major_private),
                    "private_room_median_price_range_hkd": float(counts.max()-counts.min()) if len(counts) >= 2 else np.nan,
                })
    table = pd.DataFrame(summary)
    table.to_csv(output / "stay_ablation_summary.csv", index=False)
    pd.concat(prices, ignore_index=True).to_csv(output / "stay_ablation_prices_by_room.csv", index=False)
    pd.concat(profiles, ignore_index=True).to_csv(output / "stay_ablation_profiles.csv", index=False)
    return table


def district_excess(totals, selected):
    """Compute room-type-standardized C2 shares along the district axis."""
    room_totals = totals.sum(axis=-2)
    city_rates = np.divide(selected.sum(axis=-2), room_totals,
                           out=np.zeros_like(room_totals, dtype=float), where=room_totals > 0)
    district_totals = totals.sum(axis=-1)
    observed = selected.sum(axis=-1)
    expected = (totals * city_rates[..., None, :]).sum(axis=-1)
    excess = np.divide(100 * (observed - expected), district_totals,
                       out=np.full_like(district_totals, np.nan, dtype=float), where=district_totals > 0)
    return excess, district_totals, observed, expected


def fixed_c2_map(listings, c2, host_codes, host_sizes, output):
    district_codes, districts = pd.factorize(listings[DISTRICT], sort=True)
    room_codes, room_types = pd.factorize(listings["room_type"], sort=True)
    if (district_codes < 0).any() or (room_codes < 0).any():
        raise ValueError("District and room type must be available for every listing.")
    shape = (len(host_sizes), len(districts), len(room_types))
    index = np.ravel_multi_index((host_codes, district_codes, room_codes), shape)

    # This table retains each account's contributions to each district and room type.
    total_by_host = np.bincount(index, minlength=np.prod(shape)).reshape(shape)
    c2_by_host = np.bincount(index[c2], minlength=np.prod(shape)).reshape(shape)
    multipliers = np.random.default_rng(SEED).multinomial(
        len(host_sizes), np.full(len(host_sizes), 1 / len(host_sizes)), size=BOOTSTRAPS
    ).astype(float)
    result = pd.DataFrame({
        "district": districts,
        "listing_n": total_by_host.sum(axis=(0, 2)),
        "account_n": (total_by_host.sum(axis=2) > 0).sum(axis=0),
        "c2_listing_n": c2_by_host.sum(axis=(0, 2)),
    })
    boot = {}
    for mode, fit_weights in (("listing", np.ones_like(host_sizes)), ("account", 1 / host_sizes)):
        weights = fit_weights[:, None, None]
        weighted_total = total_by_host * weights
        weighted_c2 = c2_by_host * weights
        values, mass, observed, expected = district_excess(weighted_total.sum(axis=0), weighted_c2.sum(axis=0))
        result[f"{mode}_weighted_mass"] = mass
        result[f"{mode}_observed_pct"] = 100 * observed / mass
        result[f"{mode}_expected_pct"] = 100 * expected / mass
        result[f"{mode}_excess_pp"] = values
        given_shape = (BOOTSTRAPS, *shape[1:])
        # The same account draws drive both estimates and their paired difference.
        boot_total = (multipliers @ weighted_total.reshape(len(host_sizes), -1)).reshape(given_shape)
        boot_c2 = (multipliers @ weighted_c2.reshape(len(host_sizes), -1)).reshape(given_shape)
        boot[mode] = district_excess(boot_total, boot_c2)[0]
    result["account_minus_listing_pp"] = result["account_excess_pp"] - result["listing_excess_pp"]
    boot["account_minus_listing"] = boot["account"] - boot["listing"]
    for mode, estimates in boot.items():
        result[f"{mode}_ci_low_pp"], result[f"{mode}_ci_high_pp"] = np.nanquantile(estimates, [0.025, 0.975], axis=0)
        result[f"{mode}_bootstrap_n"] = np.isfinite(estimates).sum(axis=0)
    result.to_csv(output / "fixed_c2_district_weights.csv", index=False)
    return result


def draw_comparison(geojson, results, output):
    features_geo = json.loads(geojson.read_text())["features"]
    visible = results["listing_n"] >= DISPLAY_MIN_LISTINGS
    ranked = results[visible].sort_values("listing_excess_pp")
    values = ranked[["listing_excess_pp", "account_excess_pp"]].to_numpy()
    bound = max(10, 5 * np.ceil(np.abs(values).max() / 5))
    norm = TwoSlopeNorm(vmin=-bound, vcenter=0, vmax=bound)
    cmap = colormaps["PuOr_r"]
    table = results.set_index("district")
    fig = plt.figure(figsize=(12.3, 8.55), layout="constrained")
    layout = fig.add_gridspec(2, 2, height_ratios=[1, 1.12])
    axes = [fig.add_subplot(layout[0, i]) for i in range(2)]
    for ax, (mode, label) in zip(axes, [("listing", "Each listing counts equally"),
                                          ("account", "Each account counts equally")]):
        patches, fills = [], []
        for entry in features_geo:
            info = table.loc[entry["properties"]["neighbourhood"]]
            shade = cmap(norm(info[f"{mode}_excess_pp"])) if info["listing_n"] >= DISPLAY_MIN_LISTINGS else "#d6dfe6"
            geometry = entry["geometry"]
            polygons = [geometry["coordinates"]] if geometry["type"] == "Polygon" else geometry["coordinates"]
            for polygon in polygons:
                points, verbs = [], []
                for ring in polygon:
                    points.extend(ring)
                    verbs.extend([PlotPath.MOVETO, *([PlotPath.LINETO] * (len(ring)-2)), PlotPath.CLOSEPOLY])
                patches.append(PathPatch(PlotPath(points, verbs)))
                fills.append(shade)
        ax.add_collection(PatchCollection(patches, facecolors=fills, edgecolor="white", linewidth=.65))
        ax.autoscale_view()
        ax.set_aspect(1 / np.cos(np.deg2rad(np.mean(ax.get_ylim()))))
        ax.set_axis_off()
        ax.set_title(label, loc="left", fontweight="bold", fontsize=13)
    scale = fig.colorbar(plt.cm.ScalarMappable(norm=norm, cmap=cmap), ax=axes, orientation="horizontal",
                         shrink=.62, pad=.015, aspect=36, label="C2 observed share minus room-type expectation (pp)")
    scale.ax.tick_params(labelsize=8)
    axes[1].legend(handles=[Patch(color="#d6dfe6", label="Fewer than 50 listings")],
                   loc="upper right", frameon=False, fontsize=8)
    ax = fig.add_subplot(layout[1, :])
    y = np.arange(len(ranked))
    for mode, offset, color, label in [("listing", -.14, "#276E82", "Listing-weighted"),
                                       ("account", .14, "#B55226", "Account-weighted")]:
        point = ranked[f"{mode}_excess_pp"]
        ax.hlines(y+offset, ranked[f"{mode}_ci_low_pp"], ranked[f"{mode}_ci_high_pp"], color=color, alpha=.68, lw=1.5)
        ax.scatter(point, y+offset, s=25, zorder=3, color=color, label=label)
    ax.set_yticks(y, [f"{row.district}  ·  {row.listing_n:,} listings" for row in ranked.itertuples()])
    ax.axvline(0, color="#567080", lw=.8)
    ax.set_xlabel("Excess share (percentage points)  ·  95% account-bootstrap intervals")
    ax.spines[["left", "right", "top"]].set_visible(False)
    ax.tick_params(axis="y", length=0)
    ax.legend(loc="lower right", frameon=False)
    ax.grid(True, axis="x", alpha=.2)
    fig.suptitle("How the same C2 group varies by district", fontweight="bold", fontsize=18)
    save_figure(fig, output / "fixed_c2_district_weights")


def shortlist_example(listings_path, listings, output):
    maximum = pd.read_csv(listings_path, usecols=["id", "maximum_nights"], dtype={"id": "string"})
    with_limits = listings.merge(maximum, on="id", validate="one_to_one")
    matches = with_limits[
        with_limits["room_type"].eq("Private room") & with_limits["Kitchen"]
        & with_limits["accommodates"].ge(1) & with_limits["price_hkd"].le(EXAMPLE_BUDGET_HKD)
        & with_limits["minimum_nights"].le(EXAMPLE_NIGHTS) & with_limits["maximum_nights"].ge(EXAMPLE_NIGHTS)
    ]
    summary = matches.groupby(DISTRICT).agg(
        matching_listings=("id", "size"),
        distinct_accounts=("host_id", "nunique"),
        median_observed_nightly_hkd=("price_hkd", "median"),
    ).sort_values("matching_listings", ascending=False)
    summary.to_csv(output / "shortlist_example.csv", index_label="district")


def run(listings_path, baseline, geojson, output):
    output.mkdir(parents=True, exist_ok=True)
    listings = load_listings(listings_path)
    data_hash = hashlib.sha256(listings_path.read_bytes()).hexdigest()
    expected_hash = json.loads((baseline / "run.json").read_text())["source_sha256"]
    if data_hash != expected_hash:
        raise ValueError("The follow-up must use the baseline's exact listing snapshot.")
    labels = pd.read_csv(baseline / "labels.csv.gz", usecols=["id", "k3", "k4"], dtype={"id": "string"})
    if set(labels["id"]) != set(listings["id"]) or not labels["id"].is_unique:
        raise ValueError("The baseline must provide one k=3 and k=4 label for each listing.")
    labels = labels.set_index("id").loc[listings["id"]]
    host_codes, _ = pd.factorize(listings["host_id"], sort=True)
    if (host_codes < 0).any():
        raise ValueError("Host account ID is required to calculate account weights.")
    host_sizes = np.bincount(host_codes)
    c2 = labels["k3"].to_numpy() == 2
    ablation = stay_length_ablation(listings, labels, 1 / host_sizes[host_codes], output)
    district = fixed_c2_map(listings, c2, host_codes, host_sizes, output)
    draw_comparison(geojson, district, output)
    shortlist_example(listings_path, listings, output)
    manifest = {"listing_sha256": data_hash, "listings": len(listings), "accounts": len(host_sizes),
                "fixed_k": 3, "fixed_cluster": "C2", "fixed_c2_listings": int(c2.sum()),
                "bootstrap_draws": BOOTSTRAPS, "confidence_interval": 0.95,
                "seed": SEED, "map_min_listings": DISPLAY_MIN_LISTINGS,
                "shortlist_example": {"nights": EXAMPLE_NIGHTS, "guest_count": 1,
                                      "budget_hkd_per_night": EXAMPLE_BUDGET_HKD,
                                      "room_type": "Private room", "amenity": "Kitchen"},
                "stay_ablation": "Drop only the transformed minimum_nights column after fitting baseline scaling."}
    (output / "followup_run.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(ablation.to_string(index=False))
    print(district.loc[district["listing_n"] >= DISPLAY_MIN_LISTINGS,
                       ["district", "listing_n", "listing_excess_pp", "account_excess_pp",
                        "account_ci_low_pp", "account_ci_high_pp"]].to_string(index=False))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for option in ("listings", "baseline", "geojson", "output"):
        parser.add_argument(f"--{option}", required=True, type=Path)
    args = parser.parse_args()
    with threadpool_limits(limits=2):
        run(args.listings, args.baseline, args.geojson, args.output)
