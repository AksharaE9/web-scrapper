import urllib.request
import urllib.parse
import json
import time
from pathlib import Path

SPARQL_ENDPOINT = "https://query.wikidata.org/sparql"
USER_AGENT = "LeadCoreZeroConceptFoundry/1.0 (dev@leadcore.local)"

TAG_KEYS = ["shop=", "amenity=", "office=", "craft=", "healthcare=", "leisure=", "tourism="]

def fetch_wikidata_aliases():
    out_dir = Path("data/taxonomy")
    out_dir.mkdir(parents=True, exist_ok=True)
    all_bindings = []
    
    for tag_key in TAG_KEYS:
        query = f"""
        SELECT ?item ?osmtag ?lang ?label ?alt WHERE {{
          ?item wdt:P1282 ?osmtag .
          FILTER(CONTAINS(STR(?osmtag), "{tag_key}"))
          OPTIONAL {{
            ?item rdfs:label ?label .
            BIND(LANG(?label) AS ?lang)
            FILTER(?lang IN ("en","hi","te","ta","kn","ml","mr","bn"))
          }}
          OPTIONAL {{
            ?item skos:altLabel ?alt .
            FILTER(LANG(?alt) IN ("en","hi","te","ta","kn","ml","mr","bn"))
          }}
        }} LIMIT 500
        """
        params = {"query": query, "format": "json"}
        url = f"{SPARQL_ENDPOINT}?{urllib.parse.urlencode(params)}"
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                bindings = data.get("results", {}).get("bindings", [])
                all_bindings.extend(bindings)
                print(f"Fetched {tag_key}: {len(bindings)} bindings")
        except Exception as e:
            print(f"Error fetching {tag_key}: {e}")
        time.sleep(1.0)
        
    out_file = out_dir / "wikidata_aliases.json"
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(all_bindings, f, indent=2)
    print(f"Saved {len(all_bindings)} total bindings to {out_file}")

if __name__ == "__main__":
    fetch_wikidata_aliases()
