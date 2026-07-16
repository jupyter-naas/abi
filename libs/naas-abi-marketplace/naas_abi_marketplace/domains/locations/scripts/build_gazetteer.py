"""Build a worldwide gazetteer (city, region, state, country, postal_code).

Source: GeoNames (https://www.geonames.org), public dataset released under
CC BY 4.0 -- attribution to GeoNames is required for any redistribution.

The GeoNames postal-code export already carries city/region/state/country in
one row per postal code, so no join against the multi-GB `allCountries.txt`
place dump is needed. Coverage is ~83 countries that publish postal codes;
countries without postal codes (e.g. most of Africa, parts of the Middle
East) will be absent -- see README.md in this directory.

Usage:
    python build_gazetteer.py --countries FR,US,DE --output gazetteer.csv
    python build_gazetteer.py --output gazetteer.parquet --format parquet
    python build_gazetteer.py --output gazetteer.db --format sqlite
"""

import argparse
import sqlite3
import zipfile
from pathlib import Path

import pandas as pd
import requests

GEONAMES_BASE = "https://download.geonames.org/export"

POSTAL_CODE_COLUMNS = [
    "country_code",
    "postal_code",
    "place_name",
    "admin_name1",
    "admin_code1",
    "admin_name2",
    "admin_code2",
    "admin_name3",
    "admin_code3",
    "latitude",
    "longitude",
    "accuracy",
]

COUNTRY_INFO_COLUMNS = [
    "iso",
    "iso3",
    "iso_numeric",
    "fips",
    "country",
    "capital",
    "area",
    "population",
    "continent",
    "tld",
    "currency_code",
    "currency_name",
    "phone",
    "postal_code_format",
    "postal_code_regex",
    "languages",
    "geonameid",
    "neighbours",
    "equivalent_fips_code",
]

GAZETTEER_COLUMNS = [
    "city",
    "region",
    "state",
    "country",
    "country_code",
    "postal_code",
    "latitude",
    "longitude",
]


def download(url: str, dest: Path) -> Path:
    if dest.exists():
        return dest
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading {url} -> {dest}")
    with requests.get(url, stream=True, timeout=120) as response:
        response.raise_for_status()
        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=1 << 20):
                f.write(chunk)
    return dest


def load_country_info(cache_dir: Path) -> pd.DataFrame:
    path = download(f"{GEONAMES_BASE}/dump/countryInfo.txt", cache_dir / "countryInfo.txt")
    df = pd.read_csv(
        path,
        sep="\t",
        comment="#",
        names=COUNTRY_INFO_COLUMNS,
        header=None,
        dtype=str,
        keep_default_na=False,
    )
    return df[["iso", "country"]].rename(columns={"iso": "country_code", "country": "country"})


def load_postal_codes(cache_dir: Path, country_code: str | None) -> pd.DataFrame:
    """country_code=None downloads the full world dump (allCountries.zip, ~250MB)."""
    filename = f"{country_code}.zip" if country_code else "allCountries.zip"
    zip_path = download(f"{GEONAMES_BASE}/zip/{filename}", cache_dir / filename)
    txt_name = f"{country_code}.txt" if country_code else "allCountries.txt"
    with zipfile.ZipFile(zip_path) as zf, zf.open(txt_name) as f:
        return pd.read_csv(
            f,
            sep="\t",
            names=POSTAL_CODE_COLUMNS,
            header=None,
            dtype=str,
            keep_default_na=False,
        )


def build_gazetteer(countries: list[str] | None, cache_dir: Path) -> pd.DataFrame:
    country_info = load_country_info(cache_dir)

    if countries:
        postal = pd.concat(
            [load_postal_codes(cache_dir, code) for code in countries],
            ignore_index=True,
        )
    else:
        postal = load_postal_codes(cache_dir, None)

    gaz = postal.merge(country_info, on="country_code", how="left")
    gaz = gaz.rename(
        columns={
            "place_name": "city",
            "admin_name1": "state",
            "admin_name2": "region",
        }
    )
    gaz = gaz[GAZETTEER_COLUMNS].drop_duplicates().reset_index(drop=True)
    return gaz


def save(gaz: pd.DataFrame, output: Path, fmt: str) -> None:
    if fmt == "csv":
        gaz.to_csv(output, index=False)
    elif fmt == "parquet":
        gaz.to_parquet(output, index=False)
    elif fmt == "sqlite":
        with sqlite3.connect(output) as conn:
            gaz.to_sql("gazetteer", conn, if_exists="replace", index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--countries",
        help="Comma-separated ISO-3166 country codes (e.g. FR,US,DE). "
        "Omit to download the full world postal-code dump (~250MB).",
    )
    parser.add_argument("--output", default="gazetteer.csv", help="Output file path.")
    parser.add_argument("--format", choices=["csv", "parquet", "sqlite"], default="csv")
    parser.add_argument(
        "--cache-dir",
        default=str(Path(__file__).parent),
        help="Directory used to cache downloaded GeoNames dumps "
        "(defaults to this script's directory).",
    )
    args = parser.parse_args()

    countries = (
        [code.strip().upper() for code in args.countries.split(",")]
        if args.countries
        else None
    )

    gaz = build_gazetteer(countries, Path(args.cache_dir))
    print(f"Built gazetteer: {len(gaz):,} rows, {gaz['country_code'].nunique()} countries.")

    output = Path(args.output)
    save(gaz, output, args.format)
    print(f"Saved to {output}")


if __name__ == "__main__":
    main()
