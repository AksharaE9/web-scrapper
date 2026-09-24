import asyncio
import httpx
import json
import time

async def main():
    async with httpx.AsyncClient(timeout=120.0) as client:
        # Submit run for degree college in Ameerpet, Hyderabad
        payload = {
            "location": {
                "raw_text": "Ameerpet, Hyderabad",
                "locality": "Ameerpet",
                "city": "Hyderabad",
                "country": "India"
            },
            "keywords": ["degree college"],
            "max_results": 25,
            "min_confidence": 0.5,
            "enrich_websites": True,
            "sources": ["overture", "osm"]
        }
        
        print("Submitting run for 'degree college' in 'Ameerpet, Hyderabad'...")
        res = await client.post("http://127.0.0.1:8000/api/runs", json=payload)
        assert res.status_code == 202, f"Expected 202, got {res.status_code}: {res.text}"
        run_data = res.json()
        run_id = run_data["run_id"]
        print(f"Run ID: {run_id}")
        
        # Poll for completion
        start_t = time.time()
        while time.time() - start_t < 90:
            r = await client.get(f"http://127.0.0.1:8000/api/runs/{run_id}")
            data = r.json()
            status = data.get("status")
            print(f"Status after {time.time() - start_t:.1f}s: {status}")
            if status in ("completed", "failed", "partial"):
                print("\n=== FINAL RUN SUMMARY ===")
                print(f"Status: {status}")
                print(f"Completion Reason: {data.get('completion_reason')}")
                stats = data.get("stats") or {}
                print("Source Stats:", json.dumps(stats.get("source_stats"), indent=2))
                
                # Fetch leads
                leads_r = await client.get(f"http://127.0.0.1:8000/api/runs/{run_id}/leads?decision=accepted")
                accepted_leads = leads_r.json().get("items", [])
                print(f"\nAccepted Leads Count: {len(accepted_leads)}")
                for idx, lead in enumerate(accepted_leads[:10], 1):
                    name = lead.get("name")
                    cats = lead.get("categories") or []
                    score = lead.get("relevance_score")
                    phone = lead.get("phone")
                    print(f"  {idx}. {name} (Score: {score}) | Phone: {phone} | Cats: {cats}")
                
                review_r = await client.get(f"http://127.0.0.1:8000/api/runs/{run_id}/leads?decision=review")
                review_leads = review_r.json().get("items", [])
                print(f"Review Queue Count: {len(review_leads)}")
                
                rejected_r = await client.get(f"http://127.0.0.1:8000/api/runs/{run_id}/leads?decision=rejected")
                rejected_leads = rejected_r.json().get("items", [])
                print(f"Rejected Count: {len(rejected_leads)}")
                break
            await asyncio.sleep(2)

if __name__ == "__main__":
    asyncio.run(main())
