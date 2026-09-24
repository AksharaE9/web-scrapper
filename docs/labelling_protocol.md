# LeadCore Zero — Relevance Labelling Protocol
## Pre-registered Annotation Rubric (VALIDATE-1.0)

> **STATUS: PRE-REGISTERED** — This rubric MUST be read and signed off BEFORE any
> annotation begins. Changing this document after first use invalidates all labels.
> Hash this file at registration time:
> ```
> sha256sum docs/labelling_protocol.md
> ```
> Record the hash in `eval/eval_hash.txt` alongside the date and annotator names.

---

## 0. Purpose

This rubric governs the manual annotation of candidate business leads for the LeadCore
Zero relevance benchmark. It implements the annotation protocol mandated in §2.4 of the
VALIDATE-1.0 audit document.

**Why this matters**: Parry et al. (SIGIR 2025) found real human TREC assessors agreed
at Fleiss' κ = 0.17–0.28 — "near-random" — with pairwise overlap 0.11–0.19. Relevance
judgement is genuinely hard. A single annotator reporting no disagreement anywhere is
reporting their labelling policy, not a property of the system.

---

## 1. Annotator Requirements

| Requirement | Mandatory |
|---|---|
| Minimum annotators | **≥ 2** |
| At least one independent (did not build the system) | **YES — non-negotiable** |
| Blinded to which tier, build, or config produced an item | **YES** |
| Must sign this rubric before labelling | **YES** |
| LLM-only annotation accepted as sole M4 source | **NO** — human labels required |

If an LLM is used for any portion of labelling, report LLM-vs-human Cohen's κ on a
human-judged subsample, and publish **both** precision figures separately. Per Faggioli
et al. (ICTIR 2023), GPT-3.5 achieved κ = 0.26 vs. 0.52 human–human, and agreement
dropped to 47% on documents humans judged relevant. LLM judges fail asymmetrically in
the direction that inflates precision.

---

## 2. Blinding and Pool Construction

1. **Pool and shuffle** every candidate across ALL tiers and configurations before
   judging begins. The annotator MUST NOT see which tier, run, keyword, or config
   produced an item while judging.
2. **Seed 10–20% known-negatives** into the pool (drawn from `SEEDED_NEGATIVES` in
   `app/eval/mutations.py`). An annotator who accepts any seeded negative has a
   measurable false-positive rate; one who accepts all of them is not judging.
3. Present items in random order, one at a time.
4. Record:
   - Item ID
   - Annotator ID
   - Label (RELEVANT / NOT\_RELEVANT / UNCERTAIN)
   - Confidence (HIGH / MEDIUM / LOW)
   - Notes (free text for tie-break cases)

---

## 3. Annotation Schema

For each candidate business, label as:

| Label | Code | Meaning |
|---|---|---|
| **RELEVANT** | 1 | The business IS the type being searched for |
| **NOT RELEVANT** | 0 | The business is clearly NOT the type being searched for |
| **UNCERTAIN** | -1 | Genuinely ambiguous; both annotators must discuss and resolve |

Inter-annotator agreement: compute Cohen's κ on the full set before resolving
disagreements. Report κ alongside the scorecard.

---

## 4. Pre-registered Category Definitions

These definitions are FIXED before annotation begins. They cannot be changed after
the first label is recorded.

### 4.1 Degree College (`degree_college`)

**RELEVANT** (label = 1):
- An institution affiliated to a university that grants bachelor's (UG) or postgraduate
  (PG) degrees in arts, science, commerce, engineering, medicine, management, or law.
- Has a principal / principal's office, professors/lecturers, and semester-based curriculum.
- Recognised by UGC and/or AICTE.
- Examples: "Sri Venkateswara Degree College", "Aurora PG College", "JNTU College of Engineering"

**NOT RELEVANT** (label = 0) — EXPLICITLY INCLUDING:
- **K-12 schools** — including "Model Schools", "High Schools", "Secondary Schools",
  "Higher Secondary Schools", "Matriculation Schools", CBSE/ICSE schools.
  > 🔴 "Gowtham Model School" is NOT a degree college. It is a school.
  > 🔴 "St. Alphonsa High School" is NOT a degree college. It is a school.
  > 🔴 "Gitanjali Group of Schools" is NOT a degree college. It is schools.
- **Preschools / Kindergartens** — Montessori, play schools, daycare centres.
- **Coaching centres** — IIT-JEE, NEET, UPSC prep institutes, tutorial centres.
- **Vocational academies** — aviation academies, hospitality academies, skill training
  institutes, ITIs.
  > 🔴 "Flying Star Aviation and Hospitality Academy" is NOT a degree college.
- **IT training institutes** — "LiveTech" and similar short-course providers.
  > 🔴 "LiveTech" is NOT a degree college. It is an IT training institute.
- **Universities without a degree-granting college component** — the parent university
  as a legal entity is NOT the same as a degree college affiliated to it.

**TIE-BREAK RULE**: When uncertain, ask: "Does this institution issue UGC-recognised
bachelor's degrees?" If NO → label 0. If YES → label 1.

---

### 4.2 Gym / Fitness Centre (`gym`)

**RELEVANT** (label = 1):
- A gym, fitness centre, crossfit box, or sports club with workout equipment and
  membership-based access.

**NOT RELEVANT** (label = 0):
- Yoga studios without gym equipment (unless "gym" is in the name)
- Dance academies
- Sports coaching (cricket coaching, badminton coaching)
- Swimming pools without gym floor

---

### 4.3 Pharmacy (`pharmacy`)

**RELEVANT** (label = 1):
- A retail pharmacy / medical store / drug store dispensing prescription and OTC medications.
  Includes: "Apollo Pharmacy", "MedPlus", "Netmeds" pick-up points.

**NOT RELEVANT** (label = 0):
- Hospitals with in-patient pharmacy (the hospital entity, not its pharmacy counter)
- Ayurvedic / Siddha / homeopathy shops that do NOT dispense allopathic medications
- Medical equipment stores

---

### 4.4 Pooja Store (`pooja stores`)

**RELEVANT** (label = 1):
- A retail store primarily selling puja/religious goods: agarbatti, diyas, idols,
  puja samagri, flowers (as secondary), havan materials.

**NOT RELEVANT** (label = 0):
- General stationery stores (William Penn, pen shops)
- Gift shops (Archies, Hallmark)
- Fashion accessory shops
- Shoe stores
- Any store where religious items are a minor secondary line

---

### 4.5 Hotel (`hotel`)

**RELEVANT** (label = 1):
- A hotel, guesthouse, lodge, or service apartment providing paid overnight accommodation.

**NOT RELEVANT** (label = 0):
- Restaurants that use "hotel" in their name (common in South India — e.g. "Udupi Hotel"
  is a restaurant, NOT lodging)
- PGs (paying guest accommodation) — separate concept
- Hostels targeting long-term stays without daily rates

---

## 5. Confidence Intervals — Required Reporting

Every precision figure MUST be reported in this form:

```
precision = P [CI_lo, CI_hi] Wilson-95, n=N
vs accept-all baseline = B, Δ = +D pp, permutation p = p_val (k=1000)
```

**MINIMUM sample sizes** (from Brown et al. 2001 via §0.4):
- ±3pp precision → n ≥ 343 judged items
- ±5pp precision → n ≥ 124 judged items
- TREC floor → 50 topics minimum

---

## 6. Seeded Known-Negatives

The annotation pool MUST contain at least 10–20% seeded known-negatives drawn from
the list in `app/eval/mutations.py → SEEDED_NEGATIVES`. These are:
- Businesses that are clearly in the wrong category (e.g., petrol station for "degree college")
- Malformed inputs (empty name, SQL injection string)
- Categories not covered by the taxonomy

**FP rate threshold**: If any annotator accepts more than 20% of seeded negatives,
their labels for that session are flagged for review.

---

## 7. Recall Disclaimer (M5)

The Lincoln–Petersen estimator used for M5 recall is **biased upward** under
heterogeneous catchability. Report M5 as a LOWER BOUND with this exact caveat:

> "Recall M5 = 0.XX is a Lincoln–Petersen lower bound. It is systematically
> upward-biased under heterogeneous source coverage (unregistered businesses captured
> by neither source inflate N̂). True recall is no better than this figure; likely worse."

---

## 8. Annotator Sign-off

By labelling items, each annotator confirms they have read this rubric in full.

| Annotator | Role | Date | Signature |
|---|---|---|---|
| | | | |
| | | | |

**Rubric hash (SHA-256)**: `<compute before use>`
**Frozen at**: `<date>`
**Test set opened count**: 0 (increment on each opening)
