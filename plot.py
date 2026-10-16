"""Create a first SVG figure from data/processed/education_wealth.csv."""

from __future__ import annotations

import csv
import math
from html import escape
from pathlib import Path


ROOT = Path(__file__).resolve().parent
DATA = ROOT / "data" / "processed" / "education_wealth.csv"
COLLEGE = "College degree or higher"
HS_OR_LESS = "High school or less"
STYLES = {
    COLLEGE: {"dash": "", "marker": "circle", "fill": "#000000"},
    HS_OR_LESS: {"dash": "stroke-dasharray=\"8,5\"", "marker": "square", "fill": "#ffffff"},
}


def render_figure(metric: str, statistic: str, filename: str) -> None:
    if not DATA.exists():
        raise SystemExit("Data not found. Run `python get_data.py` first.")
    with DATA.open(newline="", encoding="utf-8") as source:
        rows = list(csv.DictReader(source))
    values = {
        (int(row["year"]), row["education_group"]): float(row[metric])
        for row in rows
    }
    years = sorted({year for year, _ in values})
    if not years:
        raise SystemExit(f"No observations found in {DATA}")

    width, height = 1320, 790
    left, right, top, bottom = 105, 55, 60, 480
    x_min, x_max = min(years), max(years)
    max_value = max(0.0, max(values.values()))
    y_max = max(100_000, math.ceil(max_value / 100_000) * 100_000)

    def x_pos(year: int) -> float:
        return left + (year - x_min) / (x_max - x_min) * (width - left - right)

    def y_pos(value: float) -> float:
        return bottom - value / y_max * (bottom - top)

    pieces = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#ffffff"/>',
        '<style>text{font-family:Georgia,"Times New Roman",serif;fill:#000}.muted{fill:#333}.grid{stroke:#dddddd;stroke-width:.8}.axis{stroke:#000;stroke-width:1}</style>',
    ]

    step = max(50_000, math.ceil(y_max / 6 / 50_000) * 50_000)
    for tick in range(0, int(y_max) + step, step):
        y = y_pos(tick)
        pieces.append(f'<line x1="{left}" y1="{y:.1f}" x2="{width-right}" y2="{y:.1f}" class="grid"/>')
        pieces.append(f'<text x="{left-14}" y="{y+5:.1f}" text-anchor="end" class="muted" font-size="13">${tick//1000:,}k</text>')
    pieces.append(f'<line x1="{left}" y1="{top}" x2="{left}" y2="{bottom}" class="axis"/>')
    pieces.append(f'<line x1="{left}" y1="{bottom}" x2="{width-right}" y2="{bottom}" class="axis"/>')
    pieces.append(f'<text x="28" y="{(top+bottom)/2:.1f}" text-anchor="middle" font-size="14" transform="rotate(-90 28 {(top+bottom)/2:.1f})">{escape(statistic)} family net worth (2025 dollars)</text>')

    for year in years:
        x = x_pos(year)
        pieces.append(f'<line x1="{x:.1f}" y1="{bottom}" x2="{x:.1f}" y2="{bottom+6}" class="axis"/>')
        pieces.append(f'<text x="{x:.1f}" y="{bottom+24}" text-anchor="middle" class="muted" font-size="12">{year}</text>')

    for group in (COLLEGE, HS_OR_LESS):
        coordinates = [(x_pos(year), y_pos(values[(year, group)])) for year in years if (year, group) in values]
        points = " ".join(f"{x:.1f},{y:.1f}" for x, y in coordinates)
        style = STYLES[group]
        dash = f' {style["dash"]}' if style["dash"] else ""
        pieces.append(f'<polyline points="{points}" fill="none" stroke="#000" stroke-width="2"{dash} stroke-linejoin="round"/>')
        for (year, _), (x, y) in zip([(year, group) for year in years if (year, group) in values], coordinates):
            if style["marker"] == "circle":
                pieces.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="4" fill="{style["fill"]}" stroke="#000" stroke-width="1"/>')
            else:
                pieces.append(f'<rect x="{x-4:.1f}" y="{y-4:.1f}" width="8" height="8" fill="{style["fill"]}" stroke="#000" stroke-width="1"/>')

    legend_y = 30
    for index, group in enumerate((COLLEGE, HS_OR_LESS)):
        x = left + index * 340
        style = STYLES[group]
        dash = f' {style["dash"]}' if style["dash"] else ""
        pieces.append(f'<line x1="{x}" y1="{legend_y}" x2="{x+30}" y2="{legend_y}" stroke="#000" stroke-width="2"{dash}/>')
        if style["marker"] == "circle":
            pieces.append(f'<circle cx="{x+15}" cy="{legend_y}" r="4" fill="#000" stroke="#000"/>')
        else:
            pieces.append(f'<rect x="{x+11}" y="{legend_y-4}" width="8" height="8" fill="#fff" stroke="#000"/>')
        pieces.append(f'<text x="{x+40}" y="{legend_y+5}" font-size="13">{escape(group)}</text>')

    pieces.extend([
        f'<text x="105" y="555" font-size="15" font-weight="700">Figure {1 if statistic == "Median" else 2}. {statistic} family net worth by education group, 1989–2025</text>',
        '<text x="105" y="579" font-size="13">Note: Values are adjusted to 2025 dollars. Groups use respondent/reference person’s own education in all waves.</text>',
        '<text x="105" y="599" font-size="13">Some college/associate degree and unknown education are excluded.</text>',
        '<text x="105" y="619" font-size="13">Medians are calculated within each of the five implicates using survey weights, then averaged.</text>',
        '<text x="105" y="653" font-size="13">Source: Federal Reserve Board, Survey of Consumer Finances, 1989–2025; authors’ calculations.</text>',
        '</svg>',
    ])
    figure_path = ROOT / filename
    figure_path.write_text("\n".join(pieces), encoding="utf-8")
    print(f"Wrote {figure_path}")


def main() -> None:
    render_figure("median_net_worth_2025_dollars", "Median", "wealth_gap_by_education.svg")
    render_figure("mean_net_worth_2025_dollars", "Mean", "wealth_gap_by_education_mean.svg")


if __name__ == "__main__":
    main()
