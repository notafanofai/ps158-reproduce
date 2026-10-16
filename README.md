# SCF family net worth by education

This project makes two black-and-white figures comparing family net worth for
respondents with a college degree or higher and respondents with a high-school
education or less, using the respondent's own education for every wave from
1989 through 2025. Values are in 2025 dollars.

- `wealth_gap_by_education.svg`: median family net worth (Figure 1).
- `wealth_gap_by_education_mean.svg`: mean family net worth (Figure 2).

## Data

`get_data.py` downloads public-use Survey of Consumer Finances (SCF) extracts
from the Federal Reserve Board. It uses the harmonized respondent education
variable (`EDCL`), SCF survey weights, and implicates to estimate the series.
The source data are cached in `data/raw/`; processed estimates are written to
`data/processed/education_wealth.csv`.

## Rerun

Install Python with `pandas` and its Stata reader (`pyreadstat`), then run from
the project directory:

```sh
python get_data.py
python plot.py
```

`get_data.py` downloads any missing SCF files and rebuilds the CSV.
`plot.py` regenerates both SVG figures.
