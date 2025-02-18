# theorem-scraper

Some scripts for scraping theorem entries from the nLab, Wikipedia, and Wikidata.

## nLab

Searches for nLab pages with titles containing certain keywords, satisfying certain criteria.
See `nlab_output.txt` for the full list.

## Wikidata

Searches for Wikidata entries listed as instances of theorems, that have an associated Wikipedia page, and that is not in Wikipedia's list of theorems.
See `wikidata_output.txt` for the full list.

Usage: `python3 wikidata.py <e-mail associated to search>`
