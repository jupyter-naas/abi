# Locations Integrations

One integration per data source, each following the standard `Integration`/`IntegrationConfiguration` pattern and exposing `as_tools()` for use by `LocationsAgent`.

## GeoNamesIntegration

Wraps the raw [GeoNames](https://www.geonames.org) dumps (postal codes + country info), released under CC BY 4.0. Downloads are cached locally (`cache_dir` config, defaults to `datastore/domains/locations/geonames`).

- `get_country_info()` -- ISO country code to country name mapping.
- `get_postal_codes(country_code=None)` -- city/region/state/postal_code records for a country, or the full world dump (~250MB, cached after first call).
- `search_postal_code(country_code, postal_code)` -- look up a specific postal code.

Broadest coverage, but limited to the ~83 countries GeoNames publishes postal codes for.

## PgeocodeIntegration

Wraps [pgeocode](https://github.com/symerio/pgeocode), an offline postal-code geocoder. Data is downloaded once per country and cached by pgeocode itself.

- `query_postal_code(country_code, postal_code)` -- accepts a single postal code or a list; returns city/region/state/lat/lon.

Faster than GeoNames for repeated single-country lookups; same ~83-country coverage.

## GeonamescacheIntegration

Wraps [geonamescache](https://github.com/yaph/geonamescache), a bundled offline snapshot of GeoNames countries, US states/counties, and cities. No network access or download required.

- `get_countries()`, `get_cities(min_population=None)`, `search_cities(name)`, `get_us_states()`, `get_us_counties()`.

No postal codes, but covers every country for coarse city/country lookups and bulk city listing by population.

## CLDRIntegration

Wraps the Unicode [CLDR](https://cldr.unicode.org) (Common Locale Data Repository) via the [babel](https://babel.pocoo.org) package, bundled offline locale data, no network access required.

- `get_territory_name(territory_code, locale=None)` -- localized name of a country/territory code (e.g. `"FR"` -> `"France"` in English, `"フランス"` in Japanese).
- `get_territory_names(territory_code, locales=None)` -- the same territory's name across multiple locales at once (defaults to a curated set of major world languages).
- `get_territories(locale=None)` -- every territory code and its localized name for one locale.
- `get_language_name(language_code, locale=None)` -- localized name of a language code.

Complements the other three (which are English-only) with multilingual country/region names, useful for matching user input regardless of language.

## Tests

Each integration has a sibling `*_test.py` that exercises the real library/source (no mocking), matching the codebase convention.
