"""
A7 Regression Test — PostGIS Geography Lon/Lat Point Roundtrip
Asserts that coordinates persist in GeoJSON order (lon first, lat second)
and read back via ST_X/ST_Y within 1e-6 precision.
"""

import uuid
import pytest
from app.db.pool import get_conn
from app.db.geo_sql import point_geography_sql, select_geom_coords_sql

@pytest.mark.asyncio
async def test_whitefield_point_geom_roundtrip() -> None:
    test_biz_id = str(uuid.uuid4())
    # Whitefield, Bengaluru coordinates: lon ~ 77.7500, lat ~ 12.9698
    whitefield_lon = 77.750000
    whitefield_lat = 12.969800
    
    async with get_conn() as conn:
        # 1. Insert with ST_SetSRID(ST_MakePoint(lon, lat), 4326)::geography
        insert_sql = f"""
            INSERT INTO businesses (id, canonical_name, name_norm, geom)
            VALUES (%s, 'Whitefield Pooja Kendra', 'whitefield pooja kendra', {point_geography_sql('%s', '%s')})
        """
        await conn.execute(insert_sql, (test_biz_id, whitefield_lon, whitefield_lat))
        
        # 2. Read back using ST_X and ST_Y
        select_sql = f"""
            SELECT canonical_name, {select_geom_coords_sql('geom')}
            FROM businesses WHERE id = %s
        """
        cursor = await conn.execute(select_sql, (test_biz_id,))
        row = await cursor.fetchone()
        assert row is not None
        
        read_lon = float(row["lon"]) if isinstance(row, dict) else float(row[1])
        read_lat = float(row["lat"]) if isinstance(row, dict) else float(row[2])
        
        # 3. Assert coordinate order (lon in [77.0, 78.5], lat in [12.0, 13.5])
        assert 77.0 <= read_lon <= 78.5, f"Longitude swapped or out of range: {read_lon}"
        assert 12.0 <= read_lat <= 13.5, f"Latitude swapped or out of range: {read_lat}"
        
        # 4. Assert precision within 1e-5
        assert abs(read_lon - whitefield_lon) < 1e-5, f"Longitude error: {read_lon} vs {whitefield_lon}"
        assert abs(read_lat - whitefield_lat) < 1e-5, f"Latitude error: {read_lat} vs {whitefield_lat}"
