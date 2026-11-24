# Data

The included season CSV comes from [Vaastav Anand's Fantasy-Premier-League dataset](https://github.com/vaastav/Fantasy-Premier-League/tree/master/data), distributed under the upstream [MIT licence](LICENSE). Credit belongs to the dataset's author and contributors.

The file is included unchanged as `raw/fpl_25_26_all gw_merged.csv`. Its bytes match the pinned upstream download recorded in [results/data_provenance.json](../results/data_provenance.json), produced by [verification/check_source.py](../verification/check_source.py). The original source's season label is retained; this project does not independently certify the supplier's football records.

The app checks the SHA-256 fingerprint in [app/config.json](../app/config.json) before loading. No download or preparation step is needed to run the project. To recheck the external source, run `python verification/check_source.py`; this makes a network request and writes a local report, without modifying the CSV.

Each row is a player-fixture observation. Distinct fixtures in a gameweek must be aggregated. Only fully identical copies are removed; conflicting player-fixture records are rejected. Prices use the latest recorded fixture at or before the selected interval end, rather than a later price.

Full field definitions, units, metric formulas and validation coverage live in [fpl_data_taxonomy.json](../fpl_data_taxonomy.json). The model receives calculated tool observations, not the entire CSV.
