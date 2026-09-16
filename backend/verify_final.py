import httpx

r = httpx.get('http://127.0.0.1:8000/api/runs', timeout=5)
runs = r.json()
print(f"Total runs recorded: {len(runs)}")

if runs:
    latest = runs[0]
    run_id = latest["id"]
    print(f"Latest run ID: {run_id} | Status: {latest['status']} | Locality: {latest.get('locality')}")

    leads_res = httpx.get(f'http://127.0.0.1:8000/api/runs/{run_id}/leads?limit=10', timeout=5)
    leads_data = leads_res.json()
    leads = leads_data if isinstance(leads_data, list) else leads_data.get("leads", [])
    print(f"Leads returned for latest run: {len(leads)}")
    for l in leads[:5]:
        dist_str = f"{l.get('distance_km')}km" if l.get("distance_km") is not None else "N/A"
        print(f"  Rank #{l.get('rank')}: {l.get('canonical_name')} | Category: {l.get('primary_category')} | Dist: {dist_str} | Phone: {l.get('phones_e164')} | Tier: {l.get('tier')}")
