"""Academic reorganization of the Group 3 final poster. 80 x 100 cm."""

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
BODY, LINE = "#20252B", "#D9E1E3"
ACCENT = "#F3AA79"
CLUSTER = {"entire": "#276E82", "long": "#B55226", "short": "#675294"}
RIBBON = {"entire": "#87B7C0", "long": "#E7A67D", "short": "#B9ABD6"}
FONTS = {"regular": "Helvetica", "demi": "Helvetica-Bold", "bold": "Helvetica-Bold", "heavy": "Helvetica-Bold"}

# Reported on Group3_Poster_Final. These snapshot, threshold, and calendar
# figures are not stored in the local experiment tables.
REPORTED = {
    "dec_listings": 6630,
    "march_private_rooms": 882,
    "march_max_minimum_nights": 7,
    "threshold": (
        ("June", "28 nights", 76, 25),
        ("June", "29 nights", 821, 33),
        ("September", "28 nights", 79, 31),
        ("September", "29 nights", 799, 39),
    ),
    "accounts_supplying_new_matches": 9,
    "calendar_pool": 2496,
    "calendar": ((275, 1341), (95, 1402), (6, 1009)),
}

HEADER_H = 76
BG_Y, BG_H = 84, 94
METH_Y, METH_H = 186, 84
RQ1_Y, RQ1_H = 278, 62
RQ2_Y, RQ2_H = 348, 176
RQ3_Y, RQ3_H = 532, 122
PRAC_Y, PRAC_H = 662, 176
DIS_Y, DIS_H = 846, 56
FOOT_Y = 910


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


def tint(value):
    return colors.HexColor(value) if isinstance(value, str) else value


def whole(value):
    number = float(value)
    return int(number) if number == int(number) else number


def require(rows, predicate, label):
    found = next((row for row in rows if predicate(row)), None)
    if found is None:
        raise ValueError(f"Missing {label}.")
    return found


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

    def para(self, x, y, value, width, size, leading=None, face="regular", ink=BODY):
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
        measured = self.width(label, 6.6, "bold")
        self.rect(x - measured / 2 - 2.4, y - 5.6, measured + 4.8, 8.6, WHITE, radius=2)
        self.text(x, y, label, 6.6, "bold", color, "center")

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

    def heading(self, x, y, number, title, size=10.4):
        self.text(x, y, number, 7, "bold", ACCENT)
        self.text(x + self.width(number + "  ", 7, "bold"), y, title, size, "bold")

    def formula(self, x, y, host=False):
        self.text(x, y, "w", 9.5, "bold")
        self.text(x + 6.2, y + 2.1, "i", 5.2, "bold")
        if host:
            body = "= 1 / n"
            self.text(x + 10, y, body, 9.5, "bold")
            self.text(x + 10 + self.width(body, 9.5, "bold") + 0.2, y + 2.1, "h(i)", 5, "bold")
        else:
            self.text(x + 10, y, "= 1", 9.5, "bold")


def listing_roles(profiles):
    entire = max(profiles, key=lambda key: float(profiles[key]["Entire home/apt (%)"]))
    rest = [key for key in profiles if key != entire]
    long_stay = max(rest, key=lambda key: float(profiles[key]["Min. nights (median)"]))
    short_stay = min(rest, key=lambda key: float(profiles[key]["Min. nights (median)"]))
    return {"entire": entire, "long": long_stay, "short": short_stay}


def host_roles(profiles):
    private = max(profiles, key=lambda key: float(profiles[key]["Private room (%)"]))
    rest = [key for key in profiles if key != private]
    smaller = min(rest, key=lambda key: float(profiles[key]["Guests (median)"]))
    larger = max(rest, key=lambda key: float(profiles[key]["Guests (median)"]))
    return {"smaller": smaller, "larger": larger, "private": private}


def load(followups):
    import pandas as pd

    sample = json.loads((RESULTS / "run.json").read_text())
    checks = json.loads((CHECKS / "checks.json").read_text())
    followup = json.loads((followups / "followup_run.json").read_text())
    if followup["listing_sha256"] != sample["source_sha256"]:
        raise ValueError("Follow-up tables do not match the September snapshot.")
    profiles = {int(row["cluster"]): row for row in read_csv(RESULTS / "cluster_profiles_all_k.csv") if int(row["k"]) == 3}
    host = {int(row["cluster"]): row for row in read_csv(CHECKS / "host_weighted_profiles.csv")}
    transitions = {
        int(row["cluster"]): {cluster: int(row[str(cluster)]) for cluster in (1, 2, 3)}
        for row in read_csv(CHECKS / "host_weight_transitions.csv")
    }
    prices = {
        int(row["cluster"]): row for row in read_csv(CHECKS / "prices_within_room_type.csv")
        if row["room_type"] == "Private room"
    }
    ablation = require(
        read_csv(followups / "stay_ablation_summary.csv"),
        lambda row: row["k"] == "3" and row["fit_weighting"] == "listing" and row["features"] == "without_minimum_nights",
        "minimum-nights ablation",
    )
    private_counts = [int(part) for part in ablation["private_rooms_by_cluster"].split("/") if part]
    labels = pd.read_csv(RESULTS / "labels.csv.gz")
    listings = pd.read_csv(
        ROOT / "data/hong-kong-2026-09-20-listings.csv.gz",
        usecols=["id", "host_id"],
    )
    joined = labels.merge(listings, on="id")
    joined["weight"] = 1 / joined.groupby("host_id")["id"].transform("size")
    roles = listing_roles(profiles)
    long_id = roles["long"]
    long_rows = joined[joined["k3"] == long_id]
    listing_share = len(long_rows) / len(joined)
    host_share = long_rows["weight"].sum() / joined["weight"].sum()
    top_ten = long_rows.groupby("host_id").size().sort_values(ascending=False).head(10).sum()
    concentration = top_ten / len(long_rows)
    hosts = host_roles(host)
    expected = {
        roles["entire"]: {hosts["smaller"]: 1566, hosts["larger"]: 950},
        roles["long"]: {hosts["private"]: 2204},
        roles["short"]: {hosts["private"]: 1863},
    }
    for source, destinations in expected.items():
        for destination, count in destinations.items():
            if transitions[source][destination] != count:
                raise ValueError(f"Unexpected flow {source}->{destination}: {transitions[source][destination]}")
    if (round(listing_share * 100, 1), round(host_share * 100, 1), round(concentration * 100)) != (33.6, 9.4, 76):
        raise ValueError("C2 weight or concentration does not match the final poster.")
    if (max(private_counts), sum(private_counts)) != (3992, 4003):
        raise ValueError("Ablation counts do not match the final poster.")
    if checks["cross_quarter"]["june_listings"] != 6734 or sample["listing_count"] != 6614:
        raise ValueError("Snapshot sizes do not match the checked June and September files.")
    return {
        "sample": sample,
        "checks": checks,
        "profiles": profiles,
        "host": host,
        "roles": roles,
        "hosts": hosts,
        "transitions": transitions,
        "prices": prices,
        "ablation": (max(private_counts), sum(private_counts)),
        "listing_share": listing_share,
        "host_share": host_share,
        "concentration": concentration,
        "june_listings": checks["cross_quarter"]["june_listings"],
    }


def draw_header(p):
    p.rect(0, 0, WIDTH, HEIGHT, PAPER)
    p.rect(0, 0, WIDTH, HEADER_H, NAVY)
    p.rect(36, 14, 9, 2.2, ACCENT)
    p.text(50, 17.5, "AIAA3111  /  INTRODUCTION TO DATA MINING", 6.6, "demi", "#CFE1E8")
    p.text(764, 17.5, "GROUP 3", 7, "bold", ACCENT, "right")
    p.text(36, 44, "Beyond Room Type", 26, "heavy", WHITE)
    p.text(38, 58, "How Listing- and Host-Weighted Clustering Reveal Different Structures in Hong Kong Airbnb",
           8.2, "demi", "#DBE8ED")
    p.text(38, 70, "Jiaqi Li   ·   Jialin Chen   /   HKUST (Guangzhou)", 6.6, "demi", "#AFC4CF")


def draw_background(p, data):
    sample = data["sample"]
    p.rect(29, BG_Y, 456, BG_H, WHITE, LINE, radius=5)
    p.heading(42, BG_Y + 14, "01", "Background")
    p.text(42, BG_Y + 28, "Why Does the Unit of Analysis Matter?", 8)
    p.para(42, BG_Y + 40, "Listings are often treated as separate observations, but one host account can manage many of them. "
           "Listing weights then give large accounts more influence. Host weights give each account the same total weight.",
           424, 6.2, 7.6, face="bold")
    p.text(42, BG_Y + 64, "Would the same listings form different groups if each account had equal total weight?",
           6.2, "bold", BODY)
    stats = (
        (108, f"{sample['listing_count']:,}", "September listings"),
        (250, f"{data['checks']['host_accounts']:,}", "Host accounts"),
        (392, f"{data['concentration']:.0%}", "of C2 from 10 accounts"),
    )
    for x, value, label in stats:
        p.text(x, BG_Y + 80, value, 11, "heavy", align="center")
        p.text(x, BG_Y + 89, label, 5.4, "demi", BODY, "center")


def draw_questions(p):
    p.rect(497, BG_Y, 274, BG_H, WHITE, LINE, radius=5)
    p.heading(510, BG_Y + 14, "02", "Research Questions")
    questions = (
        ("RQ1", "Discover", "What patterns emerge from clustering these listings?"),
        ("RQ2", "Compare", "How does listing weight versus account weight change the clusters?"),
        ("RQ3", "Explain", "What explains the difference, and does it persist over time?"),
    )
    y = BG_Y + 32
    for index, (code, verb, text) in enumerate(questions):
        p.rect(510, y - 3, 16, 16, NAVY, radius=2)
        p.text(518, y + 7.5, str(index + 1), 7.2, "bold", WHITE, "center")
        p.text(532, y + 2, f"{code}  ·  {verb}", 6.8)
        p.para(532, y + 11, text, 220, 5.9, 7.2, face="bold")
        y += 20


def draw_methodology(p, data):
    p.rect(29, METH_Y, 742, METH_H, WHITE, LINE, radius=5)
    p.heading(42, METH_Y + 13, "03", "Methodology")
    steps = (
        ("Four snapshots", "Sep 2026 is primary"),
        ("Features", "Room, size, stay, amenities"),
        ("K-Means, k = 3", "Exploratory resolution"),
        ("Two weights", "Listing or host account"),
        ("Check", "Ablation and time"),
    )
    box_w, gap, y = 128, 16, METH_Y + 36
    x = 42
    for index, (title, detail) in enumerate(steps):
        p.rect(x, y - 11, box_w, 26, "#F7F4EE", "#E3E8EA", radius=3)
        p.text(x + box_w / 2, y - 2, title, 6.5, align="center")
        p.text(x + box_w / 2, y + 8, detail, 5.4, "demi", BODY, "center")
        if index < len(steps) - 1:
            p.line(x + box_w + 2, y + 2, x + box_w + gap - 3, y + 2, NAVY, .8)
        x += box_w + gap
    p.text(42, METH_Y + 64, "Listing-weighted", 6.6, ink=CLUSTER["entire"])
    p.formula(130, METH_Y + 64, host=False)
    p.text(196, METH_Y + 64, "each listing counts equally", 6, "bold", BODY)
    p.text(390, METH_Y + 64, "Host-weighted", 6.6)
    p.formula(470, METH_Y + 64, host=True)
    p.text(560, METH_Y + 64, "each account counts equally", 6, "bold", BODY)
    p.text(42, METH_Y + 78, "Price and district are held out of the fit. k = 3 examines a finer structure; it is not claimed as the unique optimum. "
           f"June has {data['june_listings']:,} listings; December 2025 has {REPORTED['dec_listings']:,}.",
           6, "bold", BODY)


def draw_rq1(p, data):
    roles, profiles = data["roles"], data["profiles"]
    p.rect(29, RQ1_Y, 742, RQ1_H, WHITE, LINE, radius=5)
    p.heading(42, RQ1_Y + 13, "RQ1", "Listing-Weighted Clustering Reveals Three Accommodation Profiles", 9.6)
    rows = (
        ("entire", "Entire homes"),
        ("long", "Long-stay private rooms"),
        ("short", "Short-stay private rooms"),
    )
    x = 42
    for role, name in rows:
        row = profiles[roles[role]]
        p.dot(x + 3, RQ1_Y + 36, 2.4, CLUSTER[role])
        p.text(x + 10, RQ1_Y + 34, name, 6.6, "bold", CLUSTER[role])
        p.text(x + 10, RQ1_Y + 44, f"{int(row['listings']):,} listings", 6, "demi", BODY)
        p.text(x + 10, RQ1_Y + 54, f"{whole(row['Min. nights (median)'])}-night median minimum", 6, ink=BODY)
        x += 175
    p.para(560, RQ1_Y + 34, "At k = 3, listing weights subdivide private rooms mainly by minimum stay.",
           190, 6.2, 7.6, face="bold")


def draw_rq2(p, data):
    roles, hosts = data["roles"], data["hosts"]
    profiles, host_profiles = data["profiles"], data["host"]
    transitions = data["transitions"]
    left_order = [roles[name] for name in ("entire", "long", "short")]
    right_order = [hosts[name] for name in ("smaller", "larger", "private")]
    left_role = {roles[name]: name for name in roles}
    right_role = {hosts[name]: name for name in hosts}
    left_names = {"entire": "Entire homes", "long": "Long-stay private rooms", "short": "Short-stay private rooms"}
    right_names = {"smaller": "Smaller entire homes", "larger": "Larger entire homes", "private": "Private rooms"}
    left_sizes = {key: sum(transitions[key].values()) for key in left_order}
    right_sizes = {key: sum(transitions[src][key] for src in left_order) for key in right_order}
    p.rect(29, RQ2_Y, 742, RQ2_H, WHITE, LINE, radius=5)
    p.heading(42, RQ2_Y + 14, "RQ2", "Weighting Changes Which Room Type Is Subdivided", 10.2)
    p.text(756, RQ2_Y + 13, f"C2 weight  {data['listing_share']:.1%} to {data['host_share']:.1%}", 7.4, "bold", align="right")
    p.text(756, RQ2_Y + 22, "Same C2 listings, share of total weight", 5.4, "demi", BODY, "right")
    p.text(42, RQ2_Y + 28, "Same September listings. Colors mark the listing-weighted groups. Host labels are a separate fit.",
           6, "bold", BODY)
    p.text(42, RQ2_Y + 42, "Listing-weighted", 6.8)
    p.text(590, RQ2_Y + 42, "Host-weighted", 6.8)
    gap, plot_h = 5, 96
    factor = (plot_h - gap * 2) / data["sample"]["listing_count"]
    top = RQ2_Y + 52

    def stack(order, sizes):
        positions, y = {}, top
        for key in order:
            positions[key] = y
            y += sizes[key] * factor + gap
        return positions

    left, right = stack(left_order, left_sizes), stack(right_order, right_sizes)
    sx, ex = 228, 548
    used_l, used_r, tags = dict(left), dict(right), []
    for src in left_order:
        for dst in right_order:
            count = transitions[src][dst]
            if not count:
                continue
            thickness = max(count * factor, 0.35)
            y1, y2 = used_l[src], used_r[dst]
            p.ribbon(sx, ex, y1, y2, count * factor, RIBBON[left_role[src]])
            if count >= 750:
                tags.append(((y1 + y2 + count * factor) / 2, f"{count:,}", CLUSTER[left_role[src]]))
            used_l[src] += count * factor
            used_r[dst] += count * factor
    for y, label, color in tags:
        p.tag((sx + ex) / 2, y + 1.5, label, color)
    for key in left_order:
        role, height, y = left_role[key], left_sizes[key] * factor, left[key]
        p.rect(sx - 5, y, 5, height, CLUSTER[role])
        mid = y + height / 2
        p.text(42, mid - 1, left_names[role], 6.6, "bold", CLUSTER[role])
        nights = whole(profiles[key]["Min. nights (median)"])
        p.text(42, mid + 8, f"{nights}-night median  ·  {left_sizes[key]:,}", 5.7, "demi", BODY)
    for key in right_order:
        role, height, y = right_role[key], right_sizes[key] * factor, right[key]
        p.rect(ex, y, 5, height, NAVY)
        mid = y + max(height, 12) / 2
        p.text(566, mid - 1, right_names[role], 6.6, "bold")
        if role == "private":
            detail = f"{right_sizes[key]:,} listings together"
        else:
            detail = f"{whole(host_profiles[key]['Guests (median)'])} guests median  ·  {right_sizes[key]:,}"
        p.text(566, mid + 8, detail, 5.7, "demi", BODY)
    p.text(42, RQ2_Y + 158, "Listing weights split private rooms by minimum stay. Host weights split entire homes by capacity.",
           6.3, "bold")
    p.text(756, RQ2_Y + 168, "Main flows labeled. Residual transitions: 15, 8 and 8 listings. Ten accounts hold 76% of C2.",
           5.5, "bold", BODY, "right")


def draw_rq3(p, data):
    roles, profiles, prices = data["roles"], data["profiles"], data["prices"]
    p.rect(29, RQ3_Y, 360, RQ3_H, WHITE, LINE, radius=5)
    p.heading(42, RQ3_Y + 13, "RQ3", "Minimum Stay Explains the Private-Room Split", 8.6)
    dominant, total = data["ablation"]
    p.rect(42, RQ3_Y + 24, 150, 36, "#F8F1EA", radius=3)
    p.text(50, RQ3_Y + 36, f"{dominant:,} / {total:,}", 11, "heavy", CLUSTER["long"])
    p.text(50, RQ3_Y + 48, "private rooms, one cluster", 5.5, "demi", BODY)
    p.text(50, RQ3_Y + 56, "after dropping minimum nights", 5.5, "bold", BODY)
    long_row, short_row = profiles[roles["long"]], profiles[roles["short"]]
    long_price, short_price = prices[roles["long"]], prices[roles["short"]]
    rows = (
        ("Nights", f"{whole(long_row['Min. nights (median)'])}", f"{whole(short_row['Min. nights (median)'])}"),
        ("Guests", f"{whole(long_row['Guests (median)'])}", f"{whole(short_row['Guests (median)'])}"),
        ("Kitchen", f"{round(float(long_row['Kitchen (%)']))}%", f"{round(float(short_row['Kitchen (%)']))}%"),
        ("Price", f"HK${round(float(long_price['median_hkd'])):,}", f"HK${round(float(short_price['median_hkd'])):,}"),
    )
    p.text(300, RQ3_Y + 32, "C2", 6, "bold", CLUSTER["long"], "right")
    p.text(360, RQ3_Y + 32, "C3", 6, "bold", CLUSTER["short"], "right")
    for index, (label, left, right) in enumerate(rows):
        y = RQ3_Y + 44 + index * 10
        p.text(206, y, label, 5.8, ink=BODY)
        p.text(300, y, left, 5.8, "demi", align="right")
        p.text(360, y, right, 5.8, "demi", align="right")
    p.text(206, RQ3_Y + 88, f"Priced {int(long_price['priced']):,}/{int(long_price['listings']):,} and "
           f"{int(short_price['priced']):,}/{int(short_price['listings']):,}.", 5.3, "bold", BODY)
    p.text(206, RQ3_Y + 96, "Price was not used to form the clusters.", 5.3, "bold", BODY)
    p.text(42, RQ3_Y + 112, "This describes the fit, not a cause of demand.", 5.5, "bold", BODY)

    p.rect(401, RQ3_Y, 370, RQ3_H, WHITE, LINE, radius=5)
    p.heading(414, RQ3_Y + 13, "RQ3", "The Shift Appears in Three of Four Snapshots", 8.2)
    columns = (
        ("Dec 2025", f"{REPORTED['dec_listings']:,}", "Private rooms\nby stay", "Entire homes\nby capacity", False),
        ("Mar 2026", f"{REPORTED['march_private_rooms']:,} private", "Entire homes\nby capacity", "Entire homes\nby capacity", True),
        ("Jun 2026", f"{data['june_listings']:,}", "Private rooms\nby stay", "Entire homes\nby capacity", False),
        ("Sep 2026", f"{data['sample']['listing_count']:,}", "Private rooms\nby stay", "Entire homes\nby capacity", False),
    )
    for index, (name, count, listing, host, exception) in enumerate(columns):
        x = 414 + index * 88
        p.rect(x, RQ3_Y + 28, 82, 78, "#F8F1EA" if exception else "#F7F4EE", radius=3)
        p.text(x + 6, RQ3_Y + 40, name, 6.4, ink=CLUSTER["long"] if exception else INK)
        p.text(x + 6, RQ3_Y + 50, count, 5.6, "demi", BODY)
        p.text(x + 6, RQ3_Y + 62, "Listing", 5.2, ink=CLUSTER["entire"])
        p.text(x + 6, RQ3_Y + 70, listing.replace("\n", " "), 5.1, "bold", BODY)
        p.text(x + 6, RQ3_Y + 84, "Host", 5.2)
        p.text(x + 6, RQ3_Y + 92, host.replace("\n", " "), 5.1, "bold", BODY)
    p.text(414, RQ3_Y + 114, "March exception: among 882 private rooms, the longest minimum stay was 7 nights.",
           5.5, "bold", BODY)


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


def draw_practical(p):
    p.rect(29, PRAC_Y, 742, PRAC_H, WHITE, LINE, radius=5)
    p.heading(42, PRAC_Y + 14, "05", "Practical Implications", 10)
    p.text(220, PRAC_Y + 14, "How host concentration and stay rules shape a shortlist", 6.2, ink=BODY)
    p.text(42, PRAC_Y + 30, "Listing counts and account counts answer different questions", 6.6)
    p.text(42, PRAC_Y + 40, "1 guest · private room · kitchen · ≤ HK$250 · 29 nights", 5.6, "bold", BODY)
    shapes, projection = district_geometry()
    project = projection(150, PRAC_Y + 48, 150, 52)
    for name, polygons in shapes.items():
        if name == "Wan Chai":
            shade = CLUSTER["long"]
        elif name == "Yau Tsim Mong":
            shade = CLUSTER["entire"]
        else:
            shade = "#E4E8EA"
        for rings in polygons:
            p.polygon(rings, project, shade)
    p.text(42, PRAC_Y + 108, "Most matching listings", 5.6, ink=CLUSTER["long"])
    p.text(42, PRAC_Y + 116, "Wan Chai", 6.2, "bold")
    p.text(150, PRAC_Y + 108, "Most distinct accounts", 5.6, ink=CLUSTER["entire"])
    p.text(150, PRAC_Y + 116, "Yau Tsim Mong", 6.2, "bold")
    p.text(42, PRAC_Y + 128, "Accounts are listing accounts, not verified owners.", 5.4, "bold", BODY)

    p.text(310, PRAC_Y + 30, "One night changes who is eligible", 6.6)
    p.text(310, PRAC_Y + 42, "Stay", 5.4, "demi", BODY)
    p.text(390, PRAC_Y + 42, "Listings", 5.4, "demi", BODY, "right")
    p.text(470, PRAC_Y + 42, "Accounts", 5.4, "demi", BODY, "right")
    for index, (month, stay, listings, accounts) in enumerate(REPORTED["threshold"]):
        y = PRAC_Y + 54 + index * 12
        if index in (0, 2):
            p.text(310, y, month, 5.6)
        p.text(352, y, stay, 5.6, "bold", BODY)
        p.text(390, y, f"{listings:,}", 5.8, "demi", align="right")
        bar = 8 + listings / 821 * 52
        p.rect(398, y - 3.2, bar, 3.4, CLUSTER["long"] if "29" in stay else "#E7D3C4", radius=.6)
        p.text(470, y, str(accounts), 5.8, "demi", align="right")
    p.para(310, PRAC_Y + 106, "June adds 745 listings and 8 accounts; September adds 720 listings and 8 accounts. "
           "Nine accounts supply the newly eligible listings in each snapshot. A similar jump appears at HK$200 and HK$300.",
           200, 5.4, 6.6, face="bold")
    p.text(310, PRAC_Y + 128, "These are filter results, not new market supply.", 5.4, "bold")

    p.text(530, PRAC_Y + 30, "Availability also depends on lead time", 6.4)
    p.text(530, PRAC_Y + 40, f"Oct 1–30 · 1 guest · {REPORTED['calendar_pool']:,} private rooms", 5.4, "bold", BODY)
    points = REPORTED["calendar"]
    x0, x1, y0, y1 = 548, 740, PRAC_Y + 96, PRAC_Y + 54
    p.line(x0, y0, x1, y0, "#E6EBED")
    for index, (days, rooms) in enumerate(points):
        x = x0 + index * (x1 - x0) / 2
        y = y0 - (rooms / 1600) * (y0 - y1)
        if index:
            prev_days, prev_rooms = points[index - 1]
            px = x0 + (index - 1) * (x1 - x0) / 2
            py = y0 - (prev_rooms / 1600) * (y0 - y1)
            p.line(px, py, x, y, CLUSTER["short"], 1.3)
        p.dot(x, y, 2.2, CLUSTER["short"], WHITE)
        p.text(x, y - 8, f"{rooms:,}", 6, "bold", CLUSTER["short"], "center")
        p.text(x, y0 + 8, f"{days} days", 5.3, "demi", BODY, "center")
    p.para(530, PRAC_Y + 116, "Calendar and minimum-stay filters only. Price and amenities are unrestricted. Counts approximate observed eligibility, not live bookings.",
           220, 5.3, 6.5, face="bold")


def draw_discussion(p):
    p.rect(29, DIS_Y, 742, DIS_H, WHITE, LINE, radius=5)
    p.heading(42, DIS_Y + 12, "06", "Discussion", 9.4)
    points = (
        (42, "Perspective", "Neither weight is always better; it depends on the question."),
        (292, "Explanation", "Stay rules drive the split; concentration lowers C2's weight."),
        (542, "Time", "The shift recurs in three snapshots. March is the exception."),
    )
    for x, title, text in points:
        p.text(x, DIS_Y + 26, title, 6.2)
        p.text(x, DIS_Y + 36, text, 5.6, "bold", BODY)
    p.text(42, DIS_Y + 50, "Depends on these snapshots, features, k = 3, and weights. Host IDs are accounts, not owners. The shortlist is an application, not a cluster test.",
           5.3, "bold", BODY)


def draw_footer(p):
    p.rect(0, FOOT_Y, WIDTH, HEIGHT - FOOT_Y, NAVY)
    p.text(36, FOOT_Y + 12, "07  ·  CONCLUSION", 6, "bold", ACCENT)
    p.text(36, FOOT_Y + 26, "Changing the weighting unit changes the clustering structure found in the same Airbnb listings.",
           7.6, "bold", WHITE)
    p.text(36, FOOT_Y + 38, "Listing weights separate private rooms by minimum stay. Host weights separate entire homes by capacity.",
           6, "demi", "#D5E3EA")
    p.text(36, FOOT_Y + 48, "This pattern appears in three of four snapshots. March 2026 is the exception.",
           6, "demi", "#D5E3EA")
    p.text(36, FOOT_Y + 60, "A search should respect minimum stay and report both matching listings and distinct host accounts.",
           6, "demi", "#D5E3EA")
    p.text(36, FOOT_Y + 72, "Inside Airbnb  ·  Hong Kong  ·  Dec 2025, Mar, Jun, and Sep 2026  ·  CC BY 4.0",
           5.4, "demi", "#C3D6DF")
    p.text(764, FOOT_Y + 72, "insideairbnb.com/get-the-data", 5.4, "demi", "#C3D6DF", "right")
    p.pdf.linkURL("https://insideairbnb.com/get-the-data",
                  (620 * mm, (HEIGHT - (FOOT_Y + 76)) * mm, 770 * mm, (HEIGHT - (FOOT_Y + 66)) * mm))


def render(pdf_path, preview):
    install_type()
    data = load(ROOT / "experiments/2026-11-21")
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    poster = Poster(pdf_path)
    draw_header(poster)
    draw_background(poster, data)
    draw_questions(poster)
    draw_methodology(poster, data)
    draw_rq1(poster, data)
    draw_rq2(poster, data)
    draw_rq3(poster, data)
    draw_practical(poster)
    draw_discussion(poster)
    draw_footer(poster)
    poster.pdf.showPage()
    poster.pdf.save()
    if preview:
        import pypdfium2 as pdfium
        document = pdfium.PdfDocument(str(pdf_path))
        if len(document) != 1:
            raise ValueError("The poster must be a single page.")
        page = document[0]
        width_mm = page.get_width() * 25.4 / 72
        height_mm = page.get_height() * 25.4 / 72
        if round(width_mm, 1) != 800 or round(height_mm, 1) != 1000:
            raise ValueError(f"Unexpected page size: {width_mm:.1f} x {height_mm:.1f} mm")
        page.render(scale=1800 / page.get_width()).to_pil().save(preview)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=ROOT / "poster/Group3_Poster_Final_Academic.pdf")
    parser.add_argument("--preview", type=Path, default=ROOT / "poster/Group3_Poster_Final_Academic.png")
    args = parser.parse_args()
    render(args.pdf, args.preview)
