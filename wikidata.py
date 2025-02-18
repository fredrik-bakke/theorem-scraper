import time
import requests
import re
from SPARQLWrapper import SPARQLWrapper, JSON
from bs4 import BeautifulSoup
import unicodedata
import html
import sys

def normalize_name(name):
    # Normalize to NFKD, remove diacritics, replace hyphens, remove text in parentheses, and lowercase
    name = unicodedata.normalize("NFKD", name)
    name = html.unescape(name)  # Convert HTML escape codes
    name = name.replace('.27', "'") # '
    name = name.replace("'s", '').replace("'", '')
    name = "".join([c for c in name if not unicodedata.combining(c)])  # Remove accents
    name = name.replace("–", "-").replace("—", "-").replace('---', '-').replace('--', '-')  # Normalize hyphens
    name = re.sub(r"\(.*?\)", "", name)  # Remove text in parentheses
    name = name.replace('_', ' ') # Replace underscores by spaces
    return name.lower().strip()

def get_wikidata_theorems(email):
    sparql = SPARQLWrapper("https://query.wikidata.org/sparql")
    sparql.addCustomHttpHeader("User-Agent", f"WikidataTheoremScraper/1.0 ({email})")

    query = """
    SELECT ?theorem ?theoremLabel ?identifier WHERE {
      ?theorem wdt:P31 wd:Q65943.
      OPTIONAL { ?theorem wdt:P818 ?identifier }
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    LIMIT 50000
    """

    sparql.setQuery(query)
    sparql.setReturnFormat(JSON)

    for attempt in range(3):  # Retry up to 3 times
        try:
            results = sparql.query().convert()
            break
        except Exception as e:
            print(f"Query failed (attempt {attempt + 1}): {e}")
            time.sleep(5)
    else:
        print("Failed after 3 attempts.")
        return [], []

    labeled_theorems = []
    unlabeled_theorems = []

    for result in results["results"]["bindings"]:
        wdid = result["theorem"]["value"].split("/")[-1]
        name = result.get("theoremLabel", {}).get("value", "").strip()
        identifier = result.get("identifier", {}).get("value", "N/A")

        if not name or name == wdid:
            unlabeled_theorems.append((wdid, name, identifier))
        else:
            labeled_theorems.append((wdid, name, identifier))

    return labeled_theorems, unlabeled_theorems

def get_wikipedia_theorems(email):
    url = "https://en.wikipedia.org/w/index.php?title=List_of_theorems&action=raw"
    response = requests.get(url, headers={"User-Agent": f"WikidataTheoremScraper/1.0 ({email})"})

    if response.status_code != 200:
        print("Failed to fetch Wikipedia source.")
        return set()

    theorem_names = set()

    for line in response.text.split("\n"):
        match = re.match(r"^\*\s*\[\[(.+?)\]\]\s*\(", line)
        if match:
            theorem_names.update(thm.strip() for thm in match.group(1).split('|'))

    return theorem_names

if __name__ == "__main__":
    email = sys.argv[1]
    wikipedia_theorems = get_wikipedia_theorems(email)

    normalized_wikipedia_theorems = sorted(normalize_name(thm) for thm in wikipedia_theorems)
    print("Wikipedia list of theorems (normalized):")
    print(normalized_wikipedia_theorems)
    s_normalized_wikipedia_theorems = '|'.join(normalized_wikipedia_theorems)

    labeled_theorems, unlabeled_theorems = get_wikidata_theorems(email)

    unmatched_theorems = sorted((t for t in labeled_theorems if normalize_name(t[1]) not in s_normalized_wikipedia_theorems), key=lambda t: int(t[0][1:]))

    print("\n\nWikidata Theorems not in Wikipedia list:")
    for i, (wdid, name, _) in enumerate(unmatched_theorems):
        print(f"{i+1:>4}. {"WDID("+wdid+")":>15} {name}")

    # print("\nWikidata Unlabeled Theorems (no name or name matches WDID):")
    # for i, (wdid, name, _) in enumerate(unlabeled_theorems):
    #     print(f"{i+1:>4}. {"WDID("+wdid+")":>15} {name}")
