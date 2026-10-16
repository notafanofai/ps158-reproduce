"""Download public SCF extracts and estimate wealth by education group.

Groups use the SCF reference person's own education in every wave, 1989–2025.

Run: python get_data.py
Requires pandas (which uses the installed Stata reader).
"""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from zipfile import BadZipFile, ZipFile

import pandas as pd


ROOT = Path(__file__).resolve().parent
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "processed"
OUT_CSV = OUT_DIR / "education_wealth.csv"
WAVES = (1989, 1992, 1995, 1998, 2001, 2004, 2007, 2010, 2013, 2016, 2019, 2022, 2025)

COLLEGE = "College degree or higher"
HS_OR_LESS = "High school or less"

def fetch(url: str, destination: Path) -> None:
    if destination.exists() and destination.stat().st_size:
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "Mozilla/5.0 (SCF public data analysis)"})
    with urlopen(request, timeout=180) as response:
        destination.write_bytes(response.read())


def archive_for(year: int, role: str) -> Path:
    """Fetch an official full-data or standardized-extract archive."""
    short = f"{year % 100:02d}"
    if role == "extract":
        name = f"scfp{year}s.zip"
    elif year <= 1998:
        name = f"scf{short}s.zip"
    else:
        name = f"scf{year}s.zip"
    names = [name]
    roots = (
        "https://www.federalreserve.gov/econres/files/",
        "https://www.federalreserve.gov/econresdata/scf/files/",
    )
    last_error: Exception | None = None
    for name in names:
        path = RAW_DIR / name
        if path.exists() and path.stat().st_size:
            return path
        for root in roots:
            try:
                fetch(root + name, path)
                return path
            except (HTTPError, URLError, TimeoutError) as exc:
                last_error = exc
                if path.exists():
                    path.unlink()
    raise RuntimeError(f"Could not download {role} archive for {year}: {last_error}")


def read_stata(path: Path, columns: list[str] | None = None) -> pd.DataFrame:
    """Read the largest Stata file in a Federal Reserve ZIP."""
    try:
        with ZipFile(path) as archive:
            members = [n for n in archive.namelist() if n.lower().endswith(".dta")]
            if not members:
                raise RuntimeError(f"No .dta file in {path}")
            member = max(members, key=lambda n: archive.getinfo(n).file_size)
            with archive.open(member) as stream:
                selected = [name.lower() for name in columns] if columns else None
                frame = pd.read_stata(
                    BytesIO(stream.read()), columns=selected, convert_categoricals=False
                )
    except BadZipFile as exc:
        raise RuntimeError(f"Invalid SCF archive: {path}") from exc
    frame.columns = [str(name).upper() for name in frame.columns]
    return frame


def normalize_ids(frame: pd.DataFrame, year: int) -> pd.DataFrame:
    frame = frame.copy()
    if "Y1" not in frame and "X1" in frame:
        frame["Y1"] = frame["X1"]
    if "YY1" not in frame and "XX1" in frame:
        frame["YY1"] = frame["XX1"]
    return frame


def weighted_median(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & (weights > 0)
    v = values.loc[valid].astype(float)
    w = weights.loc[valid].astype(float)
    if v.empty:
        return float("nan")
    order = v.argsort(kind="mergesort")
    v, w = v.iloc[order], w.iloc[order]
    position = int(w.cumsum().searchsorted(w.sum() / 2, side="left"))
    return float(v.iloc[position])


def weighted_mean(values: pd.Series, weights: pd.Series) -> float:
    valid = values.notna() & weights.notna() & (weights > 0)
    v = values.loc[valid].astype(float)
    w = weights.loc[valid].astype(float)
    if v.empty:
        return float("nan")
    return float((v * w).sum() / w.sum())


def category_from_own_education(edcl: pd.Series) -> pd.Series:
    # Federal Reserve EDCL harmonization: 1=no HS/GED, 2=HS/GED,
    # 3=some college/associate degree, 4=bachelor's degree or higher.
    code = pd.to_numeric(edcl, errors="coerce")
    out = pd.Series(pd.NA, index=edcl.index, dtype="object")
    out.loc[code.isin([1, 2])] = HS_OR_LESS
    out.loc[code.eq(4)] = COLLEGE
    return out


def prepare_wave(year: int) -> pd.DataFrame:
    # The summary extract provides inflation-adjusted net worth, final weights,
    # implicate IDs, and harmonized reference-person education (EDCL).
    ids = ["x1", "xx1"] if year == 1989 else ["y1", "yy1"]
    extract = read_stata(
        archive_for(year, "extract"), ids + ["wgt", "networth", "edcl"]
    )
    extract = normalize_ids(extract, year)
    required = {"Y1", "YY1", "WGT", "NETWORTH", "EDCL"}
    missing = required - set(extract.columns)
    if missing:
        raise RuntimeError(f"{year} summary extract lacks {sorted(missing)}")
    columns = ["Y1", "YY1", "WGT", "NETWORTH", "EDCL"]
    data = extract[columns].copy()
    data["education_group"] = category_from_own_education(data["EDCL"])
    data["education_measure"] = "Respondent's own education"

    data = data.dropna(subset=["education_group", "NETWORTH", "WGT", "YY1"])
    for column in ("WGT", "NETWORTH", "Y1", "YY1"):
        data[column] = pd.to_numeric(data[column], errors="coerce")
    data = data.loc[data["WGT"].gt(0)].copy()
    data["year"] = year
    # The Federal Reserve's public summary extracts express dollar variables
    # in 2025 dollars. Cast IDs to int64 before recovering implicates: early
    # SCF IDs can overflow their narrow Stata integer dtype during subtraction.
    data["implicate"] = (
        data["Y1"].astype("int64") - 10 * data["YY1"].astype("int64")
    )
    return data


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    samples = pd.concat([prepare_wave(year) for year in WAVES], ignore_index=True)
    rows: list[dict[str, object]] = []
    for (year, group, measure), subset in samples.groupby(
        ["year", "education_group", "education_measure"], dropna=True
    ):
        estimates = [
            weighted_median(chunk["NETWORTH"], chunk["WGT"])
            for _, chunk in subset.groupby("implicate")
        ]
        mean_estimates = [
            weighted_mean(chunk["NETWORTH"], chunk["WGT"])
            for _, chunk in subset.groupby("implicate")
        ]
        rows.append({
            "year": int(year),
            "education_group": group,
            "education_measure": measure,
            "median_net_worth_2025_dollars": sum(estimates) / len(estimates),
            "mean_net_worth_2025_dollars": sum(mean_estimates) / len(mean_estimates),
            "families": int(subset["YY1"].nunique()),
        })
    result = pd.DataFrame(rows).sort_values(["year", "education_group"])
    result["median_net_worth_2025_dollars"] = result[
        "median_net_worth_2025_dollars"
    ].round(2)
    result["mean_net_worth_2025_dollars"] = result[
        "mean_net_worth_2025_dollars"
    ].round(2)
    result.to_csv(OUT_CSV, index=False)
    print(f"Wrote {OUT_CSV}")
    print(result.to_string(index=False))
    print("Education groups use the respondent/reference person's own education in all waves, 1989–2025.")
    print("Net worth is reported in 2025 dollars, as in the Federal Reserve summary extracts.")


if __name__ == "__main__":
    main()
