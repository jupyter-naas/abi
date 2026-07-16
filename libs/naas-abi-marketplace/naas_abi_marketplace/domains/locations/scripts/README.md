# Locations scripts

## build_gazetteer.py

Builds a worldwide gazetteer (`city`, `region`, `state`, `country`, `postal_code`,
`latitude`, `longitude`) from the [GeoNames](https://www.geonames.org) open dataset.

GeoNames data is released under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) --
any redistribution of the built gazetteer must credit GeoNames.

### Usage

```bash
# A few countries (fast, good for dev/testing)
uv run python build_gazetteer.py --countries FR,US,DE --output gazetteer.csv

# Full world dump (~250MB download, ~2-3M rows)
uv run python build_gazetteer.py --output gazetteer.parquet --format parquet

# SQLite output
uv run python build_gazetteer.py --output gazetteer.db --format sqlite
```

Downloaded GeoNames dumps (`allCountries.zip`, `countryInfo.txt`, ...) are cached
directly in this `scripts/` directory by default (override with `--cache-dir`) so
re-running the script doesn't re-download.

### Coverage caveat

GeoNames only publishes postal codes for ~83 countries. Countries without postal
codes (most of Africa, parts of the Middle East, etc.) will not appear in the
output. If full city/country coverage without postal codes is needed, merge in
`allCountries.txt` from `https://download.geonames.org/export/dump/` (feature
class `P` = populated place) instead -- that dump has no postal_code column but
covers every country.
