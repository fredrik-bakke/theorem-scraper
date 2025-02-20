import time
import requests
import re
from SPARQLWrapper import SPARQLWrapper, JSON
from bs4 import BeautifulSoup
import unicodedata
import html
import sys
import urllib
import string
import aiohttp
import asyncio

def normalize_name(name):
    name = urllib.parse.unquote(name)
    name = html.unescape(name) # Convert HTML escape codes
    # Normalize to NFKD, remove diacritics, replace hyphens and lowercase
    name = unicodedata.normalize("NFKD", name)
    name = name.replace('.27', "'") # '
    name = name.replace("'s", '').replace('’s', '') # Remove possessive
    name = "".join([c for c in name if not unicodedata.combining(c)])  # Remove accents
    name = name.replace("–", "-").replace("—", "-").replace('---', '-').replace('--', '-')  # Normalize hyphens
    name = re.sub(r"\(.*?\)", "", name)  # Remove text in parentheses
    name = name.replace('_', ' ') # Replace underscores by spaces
    name = name.translate(str.maketrans('', '', string.punctuation))  # Remove punctuation
    name = re.sub(r'\s+', ' ', name).strip() # Replace multiple spaces with a single space
    name = name.replace('aa', 'a').replace('ae', 'a').replace('oe', 'o').replace('ue', 'u') # Replace common transliterations
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

def get_mathematical_fields(email):
    query = """
    SELECT ?field ?fieldLabel WHERE {
      ?field wdt:P31 wd:Q1936384.
      SERVICE wikibase:label { bd:serviceParam wikibase:language "en". }
    }
    """

    url = "https://query.wikidata.org/sparql"
    headers = {"Accept": "application/json", "User-Agent": f"WikidataTheoremScraper/1.0 ({email})"}
    response = requests.get(url, headers=headers, params={"query": query})

    if response.status_code != 200:
        return None

    data = response.json()
    fields = [(entry["field"]["value"].split('/')[-1], entry["fieldLabel"]["value"]) for entry in data["results"]["bindings"]]
    fields = [(wdid , name) for (wdid , name) in fields if wdid != name]
    return fields

async def fetch(session, url, headers):
    async with session.get(url, headers=headers) as response:
        return await response.text()

async def get_wikipedia_theorems_async(email):
    url = "https://en.wikipedia.org/w/index.php?title=List_of_theorems&action=raw"
    headers = {"User-Agent": f"WikidataTheoremScraper/1.0 ({email})"}

    async with aiohttp.ClientSession() as session:
        response_text = await fetch(session, url, headers)

    theorem_names = set()
    for line in response_text.split("\n"):
        match = re.match(r"^\*\s*\[\[(.+?)\]\]\s*\(", line)
        if match:
            theorem_parts = match.group(1).split('|')
            theorem_names.update(thm.strip() for thm in theorem_parts)

    return theorem_names

async def check_wikipedia_redirects_async(theorem_name, email):
    url = f"https://en.wikipedia.org/wiki/{theorem_name.replace(' ', '_')}"
    headers = {"User-Agent": f"WikidataTheoremScraper/1.0 ({email})"}

    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=headers, allow_redirects=True) as response:
            if response.status != 200:
                return None, None
            redirect_title = urllib.parse.unquote(str(response.url).split("/")[-1]).replace('_', ' ')
            return redirect_title, str(response.url)

async def get_wikipedia_alternate_names_async(main_theorem_name, email):
    raw_url = f"https://en.wikipedia.org/w/index.php?title={main_theorem_name.replace(' ', '_')}&action=raw"
    headers = {"User-Agent": f"WikidataTheoremScraper/1.0 ({email})"}

    async with aiohttp.ClientSession() as session:
        response_text = await fetch(session, raw_url, headers)

    boldface_matches = re.findall(r"'''(.*?)'''", response_text)
    return boldface_matches

async def main(email):
    wikipedia_theorems = await get_wikipedia_theorems_async(email)
    normalized_wikipedia_theorems = set(normalize_name(thm) for thm in wikipedia_theorems)

    alt_thm_name_keywords = ('theorem', 'lemma', 'corollary', 'proposition', 'lemma', 'correspondence', 'identity', 'conjecture', 'duality')

    print("Checking redirects and alternative theorem names for Wikipedia's list of theorems.")
    i = 1
    tasks = []
    for thm in wikipedia_theorems:
        tasks.append(check_wikipedia_redirects_async(thm, email=email))
    results = await asyncio.gather(*tasks)

    alt_tasks = []
    for thm, (redirect_title, url) in zip(wikipedia_theorems, results):
        if redirect_title:
            n_redirect_title = normalize_name(redirect_title)
            if n_redirect_title not in normalized_wikipedia_theorems:
                normalized_wikipedia_theorems.update(n_redirect_title)

            alt_tasks.append(get_wikipedia_alternate_names_async(redirect_title, email=email))

    alt_results = await asyncio.gather(*alt_tasks)

    for alt_theorem_names in alt_results:
        for alt_thm_name in alt_theorem_names:
            n_alt_thm_name = normalize_name(alt_thm_name)
            if n_alt_thm_name not in normalized_wikipedia_theorems and any(s in n_alt_thm_name and len(s) + 3 < len(n_alt_thm_name) for s in alt_thm_name_keywords):
                normalized_wikipedia_theorems.update(n_alt_thm_name)

    print("\nWikipedia list of theorems (exclusion strings):")
    normalized_wikipedia_theorems = sorted(thm for thm in normalized_wikipedia_theorems if len(thm) > 3)

    s_normalized_wikipedia_theorems = '|'.join(normalized_wikipedia_theorems)
    print(s_normalized_wikipedia_theorems)

    labeled_theorems, unlabeled_theorems = get_wikidata_theorems(email)

    unmatched_theorems = sorted((t for t in labeled_theorems if normalize_name(t[1]) not in s_normalized_wikipedia_theorems), key=lambda t: int(t[0][1:]))

    theorems_with_page_in_wikipedia_list = []
    theorems_with_page_not_in_wikipedia_list = []

    print("\n\nWikidata theorem search (theorems that are not on Wikipedia's list):")
    tasks = []
    for i, (wdid, name, _) in enumerate(unmatched_theorems):
        tasks.append(check_wikipedia_redirects_async(name, email=email))
    results = await asyncio.gather(*tasks)

    for i, ((wdid, name, _), (redirect_title, url)) in enumerate(zip(unmatched_theorems, results)):
        if not redirect_title:
            print(f"🟨 {i+1:>4}. {"WDID("+wdid+")":>15} {name} (No valid redirect found)")
        elif normalize_name(redirect_title) in s_normalized_wikipedia_theorems:
            print(f"✅ {i+1:>4}. {"WDID("+wdid+")":>15} {name} (Redirects to theorem in list: {redirect_title}, {url})")
            theorems_with_page_in_wikipedia_list.append((wdid, name, url))
        elif (normalize_name(redirect_title) == normalize_name(name)):
            print(f"❌ {i+1:>4}. {"WDID("+wdid+")":>15} {name} ({url})")
            theorems_with_page_not_in_wikipedia_list.append((wdid, name, url))
        else:
            print(f"❌ {i+1:>4}. {"WDID("+wdid+")":>15} {name} (Redirects to theorem not in list: {redirect_title}, {url})")
            theorems_with_page_not_in_wikipedia_list.append((wdid, name, url))

    print(f"\nTotal number of Wikidata theorems with Wikipedia pages that are not in Wikipedia's list of theorems: {len(theorems_with_page_not_in_wikipedia_list)}")

if __name__ == "__main__":
    email = sys.argv[1]
    asyncio.run(main(email))
