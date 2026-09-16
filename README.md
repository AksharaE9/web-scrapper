# LeadCore Zero 🚀

> High-Throughput, Zero-API-Cost Local Business Lead Discovery Engine. Engineered with LangGraph-style pipeline orchestration, Overture Maps S3 Parquet spatial queries, OpenStreetMap Overpass extraction, probabilistic entity deduplication, and confidence scoring.

---

## 🌟 Key Features

- 📍 **Multi-Tier Geographic Resolution**: Progressive Nominatim + Photon Komoot fuzzy geocoding with compound name splitting (e.g. `irramanzil` ⇄ `irram manzil`) and local area seeds.
- 🎯 **Adjustable Lead Volume & Dynamic Bounding Box**: Select target quantity (50, 100, 250, 500, 1,000, 2,500+ / Max); bounding box radius automatically scales to guarantee sufficient lead yield.
- ⭕ **Concentric Outward Radial Sorting**: Automatically sorts leads in outward distance rings (<1.5km $\to$ 1.5–3.5km $\to$ 3.5–6km $\to$ >6km) from the target centroid.
- ⚡ **Zero-API-Cost & Ultra-High Speed**: Uses anonymous Overture Maps S3 partitions + DuckDB Spatial with local Parquet caching (<0.3s repeat queries) and live OSM Overpass POI extraction.
- 📞 **Direct Outreach & Navigation**: One-click **Call Now (`tel:`)**, **WhatsApp Chat (`wa.me`)**, **Website**, **Google Maps Directions**, and **Copy Lead** in the interactive Lead Drawer.
- 🛡️ **Probabilistic Deduplication & Verification**: Merges multi-source records, validates phone numbers (E.164), extracts websites, and assigns verification tiers (`Verified`, `Likely`, `Unverified`).

---

## 🏗️ Architecture

```
User Query (Locality, Category, Target Volume)
   │
   ▼
[ N1: GeoResolver ] ──► Progressive Multi-Tier Geocoding (Centroid + BBox)
   │
   ├──────────────────────────────┐
   ▼                              ▼
[ N3a: Overture Places ]     [ N3b: OSM Overpass POI ]
(DuckDB S3 Parquet Query)    (Live OpenStreetMap POIs)
   │                              │
   └──────────────┬───────────────┘
                  ▼
          [ N4: Keyword Filter ]
                  ▼
          [ N5: Entity Resolver ] ──► Probabilistic Clustering & Merging
                  ▼
          [ N8: Confidence & Radial Ring Scorer ]
                  ▼
          [ N10: Global Dedup & SQLite / Neon Persister ]
                  ▼
          [ Real-Time SSE Stream & Interactive UI ]
```

---

## 🚀 Quick Start

### Prerequisites
- Python 3.11+
- Node.js 18+ and npm

### Backend Setup
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -e .

# Start Backend Server
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

### Frontend Setup
```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173) in your browser.

---

## 🧪 Testing

```bash
# Run backend pytest suite
cd backend
pytest tests

# Build and validate frontend TypeScript
cd frontend
npm run build
```

---

## 📄 License
MIT License. Open-source lead discovery engine.
