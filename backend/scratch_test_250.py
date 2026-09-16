import httpx
import time

payload = {
    'location': {
        'locality': 'Indiranagar',
        'city': 'Bengaluru',
        'state': 'Karnataka',
        'country': 'India'
    },
    'keywords': ['gym', 'fitness center'],
    'exclude_keywords': [],
    'max_results': 250,
    'sources': ['overture', 'osm']
}

r = httpx.post('http://127.0.0.1:8000/api/runs', json=payload, timeout=10)
data = r.json()
run_id = data['run_id']
print(f"Started run: {run_id}")

# Wait for background graph nodes to finish
time.sleep(5)

leads_res = httpx.get(f'http://127.0.0.1:8000/api/runs/{run_id}/leads?limit=20', timeout=10)
leads = leads_res.json()
total = leads.get('total', 0)
print(f"Total leads discovered: {total}")

for l in leads.get('leads', [])[:8]:
    dist = f"{l.get('distance_km')}km" if l.get('distance_km') is not None else "N/A"
    print(f"Rank #{l.get('rank')} | {l.get('canonical_name')} | Locality: {l.get('locality')} | Dist: {dist} | Phone: {l.get('phones_e164')} | Tier: {l.get('tier')}")
