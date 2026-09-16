# LeadCore Zero v2 — Compliance & Responsible Collection Policy

**Effective date:** 2026-09-16  
**Jurisdiction:** India (primary); international visitors to businesses covered.  
**Status:** Informational for the operator — not legal advice.

---

## 1. Robots.txt and Website Crawling

- **robots.txt is always obeyed.** The Scrapling spider is configured with
  `robots_txt_obey=True`. Pages disallowed for `LeadCoreZero` or `*` are
  **never fetched**, even if they may contain useful contact data.
- **User-Agent** identifies the crawler:
  `LeadCoreZero/2.0 (+contact: <CONTACT_EMAIL>)` where `CONTACT_EMAIL` is
  set by the operator in `.env`. Do not leave this blank.
- **AutoThrottle** is enabled on all Scrapling sessions. The default delay
  between requests to the same domain is 1–3 seconds; it adapts to server
  response times.
- **Per-domain concurrency** is capped at 1 concurrent request.
- If a site returns a bot-challenge page (Cloudflare Turnstile, CAPTCHA,
  403/503 with challenge markers), the domain is **immediately marked
  `blocked_by_site`** and no further requests are made. No bypass attempts.
- No proxies are used. Requests originate from the operator's IP address.

---

## 2. Public API Fair-Use Policies

### 2.1 Nominatim (OpenStreetMap)

- **Maximum 1 request per second** enforced via a per-instance rate limiter.
- Every Nominatim response is **cached in `geo_cache`** (perpetual TTL).
  The same query never hits Nominatim twice.
- No bulk geocoding (i.e., resolving thousands of addresses in a batch run).
  Nominatim is used only for locality/boundary resolution at run-creation time.
- Structured search parameters (`city`, `county`, `state`, `country`) are
  preferred over free-text `q=` to reduce ambiguity load.
- `countrycodes=in` is sent for Indian queries to reduce false positives.

### 2.2 Overpass API (OpenStreetMap)

- The endpoint list (`OVERPASS_ENDPOINTS` in settings) should include at least
  two public instances to allow failover without hammering one server.
- All queries include `[timeout:90]`.
- On HTTP 429 or 504, the system backs off (exponential, up to 120 s) before
  trying the next endpoint.
- `/api/status` is checked before each query to honour the server's slot
  availability.
- No excessive or repetitive queries: each `(bbox, osm_tag_filter)` combination
  is run once per run, not per keyword.

### 2.3 Wikidata SPARQL

- A descriptive User-Agent is sent: `LeadCoreZero/2.0 <CONTACT_EMAIL>`.
- Queries include a `LIMIT` clause (max 2,000 results per query).
- The Wikidata agent only runs when the keyword planner flags an
  "institution-type" keyword (hospital, college, government office, etc.).
- Results are cached in `geo_cache` with a 7-day TTL.

### 2.4 AllThePlaces

- Only public GeoJSON output files are used (no scraping of the AllThePlaces website).
- The current output licence is checked at build time and stored in
  `docs/01_decisions.md`. If the licence changes to a non-permissive one, the
  source is disabled.

---

## 3. Data Licences and Attribution

Every record in `business_sources` carries the `licence` field. Exports include
an **Attribution** sheet.

| Source | Licence | Attribution requirement |
|---|---|---|
| OpenStreetMap via Overpass | ODbL 1.0 | "© OpenStreetMap contributors" — must appear in any published derived work or database |
| Overture Maps (CDLA-Permissive-2.0) | CDLA-Permissive-2.0 | Attribution to the Overture Maps Foundation; per-record `sources` list preserved |
| Overture Maps (Apache-2.0 — Foursquare-sourced) | Apache-2.0 | NOTICE file attribution for Foursquare-sourced records |
| Wikidata | CC0 | No attribution legally required; recommended as good practice |
| AllThePlaces | Check current licence at `docs/01_decisions.md` | As specified by their licence |
| User-supplied imports | Inherits the licence of the source dataset | Operator's responsibility |
| Business websites | Public information from permitted pages | No licence; fair use |

**ODbL Share-Alike obligation:** If you create and distribute a database that is
a substantial derivative of OSM data (including data enriched with OSM-sourced
records), that database must itself be licensed under ODbL. The `leadcore-zero`
database is **not distributed**; it is a local operational store. If you export
and re-publish the data, you must comply with ODbL.

---

## 4. India Data Protection — DPDP Act 2023 Awareness

The Digital Personal Data Protection Act, 2023 is in effect. Business contact
data can constitute personal data:

- **Sole proprietors and freelancers:** A phone number or email registered to an
  individual (not a business entity) is personal data under the DPDP Act.
- **`personal_number_risk` flag:** The system flags any mobile number that has
  no associated business website, business listing, or published category, and
  marks it in the `verifications` table as `personal_number_risk: true`. The
  UI surfaces this flag on the lead drawer with a reminder.
- **Data minimisation:** Only contact fields relevant to B2B outreach are
  collected. Personal addresses and personal social profiles are not collected.
- **Removal requests:** If a business owner requests removal of their data, use
  the `suppression_list` table. The `POST /api/leads/{id}/suppress` endpoint
  adds the phone/email/domain to the suppression list, and subsequent exports
  exclude the record.
- **Retention:** `doc_chunks` (crawled text) have a 30-day TTL enforced by
  `scripts/cleanup_chunks.py`. Raw HTML is never stored.

---

## 5. Telecom Regulatory Authority of India (TRAI) — Commercial Communication

SMS and voice calls for commercial purposes in India require:
- Sender registration with TRAI's Distributed Ledger Technology (DLT) platform.
- Compliance with the Unsolicited Commercial Communication (UCC) regulations
  (TCCCPR 2018).
- Checking the National Do Not Disturb (NDND) registry before outreach.

**The export UI shows a TRAI reminder banner** when a CSV/XLSX export is
downloaded, linking to the NDND check process. This is informational; enforcement
is the operator's responsibility.

---

## 6. Prohibited Practices (hard system-level blocks)

The following are technically blocked, not just policy guidance:

| Practice | How it's blocked |
|---|---|
| CAPTCHA / bot-challenge bypass | `challenge_detect.py` detects and marks `blocked_by_site`; no retry |
| Proxy use | No proxy configuration in the codebase; `httpx` client is direct |
| SMTP probing to verify email | Only MX/A DNS lookups; no TCP connection to port 25/465/587 |
| Scraping of explicitly excluded platforms | Platform domains (google.com, justdial.com, etc.) are in a `BLOCKED_DOMAINS` list checked before any fetch |
| Storing raw HTML | `crawl_log` stores only URL + outcome; `doc_chunks` stores markdown text only |
| API key usage | No API key anywhere in the codebase or `.env.example` |

---

## 7. Operator Responsibilities

By running LeadCore Zero v2, the operator agrees to:
1. Set a valid `CONTACT_EMAIL` in `.env` so that website operators can contact
   you if your crawler causes issues.
2. Honour removal requests from businesses via the suppression workflow.
3. Use exported data only for lawful B2B outreach.
4. Comply with ODbL attribution obligations if publishing a derived database.
5. Register with TRAI DLT before conducting SMS/voice outreach campaigns.
