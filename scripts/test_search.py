from lead_qualifier.enrichment.search.router import web_search

if __name__ == "__main__":
    q = "openai company overview"
    results = web_search(q, num=5)
    for r in results:
        print(r.title, "-", r.link)
