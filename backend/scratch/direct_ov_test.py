import asyncio
from app.graph.state import KeywordPlan, ResolvedGeo
from app.graph.nodes.n3a_overture import n3a_overture_node
from app.graph.nodes.n2_keyword import plan_keyword
from app.graph.nodes.n1_geo import n1_geo_node

async def test():
    state = {
        "run_id": "test-degree-college",
        "locality": "Ameerpet",
        "city": "Hyderabad",
        "state": "Telangana",
        "country": "India",
        "keywords": ["degree college"],
        "options": {"sources": ["overture"]},
    }
    
    # 1. Geo resolve
    geo_res = await n1_geo_node(state)
    geo = geo_res.get("geo")
    print("Geo resolved:", geo.display_name, "BBox:", geo.bbox)
    
    # 2. Keyword plan
    kw_res = await plan_keyword("degree college")
    print("Keyword Plan:", kw_res.model_dump())
    
    # 3. Overture
    state["geo"] = geo
    state["plans"] = [kw_res]
    ov_res = await n3a_overture_node(state)
    candidates = ov_res.get("candidates", [])
    source_stats = ov_res.get("source_stats", {})
    print(f"\nOverture Source Stats: {source_stats}")
    print(f"Candidates Count: {len(candidates)}")
    for i, c in enumerate(candidates[:10], 1):
        print(f"  {i}. {c.name} | Cats: {c.categories} | Match: {c.evidence.get('n3a_match_reason')}")

if __name__ == "__main__":
    asyncio.run(test())
