from lead_qualifier.enrichment.search.serper_client import serper_search

def main():
    q = 'Amazon company founded year headquarters revenue site:wikipedia.org OR site:wikidata.org'
    results = serper_search(q, num=5)
    for r in results:
        print(r.title)
        print(r.link)
        print(r.snippet[:140])
        print("-" * 60)

if __name__ == "__main__":
    main()
