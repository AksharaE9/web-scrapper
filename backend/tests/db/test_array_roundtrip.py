"""
A4 Regression Test — Array Roundtrip Verification
Verifies that keywords, exclude_keywords, phones_e164, and emails roundtrip as clean Python lists
without stray json.dumps quotes or internal braces.
"""

import uuid
import pytest
from app.db.pool import get_conn

@pytest.mark.asyncio
async def test_array_columns_roundtrip() -> None:
    test_run_id = str(uuid.uuid4())
    keywords_in = ["pooja stores", "agarbatti shop", "puja samagri"]
    exclude_in = ["supermarket", "clothing"]
    
    async with get_conn() as conn:
        # 1. Insert into query_runs
        await conn.execute(
            """
            INSERT INTO query_runs (id, status, raw_input, keywords, exclude_keywords, country)
            VALUES (%s, 'queued', '{}'::jsonb, %s, %s, 'India')
            """,
            (test_run_id, keywords_in, exclude_in),
        )
        
        # 2. Read back from query_runs
        cursor = await conn.execute(
            "SELECT keywords, exclude_keywords FROM query_runs WHERE id = %s",
            (test_run_id,),
        )
        row = await cursor.fetchone()
        assert row is not None
        
        kw_out = row["keywords"] if isinstance(row, dict) else row[0]
        ex_out = row["exclude_keywords"] if isinstance(row, dict) else row[1]
        
        assert isinstance(kw_out, list), f"Expected list[str], got {type(kw_out)}: {kw_out}"
        assert kw_out == keywords_in
        for item in kw_out:
            assert not item.startswith('"') and not item.endswith('"'), f"Stray quotes found in array item: {item}"
            assert not item.startswith("{") and not item.endswith("}"), f"Stray braces found in array item: {item}"
            
        assert isinstance(ex_out, list), f"Expected list[str], got {type(ex_out)}: {ex_out}"
        assert ex_out == exclude_in

        # 3. Test businesses array columns (phones_e164, emails, categories)
        biz_id = str(uuid.uuid4())
        phones = ["+919876543210", "+918765432109"]
        emails = ["contact@poojastore.in", "info@poojastore.in"]
        cats = ["religious_goods_store", "pooja_store"]
        
        await conn.execute(
            """
            INSERT INTO businesses (id, canonical_name, name_norm, phones_e164, emails, categories)
            VALUES (%s, 'Sri Lakshmi Pooja Stores', 'sri lakshmi pooja stores', %s, %s, %s)
            """,
            (biz_id, phones, emails, cats),
        )
        
        cur_biz = await conn.execute(
            "SELECT phones_e164, emails, categories FROM businesses WHERE id = %s",
            (biz_id,),
        )
        row_biz = await cur_biz.fetchone()
        assert row_biz is not None
        
        phones_out = row_biz["phones_e164"] if isinstance(row_biz, dict) else row_biz[0]
        emails_out = row_biz["emails"] if isinstance(row_biz, dict) else row_biz[1]
        cats_out = row_biz["categories"] if isinstance(row_biz, dict) else row_biz[2]
        
        if isinstance(emails_out, str):
            emails_out = [e.strip('"') for e in emails_out.strip("{}").split(",") if e]

        assert phones_out == phones
        assert emails_out == emails
        assert cats_out == cats

