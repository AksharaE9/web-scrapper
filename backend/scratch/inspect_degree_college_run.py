import asyncio
import httpx
import json

async def main():
    async with httpx.AsyncClient() as client:
        r = await client.get("http://127.0.0.1:8000/api/runs/76eb3182-fc36-4f91-81d5-36514cbb74e7")
        data = r.json()
        print("=== RUN STATUS ===")
        print("Status:", data.get("status"))
        print("Completion Reason:", data.get("completion_reason"))
        stats = data.get("stats") or {}
        print("Source Stats:", json.dumps(stats.get("source_stats"), indent=2))
        print("Candidate Count:", stats.get("candidate_count"))
        print("Resolved Entity Count:", stats.get("resolved_entity_count"))

        leads_r = await client.get("http://127.0.0.1:8000/api/runs/76eb3182-fc36-4f91-81d5-36514cbb74e7/leads?decision=accepted")
        accepted = leads_r.json().get("items", [])
        print(f"\nAccepted Leads Count: {len(accepted)}")
        for idx, lead in enumerate(accepted[:10], 1):
            name = lead.get("name")
            phone = lead.get("phone")
            cats = lead.get("categories") or []
            print(f"  {idx}. {name} | Phone: {phone} | Cats: {cats}")

if __name__ == "__main__":
    asyncio.run(main())
