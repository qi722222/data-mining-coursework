"""Render the AIAA3111 portrait poster at its exact print size."""

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
SUBTLE, LINE = "#496072", "#D9E1E3"
ACCENT = "#F3AA79"
CLUSTER = {1: "#276E82", 2: "#B55226", 3: "#675294"}
RIBBON = {1: "#87B7C0", 2: "#E7A67D", 3: "#B9ABD6"}
FONTS = {"regular": "Helvetica", "demi": "Helvetica-Bold", "bold": "Helvetica-Bold", "heavy": "Helvetica-Bold"}


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


class Poster:
    def __init__(self, output):
        self.pdf = canvas.Canvas(str(output), pagesize=(WIDTH * mm, HEIGHT * mm), pageCompression=1)
        self.pdf.setTitle("Beyond Room Type | Hong Kong Airbnb Market Segments")
        self.pdf.setAuthor("Jiaqi Li and Jialin Chen")
        self.pdf.setSubject("AIAA3111 Group 3 · 80 × 100 cm portrait poster")
        self.pdf.scale(mm, mm)

    def text(self, x, y, value, size, face="regular", ink=INK, align="left"):
        self.pdf.setFont(FONTS[face], size)
        self.pdf.setFillColor(tint(ink))
        draw = {"left": self.pdf.drawString, "center": self.pdf.drawCentredString, "right": self.pdf.drawRightString}
        draw[align](x, HEIGHT-y, str(value))

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
        step = leading or 1.38 * size
        for line in lines:
            self.text(x, y, line, size, face, ink)
            y += step
        return y

    def rect(self, x, y, width, height, fill, stroke=None, radius=0):
        self.pdf.setFillColor(tint(fill))
        if stroke:
            self.pdf.setStrokeColor(tint(stroke))
            self.pdf.setLineWidth(.48)
        if radius:
            self.pdf.roundRect(x, HEIGHT-y-height, width, height, radius, fill=1, stroke=bool(stroke))
        else:
            self.pdf.rect(x, HEIGHT-y-height, width, height, fill=1, stroke=bool(stroke))

    def line(self, x1, y1, x2, y2, color=LINE, weight=.55):
        self.pdf.setStrokeColor(tint(color))
        self.pdf.setLineWidth(weight)
        self.pdf.line(x1, HEIGHT-y1, x2, HEIGHT-y2)

    def dot(self, x, y, radius, fill, stroke=None):
        self.pdf.setFillColor(tint(fill))
        if stroke:
            self.pdf.setStrokeColor(tint(stroke))
            self.pdf.setLineWidth(.65)
        self.pdf.circle(x, HEIGHT-y, radius, stroke=bool(stroke), fill=1)

    def ribbon(self, x_left, x_right, a, b, height, fill):
        middle = (x_left + x_right)/2
        path = self.pdf.beginPath()
        path.moveTo(x_left, HEIGHT-a)
        path.curveTo(middle-20, HEIGHT-a, middle+20, HEIGHT-b, x_right, HEIGHT-b)
        path.lineTo(x_right, HEIGHT-b-height)
        path.curveTo(middle+20, HEIGHT-b-height, middle-20, HEIGHT-a-height, x_left, HEIGHT-a-height)
        path.close()
        self.pdf.setFillColor(tint(fill))
        self.pdf.drawPath(path, fill=1, stroke=0)

    def center_tag(self, x, y, label, color):
        measured = pdfmetrics.stringWidth(label, FONTS["bold"], 7.6)
        self.rect(x-measured/2-3.2, y-7.4, measured+6.4, 11, WHITE, radius=2.6)
        self.text(x, y, label, 7.6, "bold", color, "center")

    def polygon(self, rings, project, fill):
        path = self.pdf.beginPath()
        for ring in rings:
            x, y = project(*ring[0][:2])
            path.moveTo(x, HEIGHT-y)
            for point in ring[1:]:
                x, y = project(*point[:2])
                path.lineTo(x, HEIGHT-y)
            path.close()
        self.pdf.setFillColor(tint(fill))
        self.pdf.setStrokeColor(tint(WHITE))
        self.pdf.setLineWidth(.40)
        self.pdf.drawPath(path, fill=1, stroke=1, fillMode=0)


def draw_header(p, sample, checks, has_followup=False):
    p.rect(0, 0, WIDTH, HEIGHT, PAPER)
    p.rect(0, 0, WIDTH, 148, NAVY)
    p.rect(37, 25, 9, 2.8, ACCENT)
    p.text(51, 29.2, "AIAA3111  /  INTRODUCTION TO DATA MINING", 7.2, "demi", "#CFE1E8")
    p.text(762, 29.2, "GROUP 3", 7.9, "bold", ACCENT, "right")
    p.text(37, 81, "Beyond Room Type", 45, "heavy", WHITE)
    p.text(39, 109.5, "How host weighting changes Hong Kong Airbnb segments", 14.2, "demi", "#DBE8ED")
    p.text(40, 133, "Jiaqi Li   ·   Jialin Chen   /   HKUST (Guangzhou)", 7.5, "demi", "#AFC4CF")

    if has_followup:
        p.text(38, 174, "Where would you look for a 45-night stay?", 12.5, "bold")
        p.para(38, 191, "For visiting students and interns, count both listings and host accounts before "
               "shortlisting districts. We cluster listings by room type, capacity, bedrooms, minimum stay "
               "and eight amenities.", 355, 7.6, 10.4, ink=SUBTLE)
    else:
        p.text(38, 174, "Which room type gets split?", 12.5, "bold")
        p.para(38, 191, "We fit K-Means to room type, capacity, bedrooms, minimum stay and eight amenities. "
               "We balance the feature groups and use price and location to interpret the clusters.", 355, 7.6,
               10.4, ink=SUBTLE)
    metrics = [
        (423, f"{sample['listing_count']:,}", "Airbnb listings"),
        (537, f"{checks['host_accounts']:,}", "host accounts"),
        (649, f"{checks['top_ten_host_listings']/sample['listing_count']:.1%}", "of listings from the"),
    ]
    for x, value, label in metrics:
        p.line(x, 163, x, 209, "#CFD9DB")
        p.text(x+11, 183, value, 17.7, "heavy")
        p.text(x+11, 198, label, 7.1, "demi", SUBTLE)
    p.text(660, 208, "10 largest accounts", 7.1, "demi", SUBTLE)


def draw_flows(p, sample, checks, transitions, profiles, host_profiles, ablation=None):
    sx, ex = (215, 582)
    right_order = [1, 3, 2]
    row_sizes = {c: sum(transitions[c].values()) for c in (1, 2, 3)}
    col_sizes = {c: sum(row[c] for row in transitions.values()) for c in (1, 2, 3)}
    factor, gap = 136 / sample["listing_count"], 7.0
    p.rect(29, 224, 742, 291, WHITE, LINE, radius=5)
    p.text(45, 251, "Changing the weights changes the split", 17.5, "bold")
    p.text(46, 267, "Same listings, features and number of clusters  ·  K-Means with k = 3", 7.8, "demi", SUBTLE)
    p.text(46, 293, "Each listing counts equally", 9.4, "bold")
    p.text(46, 306, "Weight 1 per listing", 7.2, "regular", SUBTLE)
    p.text(600, 293, "Each account counts equally", 9.4, "bold")
    p.text(600, 306, "Weight 1 ÷ account listings", 7.2, "regular", SUBTLE)

    def positions(order, sizes):
        y, result = 320, {}
        for cluster in order:
            result[cluster] = y
            y += sizes[cluster] * factor + gap
        return result

    left = positions([1, 2, 3], row_sizes)
    right = positions(right_order, col_sizes)
    lused, rused = left.copy(), right.copy()
    widths = []
    for c in (1, 2, 3):
        for d in right_order:
            count = transitions[c][d]
            if count:
                thickness = count * factor
                y1, y2 = lused[c], rused[d]
                p.ribbon(sx, ex, y1, y2, thickness, RIBBON[c])
                if count >= 750:
                    widths.append(((y1+y2+thickness)/2, count, CLUSTER[c]))
                lused[c] += thickness
                rused[d] += thickness
    for y, count, hue in widths:
        p.center_tag((sx+ex)/2, y+2.5, f"{count:,}", hue)

    left_labels = {1: "Mostly entire homes", 2: "Mostly private rooms", 3: "Mostly private rooms"}
    right_labels = {1: "Mostly entire homes", 3: "Mostly entire homes", 2: "Mostly private rooms"}
    for c in (1, 2, 3):
        height = row_sizes[c] * factor
        y = left[c]
        p.rect(sx-7, y, 7, height, CLUSTER[c])
        mid = y + height/2
        nights = float(profiles[c]["Min. nights (median)"])
        p.text(46, mid-3, f"C{c}   {left_labels[c]}", 8.7, "bold", CLUSTER[c])
        p.text(46, mid+10.2, f"{nights:g}-night median minimum  ·  {row_sizes[c]:,}", 7.1, "demi", SUBTLE)
    for c in right_order:
        height = col_sizes[c] * factor
        y = right[c]
        p.rect(ex, y, 7, height, NAVY)
        mid = y + height/2
        guests = float(host_profiles[c]["Guests (median)"])
        detail = (f"{guests:g} guests (median)  ·  {col_sizes[c]:,}" if c != 2
                  else f"{col_sizes[c]:,} listings in one cluster")
        p.text(600, mid-3, right_labels[c], 8.7, "bold")
        p.text(600, mid+10.2, detail, 7.1, "demi", SUBTLE)

    p.line(45, 480, 754, 480)
    if ablation:
        private_counts = [int(count) for count in ablation["private_rooms_by_cluster"].split("/")]
        flow_note = (f"Dropping minimum stay puts {max(private_counts):,}/{sum(private_counts):,} private rooms "
                     "in one listing-weighted cluster.")
    else:
        flow_note = "With four account-weighted clusters, the private-room stay-length split reappears."
    p.text(46, 496, flow_note, 7.6, "bold")
    p.text(753, 496, f"Ribbons count listings   ·   Agreement ARI {checks['host_weight_ari']:.3f}",
           7.0, "demi", SUBTLE, "right")


def draw_profiles_and_prices(p, profiles, private):
    p.rect(29, 531, 369, 285, WHITE, LINE, radius=5)
    p.text(45, 557, "The split within private rooms", 14.4, "bold")
    p.text(45, 571, "Cluster profiles with each listing weighted equally", 7.2, "demi", SUBTLE)
    columns = [("Min. stay", "Min. nights (median)"), ("Kitchen", "Kitchen (%)"),
               ("Washer", "Washer (%)"), ("Self check-in", "Self check-in (%)")]
    centers = [205, 253, 301, 349]
    for x, (heading, _) in zip(centers, columns):
        p.text(x, 590, heading, 6.7, "demi", SUBTLE, "center")
    for i, c in enumerate((1, 2, 3)):
        y = 597+i*20
        hue, record = CLUSTER[c], profiles[c]
        p.dot(49, y+9, 3.1, hue)
        p.text(57, y+12, f"C{c}   " + ("Entire homes" if c == 1 else "Private rooms"), 7.7, "bold", hue)
        for x, (_, field) in zip(centers, columns):
            value = float(record[field])
            if field.endswith("(%)"):
                fill = blend("#FAF8F3", RIBBON[c], value/100)
                display = f"{value:.0f}%"
            else:
                fill = "#EDF1F2"
                display = f"{value:g} night" + ("" if value == 1 else "s")
            p.rect(x-22.7, y, 45.4, 17.5, fill, radius=2.5)
            p.text(x, y+11.7, display, 7.8, "bold", INK, "center")
    p.text(45, 668, "Minimum stay is a median. Amenities are shares of listings.", 6.5, "regular", SUBTLE)
    p.line(45, 679, 383, 679)
    p.text(45, 695, "Nightly prices within private rooms", 11.8, "bold")
    p.text(45, 707, "Observed HKD per night  ·  Median and middle 50%", 6.9, "demi", SUBTLE)

    x_min, x_max, max_price = 78, 294, 900
    project = lambda price: x_min + float(price) * (x_max-x_min) / max_price
    for tick in (0, 300, 600, 900):
        x = project(tick)
        p.line(x, 717, x, 771, "#E5E9EB")
        p.text(x, 784, tick, 6.5, "demi", SUBTLE, "center")
    for i, c in enumerate((2, 3)):
        values, y, hue = private[c], 733+i*29, CLUSTER[c]
        first, middle, last = [project(values[field]) for field in ("q25_hkd", "median_hkd", "q75_hkd")]
        p.text(47, y+2.5, f"C{c}", 8.2, "bold", hue)
        p.line(first, y, last, y, RIBBON[c], 4)
        p.dot(middle, y, 2.8, hue, WHITE)
        p.text(middle, y-7.4, f"{float(values['median_hkd']):.0f}", 8.6, "bold", hue, "center")
        p.text(382, y+2.5, f"{int(values['priced']):,} / {int(values['listings']):,}", 7.0, "demi", SUBTLE, "right")
    p.text(382, 721, "With price / total", 6.25, "demi", SUBTLE, "right")
    p.text(45, 803, "Each dot shows the median of listings with a recorded price.", 6.45, "regular", SUBTLE)


def district_map_geometry():
    geography = json.loads((ROOT / "data/hong-kong-2026-09-20-neighbourhoods.geojson").read_text())["features"]
    shapes = {}
    for feature in geography:
        item = feature["geometry"]
        shapes[feature["properties"]["neighbourhood"]] = (
            [item["coordinates"]] if item["type"] == "Polygon" else item["coordinates"]
        )
    points = [point for polygons in shapes.values() for rings in polygons for ring in rings for point in ring]
    lon_lo = min(pt[0] for pt in points)
    lon_hi = max(pt[0] for pt in points)
    lat_lo = min(pt[1] for pt in points)
    lat_hi = max(pt[1] for pt in points)
    ratio = math.cos(math.radians((lat_lo+lat_hi)/2))

    def projection(center_x, top, width, height):
        scale = min(width/((lon_hi-lon_lo)*ratio), height/(lat_hi-lat_lo))
        left = center_x - (lon_hi-lon_lo)*ratio*scale/2
        return lambda lon, lat: (left+(lon-lon_lo)*ratio*scale, top+(lat_hi-lat)*scale)

    return shapes, projection


MAP_LOW, MAP_HIGH, MAP_MASK = "#675294", "#AE5227", "#CCD7DF"


def map_color(diff):
    return blend("#F1EDE4", MAP_LOW if diff < 0 else MAP_HIGH, abs(diff)/35)


def draw_map(p, districts):
    p.rect(414, 531, 357, 285, WHITE, LINE, radius=5)
    p.text(430, 557, "Where is the 29-night group", 13.6, "bold")
    p.text(430, 573, "more common?", 13.6, "bold")
    p.para(430, 588, "C2 share relative to what each district's room-type mix would predict.", 324, 7.25, 9.4,
           "demi", SUBTLE)
    shapes, projection = district_map_geometry()
    project = projection(593, 604, 314, 149)

    for name, polygons in shapes.items():
        row = districts[name]
        shade = map_color(float(row["excess_pp"])) if int(row["district_n"]) >= 50 else MAP_MASK
        for rings in polygons:
            p.polygon(rings, project, shade)
    references = [
        ("Yau Tsim Mong", (114.165, 22.318), 696, 631),
        ("Wan Chai", (114.182, 22.279), 697, 716),
        ("Central & Western", (114.149, 22.280), 494, 730),
    ]
    for name, center, x, y in references:
        cx, cy = project(*center)
        info = districts[name]
        change = float(info["excess_pp"])
        hue = MAP_LOW if change < 0 else MAP_HIGH
        p.line(cx, cy, x, y+1, INK, .55)
        p.dot(cx, cy, 1.7, hue, WHITE)
        p.rect(x-42, y-7.6, 84, 19, WHITE, radius=2)
        p.text(x, y, name, 6.1, "bold", INK, "center")
        p.text(x, y+8, f"{change:+.1f} pp · n={int(info['district_n']):,}", 6.2, "demi", hue, "center")
    for i in range(64):
        p.rect(433+i*3.26, 766, 3.31, 6.8, map_color((i/63)*70-35))
    for x, value in ((433, "−35 pp"), (537, "0"), (641, "+35 pp")):
        p.text(x, 783, value, 6.2, "demi", SUBTLE, "center")
    p.rect(663, 766, 8, 6.8, MAP_MASK, radius=1.1)
    p.text(677, 772, "Fewer than 50 listings", 6.7, "demi", SUBTLE)
    p.para(430, 802, "Expected share combines citywide cluster rates within each room type with the district's "
           "room-type mix. pp = percentage points.",
           326, 6.35, 8.1, ink=SUBTLE)


def draw_paired_map(p, districts, min_listings):
    p.rect(414, 531, 357, 285, WHITE, LINE, radius=5)
    p.text(430, 555, "Does C2 still stand out?", 13.8, "bold")
    p.para(430, 571, "Same C2 listings in both maps. Color shows the gap from the share expected "
           "for each district's room-type mix.", 324, 7.1, 9.4, "demi", SUBTLE)
    shapes, projection = district_map_geometry()
    for mode, center, heading in (("listing", 508, "Listings count equally"),
                                  ("account", 677, "Accounts count equally")):
        p.text(center, 601, heading, 7.5, "bold", INK, "center")
        project = projection(center, 607, 152, 99)
        for name, polygons in shapes.items():
            row = districts[name]
            shade = (map_color(float(row[f"{mode}_excess_pp"]))
                     if int(row["listing_n"]) >= min_listings else MAP_MASK)
            for rings in polygons:
                p.polygon(rings, project, shade)

    for i in range(64):
        p.rect(434+i*3.48, 710, 3.54, 6.2, map_color((i/63)*70-35))
    for x, label in ((434, "−35 pp"), (545, "0"), (657, "+35 pp")):
        p.text(x, 724, label, 6.2, "demi", SUBTLE, "center")
    p.rect(671, 710, 7.4, 6.2, MAP_MASK, radius=1)
    p.text(683, 716, f"Under {min_listings} listings", 6.2, "demi", SUBTLE)

    p.line(430, 734, 755, 734)
    p.text(430, 746, "District", 7.0, "bold")
    p.text(589, 746, "Listings", 7.0, "bold", INK, "right")
    p.text(654, 746, "Accounts", 7.0, "bold", INK, "right")
    p.text(754, 746, "Account 95% CI", 7.0, "bold", INK, "right")
    for y, district in ((761, "Wan Chai"), (777, "Yau Tsim Mong")):
        row = districts[district]
        p.text(430, y, district, 7.5, "demi")
        p.text(589, y, f"{float(row['listing_excess_pp']):+.1f}", 7.5, "demi", INK, "right")
        p.text(654, y, f"{float(row['account_excess_pp']):+.1f}", 7.5, "bold", INK, "right")
        low, high = float(row["account_ci_low_pp"]), float(row["account_ci_high_pp"])
        p.text(754, y, f"[{low:+.1f}, {high:+.1f}]", 7.2, "demi", SUBTLE, "right")
    p.para(430, 797, "Gaps are in percentage points. Intervals resample host accounts with C2 membership fixed.",
           325, 6.45, 8.1, ink=SUBTLE)


def draw_validation(p, report, sample, checks, example=None):
    p.text(36, 842, "How we checked the result", 14.2, "bold")
    p.line(36, 851, 764, 851, "#CBD4D8")
    model = report["model"]
    fit_check = checks["host_resample_ari_q25_median_q75"][1]
    sections = [
        (36, "Model choice", f"Silhouette peaked at k = 2 ({model[2]:.3f}). "
         f"We display k = 3 ({model[3]:.3f}) to examine the private-room split. "
         "At k = 3, Ward and K-Means had an adjusted Rand index (ARI) of "
         f"{report['ward']:.3f}."),
        (284, "Stability and transfer", f"Resampling host accounts gave a median ARI of {fit_check:.3f}. "
         f"The June fit and September refit reached ARI {report['cross']:.3f} on September listings. "
         f"The snapshots shared {checks['cross_quarter']['shared_listing_ids']:,} listings."),
        (532, "Scope of the evidence", f"{sample['priced_count']:,} of {sample['listing_count']:,} listings had a price. "
         "Values are advertised nightly rates. Host IDs identify accounts, and district differences describe the snapshot."),
    ]
    if example:
        sections[1] = (284, "Stability and sensitivity",
                       f"Resampling host accounts gave a median ARI of {fit_check:.3f}. "
                       "With account weighting and minimum stay included, the two private-room "
                       f"groups reappeared at k = 4. June-to-September ARI was {report['cross']:.3f}.")
        wan_chai, yau_tsim_mong = (example[name] for name in ("Wan Chai", "Yau Tsim Mong"))
        sections[2] = (532, "Try a 45-night shortlist",
                       "One guest, private room, kitchen, up to HKD 250/night. "
                       f"Wan Chai had {wan_chai['matching_listings']} listings from "
                       f"{wan_chai['distinct_accounts']} accounts. Yau Tsim Mong had "
                       f"{yau_tsim_mong['matching_listings']} from {yau_tsim_mong['distinct_accounts']}. "
                       "Counts are from the September snapshot.")
    for x, title, body in sections:
        if x > 36:
            p.line(x-12, 862, x-12, 920, "#CFD9DB")
        p.text(x, 868, title, 9.2, "bold")
        p.para(x, 883, body, 224, 7.2, 9.4, ink=SUBTLE)

    p.rect(0, 942, WIDTH, 58, NAVY)
    conclusion = ("Use stay rules to filter, then check how many accounts are behind the listings."
                  if example else "Weighting by account changes which market segments are most visible.")
    p.text(37, 966, conclusion, 10.0, "bold", WHITE)
    p.text(37, 985, "Data & boundaries  ·  Inside Airbnb, Hong Kong  ·  June and September 2026  ·  CC BY 4.0", 6.8,
           "demi", "#C3D6DF")
    p.text(763, 985, "insideairbnb.com/get-the-data", 6.8, "demi", "#C3D6DF", "right")
    p.pdf.linkURL("https://insideairbnb.com/get-the-data/", (641, HEIGHT-989, 765, HEIGHT-978), relative=1)


def render(output, preview, followups=None):
    sample = json.loads((RESULTS / "run.json").read_text())
    checks = json.loads((CHECKS / "checks.json").read_text())
    all_profiles = read_csv(RESULTS / "cluster_profiles_all_k.csv")
    profiles = {int(row["cluster"]): row for row in all_profiles if int(row["k"]) == 3}
    host_profiles = {int(row["cluster"]): row for row in read_csv(CHECKS / "host_weighted_profiles.csv")}
    transitions = {int(row["cluster"]): {c: int(row[str(c)]) for c in (1, 2, 3)}
                   for row in read_csv(CHECKS / "host_weight_transitions.csv")}
    private = {int(row["cluster"]): row for row in read_csv(CHECKS / "prices_within_room_type.csv")
               if row["room_type"] == "Private room"}
    districts = {row["district"]: row for row in read_csv(CHECKS / "district_room_adjusted.csv")
                 if row["cluster"] == "2"}
    scores = {int(row["k"]): float(row["silhouette_fixed_sample"]) for row in read_csv(RESULTS / "k_sweep.csv")}
    cross = next(row for row in read_csv(CHECKS / "cross_quarter.csv") if row["subset"] == "all September")
    ward = next(row for row in read_csv(CHECKS / "alternative_models.csv")
                if row["method"] == "Ward" and row["k"] == "3")
    report = {"model": scores, "cross": float(cross["ari_frozen_vs_september_refit"]),
              "ward": float(ward["ari_vs_reference_k3"])}
    ablation = None
    example = None
    if followups:
        followup_run = json.loads((followups / "followup_run.json").read_text())
        if followup_run["listing_sha256"] != sample["source_sha256"]:
            raise ValueError("Poster and follow-up tables must use the same snapshot.")
        ablation = next(row for row in read_csv(followups / "stay_ablation_summary.csv") if row["k"] == "3"
                        and row["fit_weighting"] == "listing" and row["features"] == "without_minimum_nights")
        districts = {row["district"]: row for row in read_csv(followups / "fixed_c2_district_weights.csv")}
        example = {row["district"]: row for row in read_csv(followups / "shortlist_example.csv")}

    install_type()
    output.parent.mkdir(parents=True, exist_ok=True)
    p = Poster(output)
    draw_header(p, sample, checks, has_followup=bool(followups))
    draw_flows(p, sample, checks, transitions, profiles, host_profiles, ablation)
    draw_profiles_and_prices(p, profiles, private)
    if followups:
        draw_paired_map(p, districts, followup_run["map_min_listings"])
    else:
        draw_map(p, districts)
    draw_validation(p, report, sample, checks, example=example)
    p.pdf.showPage()
    p.pdf.save()
    if preview:
        import pypdfium2 as pdfium
        doc = pdfium.PdfDocument(str(output))
        page = doc[0]
        page.render(scale=1800/page.get_width()).to_pil().save(preview)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdf", type=Path, default=ROOT / "poster/Group3_Poster_Draft.pdf")
    parser.add_argument("--preview", type=Path, default=ROOT / "poster/Group3_Poster_Preview.png")
    parser.add_argument("--followups", type=Path, help="Use the stay ablation and paired C2 maps from this output folder.")
    args = parser.parse_args()
    render(args.pdf, args.preview, args.followups)
