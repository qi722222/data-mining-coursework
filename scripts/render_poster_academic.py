"""Render the academic AIAA3111 poster at the same print size."""

import argparse
import csv
import json
import math
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "experiments/2026-11-19"
CHECKS = RESULTS / "market_checks"
WIDTH, HEIGHT = 800, 1000
NAVY, INK = "#142A3A", "#1B2F3F"
PAPER, WHITE = "#F5F3ED", "#FFFFFF"
SUBTLE, LINE = "#20252B", "#D9E1E3"
ACCENT = "#F3AA79"
CLUSTER = {"entire": "#276E82", "long": "#B55226", "short": "#675294"}
RIBBON = {"entire": "#87B7C0", "long": "#E7A67D", "short": "#B9ABD6"}
FONTS = {"regular": "Helvetica", "demi": "Helvetica-Bold", "bold": "Helvetica-Bold", "heavy": "Helvetica-Bold"}

HEADER_H = 98
BG_Y, BG_H = 106, 100
METH_Y, METH_H = 214, 112
RQ1_Y, RQ1_H = 334, 90
RQ2_Y, RQ2_H = 432, 208
RQ3_Y, RQ3_H = 648, 104
INT_Y, INT_H = 760, 128
DIS_Y, DIS_H = 896, 46
FOOT_Y = 950


def install_type():
    font = Path("/System/Library/Fonts/Avenir Next.ttc")
    if font.exists():
        for name, index in {"regular": 7, "demi": 2, "bold": 0, "heavy": 8}.items():
            font_name = f"AvenirNext-{name}"
            pdfmetrics.registerFont(TTFont(font_name, str(font), subfontIndex=index))
            FONTS[name] = font_name


def read_csv(path):
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def blend(a, b, weight):
    first, second = colors.HexColor(a), colors.HexColor(b)
    return colors.linearlyInterpolatedColor(first, second, 0, 1, max(0, min(1, weight)))


def tint(value):
    return colors.HexColor(value) if isinstance(value, str) else value


def require(rows, predicate, label):
    found = next((row for row in rows if predicate(row)), None)
    if found is None:
        raise ValueError(f"Missing {label}.")
    return found


def comb2(value):
    return value * (value - 1) / 2.0


def ari_from_counts(table):
    """Adjusted Rand index from a contingency table saved with the experiment."""
    total = sum(sum(row) for row in table)
    index = sum(comb2(value) for row in table for value in row)
    rows = sum(comb2(sum(row)) for row in table)
    columns = sum(comb2(sum(column)) for column in zip(*table))
    expected = rows * columns / comb2(total)
    return (index - expected) / (0.5 * (rows + columns) - expected)


class Poster:
    def __init__(self, output):
        self.pdf = canvas.Canvas(str(output), pagesize=(WIDTH * mm, HEIGHT * mm), pageCompression=1)
        self.pdf.setTitle("Beyond Room Type | Academic Research Poster")
        self.pdf.setAuthor("Jiaqi Li and Jialin Chen")
        self.pdf.setSubject("AIAA3111 Group 3 · 80 × 100 cm academic poster")
        self.pdf.scale(mm, mm)

    def text(self, x, y, value, size, face="regular", ink=INK, align="left"):
        self.pdf.setFont(FONTS[face], size)
        self.pdf.setFillColor(tint(ink))
        draw = {"left": self.pdf.drawString, "center": self.pdf.drawCentredString, "right": self.pdf.drawRightString}
        draw[align](x, HEIGHT - y, str(value))

    def width(self, value, size, face="regular"):
        return pdfmetrics.stringWidth(str(value), FONTS[face], size)

    def para(self, x, y, value, width, size, leading=None, face="regular", ink=INK):
        font, lines, next_line = FONTS[face], [], ""
        for word in value.split():
            combined = f"{next_line} {word}".strip()
            if next_line and pdfmetrics.stringWidth(combined, font, size) > width:
                lines.append(next_line)
                next_line = word
            else:
                next_line = combined
        if next_line:
            lines.append(next_line)
        step = leading or 1.32 * size
        for line in lines:
            self.text(x, y, line, size, face, ink)
            y += step
        return y

    def rect(self, x, y, width, height, fill, stroke=None, radius=0):
        self.pdf.setFillColor(tint(fill))
        if stroke:
            self.pdf.setStrokeColor(tint(stroke))
            self.pdf.setLineWidth(.45)
        if radius:
            self.pdf.roundRect(x, HEIGHT - y - height, width, height, radius, fill=1, stroke=bool(stroke))
        else:
            self.pdf.rect(x, HEIGHT - y - height, width, height, fill=1, stroke=bool(stroke))

    def line(self, x1, y1, x2, y2, color=LINE, weight=.55):
        self.pdf.setStrokeColor(tint(color))
        self.pdf.setLineWidth(weight)
        self.pdf.line(x1, HEIGHT - y1, x2, HEIGHT - y2)

    def dot(self, x, y, radius, fill, stroke=None):
        self.pdf.setFillColor(tint(fill))
        if stroke:
            self.pdf.setStrokeColor(tint(stroke))
            self.pdf.setLineWidth(.6)
        self.pdf.circle(x, HEIGHT - y, radius, stroke=bool(stroke), fill=1)

    def ribbon(self, x_left, x_right, a, b, height, fill):
        middle = (x_left + x_right) / 2
        path = self.pdf.beginPath()
        path.moveTo(x_left, HEIGHT - a)
        path.curveTo(middle - 18, HEIGHT - a, middle + 18, HEIGHT - b, x_right, HEIGHT - b)
        path.lineTo(x_right, HEIGHT - b - height)
        path.curveTo(middle + 18, HEIGHT - b - height, middle - 18, HEIGHT - a - height, x_left, HEIGHT - a - height)
        path.close()
        self.pdf.setFillColor(tint(fill))
        self.pdf.drawPath(path, fill=1, stroke=0)

    def tag(self, x, y, label, color):
        measured = self.width(label, 7.0, "bold")
        self.rect(x - measured / 2 - 2.8, y - 6.6, measured + 5.6, 10, WHITE, radius=2.2)
        self.text(x, y, label, 7.0, "bold", color, "center")

    def polygon(self, rings, project, fill):
        path = self.pdf.beginPath()
        for ring in rings:
            px, py = project(*ring[0][:2])
            path.moveTo(px, HEIGHT - py)
            for point in ring[1:]:
                px, py = project(*point[:2])
                path.lineTo(px, HEIGHT - py)
            path.close()
        self.pdf.setFillColor(tint(fill))
        self.pdf.setStrokeColor(tint(WHITE))
        self.pdf.setLineWidth(.35)
        self.pdf.drawPath(path, fill=1, stroke=1, fillMode=0)

    def heading(self, x, y, number, title, size=11.2):
        self.text(x, y, number, 7.4, "bold", ACCENT)
        self.text(x + self.width(number + "  ", 7.4, "bold"), y, title, size, "bold")

    def formula(self, x, y, host=False):
        self.text(x, y, "w", 11, "bold")
        self.text(x + 7.4, y + 2.4, "i", 6, "bold")
        if host:
            body = "=  1 / n"
            self.text(x + 12, y, body, 11, "bold")
            self.text(x + 12 + self.width(body, 11, "bold") + 0.3, y + 2.4, "h(i)", 5.6, "bold")
        else:
            self.text(x + 12, y, "=  1", 11, "bold")


def whole(value):
    number = float(value)
    return int(number) if number == int(number) else number


def listing_roles(profiles):
    entire = max(profiles, key=lambda key: float(profiles[key]["Entire home/apt (%)"]))
    rest = [key for key in profiles if key != entire]
    long_stay = max(rest, key=lambda key: float(profiles[key]["Min. nights (median)"]))
    short_stay = min(rest, key=lambda key: float(profiles[key]["Min. nights (median)"]))
    if len(rest) != 2 or long_stay == short_stay:
        raise ValueError("Listing-weighted k = 3 does not separate one entire-home group and two stay groups.")
    return {"entire": entire, "long": long_stay, "short": short_stay}


def host_roles(profiles):
    private = max(profiles, key=lambda key: float(profiles[key]["Private room (%)"]))
    rest = [key for key in profiles if key != private]
    smaller = min(rest, key=lambda key: (float(profiles[key]["Guests (median)"]), key))
    larger = max(rest, key=lambda key: (float(profiles[key]["Guests (median)"]), key))
    if len(rest) != 2 or float(profiles[smaller]["Guests (median)"]) == float(profiles[larger]["Guests (median)"]):
        raise ValueError("Host-weighted k = 3 does not separate private rooms from two capacity groups.")
    return {"smaller": smaller, "larger": larger, "private": private}


def majority_split(profiles):
    names = []
    for row in profiles.values():
        shares = {"Private rooms": float(row["Private room (%)"]), "Entire homes": float(row["Entire home/apt (%)"])}
        name, share = max(shares.items(), key=lambda item: item[1])
        if share < 90:
            return "Two groups"
        names.append(name)
    if set(names) == {"Private rooms", "Entire homes"}:
        return "Entire homes vs private rooms"
    return "Two groups"


def load(followups):
    sample = json.loads((RESULTS / "run.json").read_text())
    checks = json.loads((CHECKS / "checks.json").read_text())
    followup = json.loads((followups / "followup_run.json").read_text())
    if followup["listing_sha256"] != sample["source_sha256"]:
        raise ValueError("Follow-up tables do not match the baseline snapshot.")
    profiles = {int(row["cluster"]): row for row in read_csv(RESULTS / "cluster_profiles_all_k.csv") if int(row["k"]) == 3}
    k2 = {int(row["cluster"]): row for row in read_csv(RESULTS / "cluster_profiles_all_k.csv") if int(row["k"]) == 2}
    host = {int(row["cluster"]): row for row in read_csv(CHECKS / "host_weighted_profiles.csv")}
    transitions = {
        int(row["cluster"]): {cluster: int(row[str(cluster)]) for cluster in (1, 2, 3)}
        for row in read_csv(CHECKS / "host_weight_transitions.csv")
    }
    prices = {
        int(row["cluster"]): row for row in read_csv(CHECKS / "prices_within_room_type.csv")
        if row["room_type"] == "Private room"
    }
    roles, hosts = listing_roles(profiles), host_roles(host)
    if roles["long"] != int(str(followup["fixed_cluster"]).lstrip("C")):
        raise ValueError("The fixed map group is not the long-stay private cluster.")
    ablation = require(
        read_csv(followups / "stay_ablation_summary.csv"),
        lambda row: row["k"] == "3" and row["fit_weighting"] == "listing" and row["features"] == "without_minimum_nights",
        "minimum-nights ablation",
    )
    private_counts = [int(part) for part in ablation["private_rooms_by_cluster"].split("/") if part]
    rule_rows = read_csv(CHECKS / "private_rooms_28_night_rule.csv")
    rule_table = [[int(row["False"]), int(row["True"])] for row in rule_rows]
    scores = {int(row["k"]): row for row in read_csv(RESULTS / "k_sweep.csv")}
    heldout = read_csv(CHECKS / "price_prediction_held_out_hosts.csv")

    def mae(model):
        row = require(
            heldout,
            lambda item: item["subset"] == "Private room" and item["aggregation"] == "Pooled" and item["model"] == model,
            model,
        )
        return int(round(float(row["mae_hkd"])))

    ward = require(read_csv(CHECKS / "alternative_models.csv"), lambda row: row["method"] == "Ward" and row["k"] == "3", "Ward k=3")
    cross = require(read_csv(CHECKS / "cross_quarter.csv"), lambda row: row["subset"] == "all September", "September transfer")
    return {
        "sample": sample, "checks": checks, "roles": roles, "hosts": hosts,
        "profiles": profiles, "host_profiles": host, "transitions": transitions, "prices": prices,
        "k2_split": majority_split(k2),
        "silhouette": {k: float(scores[k]["silhouette_fixed_sample"]) for k in (2, 3)},
        "nmi2": float(scores[2]["room_type_nmi"]),
        "ablation_dominant": max(private_counts), "ablation_total": sum(private_counts),
        "stay_rule_ari": ari_from_counts(rule_table),
        "ward": float(ward["ari_vs_reference_k3"]),
        "transfer": float(cross["ari_frozen_vs_september_refit"]),
        "mae": {
            "base": mae("Room type + district"),
            "cluster": mae("Room type + district + cluster"),
            "nights": mae("Room type + district + minimum nights"),
            "both": mae("Room type + district + minimum nights + cluster"),
        },
        "districts": {row["district"]: row for row in read_csv(followups / "fixed_c2_district_weights.csv")},
        "map_min": int(followup["map_min_listings"]),
    }


def draw_header(p):
    p.rect(0, 0, WIDTH, HEIGHT, PAPER)
    p.rect(0, 0, WIDTH, HEADER_H, NAVY)
    p.rect(36, 16, 9, 2.4, ACCENT)
    p.text(50, 20, "AIAA3111  /  INTRODUCTION TO DATA MINING", 7, "demi", "#CFE1E8")
    p.text(764, 20, "GROUP 3", 7.4, "bold", ACCENT, "right")
    p.text(36, 54, "Beyond Room Type", 34, "heavy", WHITE)
    p.text(38, 74, "How Listing- and Host-Weighted Clustering Reveal Different Structures in Hong Kong Airbnb",
           10.6, "demi", "#DBE8ED")
    p.text(38, 90, "Jiaqi Li   ·   Jialin Chen   /   HKUST (Guangzhou)", 7.2, "demi", "#AFC4CF")


def draw_background(p, data):
    sample, checks = data["sample"], data["checks"]
    p.rect(29, BG_Y, 456, BG_H, WHITE, LINE, radius=5)
    p.heading(42, BG_Y + 16, "01", "Background")
    p.text(42, BG_Y + 32, "Why Does the Unit of Analysis Matter?", 8.4)
    p.para(42, BG_Y + 46, "Listings are often separate observations, but one account can manage many of them. "
           "Large accounts then carry more influence when every listing has equal weight.", 424, 6.5, 8.0, face="bold", ink=SUBTLE)
    p.text(42, BG_Y + 66, "Equal account weight asks whether those same listings would form different groups.",
           6.4, "bold", SUBTLE)
    share = checks["top_ten_host_listings"] / sample["listing_count"]
    stats = (
        (110, f"{sample['listing_count']:,}", "Listings"),
        (250, f"{checks['host_accounts']:,}", "Host accounts"),
        (392, f"{share:.1%}", "Held by the 10 largest accounts"),
    )
    for x, value, label in stats:
        p.text(x, BG_Y + 84, value, 12.5, "heavy", align="center")
        p.text(x, BG_Y + 94, label, 5.7, "demi", SUBTLE, "center")


def draw_questions(p):
    p.rect(497, BG_Y, 274, BG_H, WHITE, LINE, radius=5)
    p.heading(510, BG_Y + 16, "02", "Research Questions")
    questions = (
        ("RQ1", "Discover", "What patterns emerge from clustering these listings?"),
        ("RQ2", "Compare", "How does listing weight versus account weight change the clusters?"),
        ("RQ3", "Explain", "Which features and accounts explain the difference, and how robust is it?"),
    )
    y = BG_Y + 36
    for index, (code, verb, text) in enumerate(questions):
        p.rect(510, y - 4, 18, 18, NAVY, radius=2)
        p.text(519, y + 8, str(index + 1), 8, "bold", WHITE, "center")
        p.text(534, y + 3, f"{code}  ·  {verb}", 7.2)
        p.para(534, y + 13, text, 230, 6.3, 7.8, face="bold", ink=SUBTLE)
        if index < 2:
            p.line(519, y + 16, 519, y + 22, ACCENT, 1.1)
        y += 22


def draw_methodology(p, data):
    p.rect(29, METH_Y, 742, METH_H, WHITE, LINE, radius=5)
    p.heading(42, METH_Y + 15, "03", "Methodology")
    steps = (
        ("Snapshot", "Sept 2026 listings"),
        ("Features", "Room, size, stay, amenities"),
        ("Weighted K-Means", "Same features, two weights"),
        ("Compare", "ARI across partitions"),
        ("Explain", "Ablation and stability"),
    )
    box_w, gap, y = 128, 16, METH_Y + 40
    x = 42
    for index, (title, detail) in enumerate(steps):
        p.rect(x, y - 12, box_w, 28, "#F7F4EE", "#E3E8EA", radius=3)
        p.text(x + box_w / 2, y - 2, title, 7, align="center")
        p.text(x + box_w / 2, y + 9, detail, 5.8, "demi", SUBTLE, "center")
        if index < len(steps) - 1:
            p.line(x + box_w + 2, y + 2, x + box_w + gap - 3, y + 2, NAVY, .8)
            p.line(x + box_w + gap - 6, y - 1, x + box_w + gap - 2, y + 2, NAVY, .8)
            p.line(x + box_w + gap - 6, y + 5, x + box_w + gap - 2, y + 2, NAVY, .8)
        x += box_w + gap
    p.line(42, METH_Y + 66, 756, METH_Y + 66, "#E6ECED")
    p.text(42, METH_Y + 80, "Listing-weighted", 7.2, ink=CLUSTER["entire"])
    p.formula(148, METH_Y + 80, host=False)
    p.text(250, METH_Y + 80, "each listing counts equally", 6.4, "bold", SUBTLE)
    p.text(430, METH_Y + 80, "Host-weighted", 7.2)
    p.formula(520, METH_Y + 80, host=True)
    p.text(640, METH_Y + 80, "each account counts equally", 6.4, "bold", SUBTLE)
    p.para(42, METH_Y + 96, "Room type is one-hot encoded and eight amenities are binary. Accommodates, bedrooms, and minimum nights "
           "are log-transformed and standardized; each feature block is then variance-scaled. Price and district are excluded from "
           f"clustering and used only for interpretation. K-Means is fit for k = 2–8. The selection rule chooses k = 2; k = 3 is exploratory. "
           f"June ({data['checks']['cross_quarter']['june_listings']:,} listings) is used only to transfer labels.",
           712, 6.15, 7.6, face="bold", ink=SUBTLE)


def stack(order, sizes, top, gap, factor):
    positions, y = {}, top
    for key in order:
        positions[key] = y
        y += sizes[key] * factor + gap
    return positions


def draw_rq1(p, data):
    roles, profiles = data["roles"], data["profiles"]
    p.rect(29, RQ1_Y, 742, RQ1_H, WHITE, LINE, radius=5)
    p.heading(42, RQ1_Y + 15, "RQ1", "Baseline Clustering Reveals Room-Type Structure", 10.6)
    p.text(430, RQ1_Y + 14, f"{data['silhouette'][2]:.3f}", 12, "heavy")
    p.text(478, RQ1_Y + 14, "k = 2 silhouette", 6.3, "demi", SUBTLE)
    p.text(590, RQ1_Y + 14, f"{data['nmi2']:.3f}", 12, "heavy")
    p.text(638, RQ1_Y + 14, "room-type NMI", 6.3, "demi", SUBTLE)
    p.text(430, RQ1_Y + 30, f"{data['silhouette'][3]:.3f}", 12, "heavy", CLUSTER["long"])
    p.text(478, RQ1_Y + 30, "k = 3 silhouette, exploratory", 6.3, "demi", SUBTLE)
    rows = (
        ("entire", "Entire homes"),
        ("long", "Long-stay private rooms"),
        ("short", "Short-stay private rooms"),
    )
    p.text(78, RQ1_Y + 32, "Group", 6, "demi", SUBTLE)
    p.text(250, RQ1_Y + 32, "Listings", 6, "demi", SUBTLE, "right")
    p.text(360, RQ1_Y + 32, "Median minimum nights", 6, "demi", SUBTLE, "right")
    for index, (role, name) in enumerate(rows):
        row = profiles[roles[role]]
        y = RQ1_Y + 46 + index * 12
        p.dot(50, y - 1, 2.6, CLUSTER[role])
        p.text(60, y, name, 7, "bold", CLUSTER[role])
        p.text(250, y, f"{int(row['listings']):,}", 7, "demi", align="right")
        p.text(360, y, f"{whole(row['Min. nights (median)'])}", 7, "bold", align="right")
    p.text(42, RQ1_Y + 84, f"k = 2 is the selected solution ({data['k2_split'].lower()}). k = 3 is a finer exploratory resolution.",
           6.4, "bold", SUBTLE)


def draw_rq2(p, data):
    roles, hosts = data["roles"], data["hosts"]
    profiles, host_profiles = data["profiles"], data["host_profiles"]
    transitions = data["transitions"]
    left_order = [roles[name] for name in ("entire", "long", "short")]
    right_order = [hosts[name] for name in ("smaller", "larger", "private")]
    left_role = {roles[name]: name for name in ("entire", "long", "short")}
    right_role = {hosts[name]: name for name in ("smaller", "larger", "private")}
    left_names = {"entire": "Entire homes", "long": "Long-stay private rooms", "short": "Short-stay private rooms"}
    right_names = {"smaller": "Smaller entire homes", "larger": "Larger entire homes", "private": "Private rooms"}
    left_sizes = {key: sum(transitions[key].values()) for key in left_order}
    right_sizes = {key: sum(transitions[src][key] for src in left_order) for key in right_order}
    p.rect(29, RQ2_Y, 742, RQ2_H, WHITE, LINE, radius=5)
    p.heading(42, RQ2_Y + 16, "RQ2", "Weighting Changes Which Room Type Is Subdivided", 11.4)
    p.text(756, RQ2_Y + 12, f"{data['checks']['host_weight_ari']:.3f}", 16, "heavy", align="right")
    p.text(756, RQ2_Y + 24, "ARI between the two k = 3 partitions", 6.2, "demi", SUBTLE, "right")
    p.text(42, RQ2_Y + 32, "Colors mark listing-weighted groups. Host-weighted labels are a separate fit, not the same clusters.",
           6.3, "bold", SUBTLE)
    p.text(42, RQ2_Y + 48, "Listing-weighted", 7.4)
    p.text(596, RQ2_Y + 48, "Host-weighted", 7.4)
    gap, plot_h = 6, 118
    factor = (plot_h - gap * 2) / data["sample"]["listing_count"]
    top = RQ2_Y + 60
    left, right = stack(left_order, left_sizes, top, gap, factor), stack(right_order, right_sizes, top, gap, factor)
    sx, ex = 230, 560
    used_l, used_r, tags = dict(left), dict(right), []
    for src in left_order:
        for dst in right_order:
            count = transitions[src][dst]
            if not count:
                continue
            thickness = count * factor
            y1, y2 = used_l[src], used_r[dst]
            role = left_role[src]
            p.ribbon(sx, ex, y1, y2, thickness, RIBBON[role])
            if count >= 750:
                tags.append(((y1 + y2 + thickness) / 2, f"{count:,}", CLUSTER[role]))
            used_l[src] += thickness
            used_r[dst] += thickness
    for y, label, color in tags:
        p.tag((sx + ex) / 2, y + 2, label, color)
    for key in left_order:
        role, height, y = left_role[key], left_sizes[key] * factor, left[key]
        p.rect(sx - 6, y, 6, height, CLUSTER[role])
        mid = y + height / 2
        p.text(42, mid - 1, left_names[role], 7.2, "bold", CLUSTER[role])
        nights = whole(profiles[key]["Min. nights (median)"])
        p.text(42, mid + 8.5, f"{nights}-night median  ·  {left_sizes[key]:,}", 6.1, "demi", SUBTLE)
    for key in right_order:
        role, height, y = right_role[key], right_sizes[key] * factor, right[key]
        p.rect(ex, y, 6, height, NAVY)
        mid = y + max(height, 14) / 2
        detail = (f"{right_sizes[key]:,} listings together" if role == "private"
                  else f"{whole(host_profiles[key]['Guests (median)'])} guests median  ·  {right_sizes[key]:,}")
        p.text(578, mid - 1, right_names[role], 7.2, "bold")
        p.text(578, mid + 8.5, detail, 6.1, "demi", SUBTLE)
    p.text(42, RQ2_Y + 198, "Listing weighting subdivides private rooms by minimum stay; host weighting subdivides entire homes by capacity.",
           7.6, "bold")


def draw_rq3(p, data):
    checks = data["checks"]
    p.rect(29, RQ3_Y, 742, RQ3_H, WHITE, LINE, radius=5)
    p.heading(42, RQ3_Y + 15, "RQ3", "Feature Ablation and Account Sensitivity Explain the Results", 10.4)
    p.rect(42, RQ3_Y + 28, 250, 64, "#F8F1EA", radius=3)
    p.text(54, RQ3_Y + 42, "Minimum nights drive the private-room split", 7, ink=CLUSTER["long"])
    p.text(54, RQ3_Y + 60, f"{data['ablation_dominant']:,} / {data['ablation_total']:,}", 13, "heavy", CLUSTER["long"])
    p.text(54, RQ3_Y + 74, "private rooms fall into one cluster without minimum nights", 5.9, "demi", SUBTLE)
    p.text(54, RQ3_Y + 86, f"28-night rule vs private-room split: ARI {data['stay_rule_ari']:.3f}", 6.2, "demi")
    rows = (
        ("Paired 80% host refits", checks["host_resample_ari_q25_median_q75"][1]),
        ("Refit without 5 largest accounts", checks["remove_top_five_host_ari"]),
        ("June fit on September listings", data["transfer"]),
    )
    p.text(320, RQ3_Y + 40, "Stable under random refits, sensitive to large accounts", 7)
    for index, (label, value) in enumerate(rows):
        y = RQ3_Y + 56 + index * 12
        p.text(320, y, label, 6.5, "demi")
        p.text(620, y, f"{value:.3f}", 8, "heavy", align="right")
    p.text(320, RQ3_Y + 94, f"The five largest accounts hold {checks['top_five_host_listings']:,} listings. "
           f"Ward vs K-Means at k = 3: ARI {data['ward']:.3f}.", 6, "bold", SUBTLE)
    p.para(636, RQ3_Y + 56, "High agreement between random refits does not mean the result is independent of account concentration.",
           120, 6.2, 7.8, face="bold", ink=SUBTLE)


def draw_interpretation(p, data):
    roles, prices = data["roles"], data["prices"]
    p.rect(29, INT_Y, 360, INT_H, WHITE, LINE, radius=5)
    p.text(42, INT_Y + 15, "Cluster Differences and Minimum-Stay Rules", 8.6)
    p.text(42, INT_Y + 28, "Advertised nightly price was not used to form the clusters.", 6, "bold", SUBTLE)
    x_min, x_max = 96, 250
    project = lambda price: x_min + float(price) * (x_max - x_min) / 900
    for tick in (0, 300, 600, 900):
        x = project(tick)
        p.line(x, INT_Y + 40, x, INT_Y + 78, "#E6EBED")
        p.text(x, INT_Y + 86, str(tick), 5.6, "demi", SUBTLE, "center")
    for index, role in enumerate(("long", "short")):
        values = prices[roles[role]]
        y = INT_Y + 50 + index * 18
        first, middle, last = [project(values[field]) for field in ("q25_hkd", "median_hkd", "q75_hkd")]
        p.text(42, y + 2, "Long" if role == "long" else "Short", 6.4, "bold", CLUSTER[role])
        p.line(first, y, last, y, RIBBON[role], 3)
        p.dot(middle, y, 2.2, CLUSTER[role], WHITE)
        label_y = y - 7 if role == "long" else y + 8
        p.text(middle, label_y, f"HK${round(float(values['median_hkd'])):,}", 6.5, "bold", CLUSTER[role], "center")
        p.text(346, y + 2, f"{int(values['priced']):,} / {int(values['listings']):,}", 5.8, "demi", SUBTLE, "right")
    mae = data["mae"]
    p.text(42, INT_Y + 108, f"Held-out MAE: HK${mae['base']:,} room + district; HK${mae['cluster']:,} + cluster; "
           f"HK${mae['nights']:,} + nights; HK${mae['both']:,} both.", 6, "bold", SUBTLE)
    p.text(42, INT_Y + 120, "Minimum nights capture most of the price signal in this split.", 6.3, "bold")

    p.rect(401, INT_Y, 370, INT_H, WHITE, LINE, radius=5)
    p.text(414, INT_Y + 15, "Geographic Concentration Depends on Weighting", 8.4)
    p.text(414, INT_Y + 27, "Excess share: observed long-stay private share minus the room-mix expectation. C2 membership is held fixed.",
           5.7, "bold", SUBTLE)
    shapes, projection = district_geometry()
    for mode, center, title in (("listing", 490, "Listing-weighted"), ("account", 676, "Host-weighted")):
        p.text(center, INT_Y + 40, title, 6.2, align="center")
        project = projection(center, INT_Y + 44, 150, 42)
        for name, polygons in shapes.items():
            row = data["districts"][name]
            shade = map_color(float(row[f"{mode}_excess_pp"])) if int(float(row["listing_n"])) >= data["map_min"] else "#CCD7DF"
            for rings in polygons:
                p.polygon(rings, project, shade)
    p.text(414, INT_Y + 96, "Wan Chai", 6.3, "bold")
    wan = data["districts"]["Wan Chai"]
    p.text(500, INT_Y + 96, f"{float(wan['listing_excess_pp']):+.1f}  →  {float(wan['account_excess_pp']):+.1f} pp", 6.3, "demi")
    p.text(650, INT_Y + 96, f"[{float(wan['account_ci_low_pp']):+.1f}, {float(wan['account_ci_high_pp']):+.1f}]", 5.8, ink=SUBTLE)
    yau = data["districts"]["Yau Tsim Mong"]
    p.text(414, INT_Y + 107, "Yau Tsim Mong", 6.3, "bold")
    p.text(500, INT_Y + 107, f"{float(yau['listing_excess_pp']):+.1f}  →  {float(yau['account_excess_pp']):+.1f} pp", 6.3, "demi")
    p.text(650, INT_Y + 107, f"[{float(yau['account_ci_low_pp']):+.1f}, {float(yau['account_ci_high_pp']):+.1f}]", 5.8, ink=SUBTLE)
    p.rect(414, INT_Y + 116, 7, 3.2, "#675294")
    p.text(423, INT_Y + 119, "below", 5.2, "demi", SUBTLE)
    p.rect(448, INT_Y + 116, 7, 3.2, "#AE5227")
    p.text(457, INT_Y + 119, "above", 5.2, "demi", SUBTLE)
    p.rect(484, INT_Y + 116, 7, 3.2, "#CCD7DF")
    p.text(493, INT_Y + 119, "under 50 listings · 95% host-bootstrap intervals", 5.2, "demi", SUBTLE)


def district_geometry():
    geography = json.loads((ROOT / "data/hong-kong-2026-09-20-neighbourhoods.geojson").read_text())["features"]
    shapes = {}
    for feature in geography:
        item = feature["geometry"]
        shapes[feature["properties"]["neighbourhood"]] = (
            [item["coordinates"]] if item["type"] == "Polygon" else item["coordinates"]
        )
    points = [point for polygons in shapes.values() for rings in polygons for ring in rings for point in ring]
    lon_lo, lon_hi = min(pt[0] for pt in points), max(pt[0] for pt in points)
    lat_lo, lat_hi = min(pt[1] for pt in points), max(pt[1] for pt in points)
    ratio = math.cos(math.radians((lat_lo + lat_hi) / 2))

    def projection(center_x, top, width, height):
        scale = min(width / ((lon_hi - lon_lo) * ratio), height / (lat_hi - lat_lo))
        left = center_x - (lon_hi - lon_lo) * ratio * scale / 2
        return lambda lon, lat: (left + (lon - lon_lo) * ratio * scale, top + (lat_hi - lat) * scale)

    return shapes, projection


def map_color(diff):
    return blend("#F1EDE4", "#675294" if diff < 0 else "#AE5227", abs(diff) / 35)


def draw_discussion(p):
    p.rect(29, DIS_Y, 742, DIS_H, WHITE, LINE, radius=5)
    p.heading(42, DIS_Y + 13, "06", "Discussion", 10)
    points = (
        (42, "Perspective", "Weighting changes which structure the same listings emphasize."),
        (292, "Interpretation", "A clear cluster need not be its own market segment."),
        (542, "Influence", "Random agreement does not remove large-account sensitivity."),
    )
    for x, title, text in points:
        p.text(x, DIS_Y + 25, title, 6.4)
        p.text(x, DIS_Y + 34, text, 5.8, "bold", SUBTLE)
    p.text(42, DIS_Y + 43, "A sensitivity result, not one correct segmentation. Host IDs stand in for providers.",
           5.5, "bold", SUBTLE)


def draw_footer(p):
    p.rect(0, FOOT_Y, WIDTH, HEIGHT - FOOT_Y, NAVY)
    p.text(36, FOOT_Y + 10, "07  ·  CONCLUSION", 6.2, "bold", ACCENT)
    p.text(36, FOOT_Y + 22, "The unit of analysis changes the clustering structure found in these Hong Kong Airbnb listings.",
           8.6, "bold", WHITE)
    p.text(36, FOOT_Y + 33, "Listing weights separate private rooms by minimum stay. Host weights separate entire homes by capacity.",
           6.2, "demi", "#D5E3EA")
    p.text(36, FOOT_Y + 40, "Interpret the clusters with the features, the weights, and the concentration of host accounts.",
           6.1, "demi", "#D5E3EA")
    p.text(36, FOOT_Y + 48, "Inside Airbnb  ·  Hong Kong  ·  June and September 2026  ·  CC BY 4.0", 5.7, "demi", "#C3D6DF")
    p.text(764, FOOT_Y + 48, "insideairbnb.com/get-the-data", 5.7, "demi", "#C3D6DF", "right")
    p.pdf.linkURL("https://insideairbnb.com/get-the-data/",
                  (620, HEIGHT - (FOOT_Y + 56), 766, HEIGHT - (FOOT_Y + 46)), relative=1)


def render(output, preview, followups):
    data = load(followups)
    install_type()
    output.parent.mkdir(parents=True, exist_ok=True)
    poster = Poster(output)
    draw_header(poster)
    draw_background(poster, data)
    draw_questions(poster)
    draw_methodology(poster, data)
    draw_rq1(poster, data)
    draw_rq2(poster, data)
    draw_rq3(poster, data)
    draw_interpretation(poster, data)
    draw_discussion(poster)
    draw_footer(poster)
    poster.pdf.showPage()
    poster.pdf.save()
    if preview:
        import pypdfium2 as pdfium
        document = pdfium.PdfDocument(str(output))
        if len(document) != 1:
            raise ValueError("The academic poster must be one page.")
        page = document[0]
        width, height = page.get_size()
        expected = (WIDTH * 72 / 25.4, HEIGHT * 72 / 25.4)
        if abs(width - expected[0]) > 1 or abs(height - expected[1]) > 1:
            raise ValueError(f"Unexpected page size {width:.1f} x {height:.1f} pt.")
        page.render(scale=1800 / page.get_width()).to_pil().save(preview)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=ROOT / "poster/Group3_Poster_Academic.pdf")
    parser.add_argument("--preview", type=Path, default=ROOT / "poster/Group3_Poster_Academic.png")
    parser.add_argument("--followups", type=Path, default=ROOT / "experiments/2026-11-21")
    args = parser.parse_args()
    render(args.pdf, args.preview, args.followups)
