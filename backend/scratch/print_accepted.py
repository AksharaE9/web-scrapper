import httpx

r = httpx.get('http://127.0.0.1:8000/api/runs/76eb3182-fc36-4f91-81d5-36514cbb74e7/leads?decision=accepted')
items = r.json()['items']
print(f"Total accepted leads: {len(items)}")
for i, item in enumerate(items, 1):
    print(f"{i}. {item['canonical_name']} | Tier: {item['tier']} | Phones: {item['phones_e164']} | Website: {item['website_url']}")
