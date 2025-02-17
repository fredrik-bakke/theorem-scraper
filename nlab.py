import sys
import requests
from bs4 import BeautifulSoup
import urllib.parse

def generate_theorem_list(sitemap_soup, theorem_word = "theorem", banned_strings = None, blacklist=None):
    if banned_strings is None:
        banned_strings = set()
    if blacklist is None:
        blacklist = set()

    links = sitemap_soup.find_all("a")

    pages = [(link.text.strip(), link.get("href")) for link in links if link.get("href") and theorem_word in link.text.lower() and link.text.strip().lower() != theorem_word]

    # Remove blacklisted entries and those containing banned strings
    filtered_pages = [title for title, url in pages if title.lower() not in blacklist and not any(word in title.lower() for word in banned_strings)]

    # Remove titles where one is a substring of another, keeping only the smaller ones
    unique_titles = set(title.lower() for title in filtered_pages)
    final_pages = [title for title in filtered_pages if not any(title.lower() != other and other in title.lower() for other in unique_titles)]

    return sorted(final_pages)


def pretty_print_theorem_list(theorem_list):

    for index, title in enumerate(theorem_list, start=1):
        decoded_title = urllib.parse.unquote(title)
        print(f"{index:>4}. {decoded_title}")


def pretty_print_theorem_pages(sitemap_soup, theorem_word = "theorem", banned_strings = None, blacklist=None):
    theorem_pages = generate_theorem_list(sitemap_soup, theorem_word, banned_strings, blacklist)
    pretty_print_theorem_list(theorem_pages)

if __name__ == "__main__":

    common_ban = {"> history" , "- svg", "- contents", "-- table", "- table", "-- references", "-- section", "lecture"}
    blacklist = {"A mechanization of the Blakers-Massey connectivity theorem in Homotopy Type Theory", "correspondence type", "one-to-one correspondence", "Mochizuki's corollary 3.12", "duality involution", "dependent correspondence", "deduction theorem"}


    sitemap_url = "https://ncatlab.org/nlab/all_pages"
    response = requests.get(sitemap_url)
    if response.status_code != 200:
        print("Failed to retrieve the sitemap.")
        sys.exit(1)

    sitemap_soup = BeautifulSoup(response.text, "html.parser")
    blacklist = {s.lower() for s in blacklist}

    theorems = generate_theorem_list(sitemap_soup, "theorem", {"theorems", *common_ban}, blacklist)
    lemmas = generate_theorem_list(sitemap_soup, "lemma", {"lemmas", *common_ban}, blacklist)
    conjectures = generate_theorem_list(sitemap_soup, "conjecture", {"conjectures", *common_ban}, blacklist)
    corollaries = generate_theorem_list(sitemap_soup, "corollary", {"corollaries", *common_ban}, blacklist) # No named established corollaries
    correspondences = generate_theorem_list(sitemap_soup, "correspondence", {"correspondences", "correspondence between", *common_ban}, blacklist)
    dualities = generate_theorem_list(sitemap_soup, "duality", {"dualities", *common_ban}, blacklist)
    # propositions = generate_theorem_list(sitemap_soup, "proposition", {"propositions", "propositional", *common_ban}, blacklist) # No named propositions
    # identities = generate_theorem_list(sitemap_soup, "identity", {"identities", "identity type", *common_ban}, blacklist)

    print("\n\n======================== THEOREM ========================")
    pretty_print_theorem_list(theorems)
    print("\n\n======================== LEMMA ========================")
    pretty_print_theorem_list(lemmas)
    print("\n\n======================== CONJECTURE ========================")
    pretty_print_theorem_list(conjectures)
    print("\n\n======================== COROLLARY ========================")
    pretty_print_theorem_list(corollaries)
    print("\n\n======================== CORRESPONDENCE ========================")
    pretty_print_theorem_list(correspondences)
    print("\n\n======================== DUALITY ========================")
    pretty_print_theorem_list(dualities)

    print("\n\n======================== TOTAL ========================")
    pretty_print_theorem_list(sorted([*theorems, *lemmas, *conjectures, *dualities, *correspondences]))
