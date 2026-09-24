# LeadCore Zero v2.1 — Relevance Engine Design Document

## 1. Design Diagnosis — Why the Legacy Filter Failed

During the validation testing of LeadCore Zero v2 on the query `pooja stores` in `Whitefield, Bengaluru`, the pipeline successfully ingested and persisted 18 leads. However, precision was severely degraded. The result set included unrelated businesses:
- **William Penn** (luxury pens / stationery chain)
- **Ximi Vogue** (Korean fast-fashion / lifestyle accessories)
- **Divine Footwear** (footwear retailer)
- **Archies** (greeting cards & gift merchandise)
- **Deepam Taxi** (cab / passenger transport service)

### Root Cause Analysis

1. **OR-of-weak-signals Logic**: The previous filter accepted any candidate if a single signal matched (`{category ∈ broad list} OR {name contains token}`). Precision was therefore bounded by the lowest-precision signal in the rule.
2. **Host Categories Treated as Defining Evidence**: Categories such as `gift_shop` and `general_store` are places where pooja supplies *may* occasionally be sold, but their presence is not evidence that the business *is* a pooja store. This allowed *Archies* and *William Penn* to pass.
3. **Ambiguous Tokens Treated as Positive Evidence**: Tokens such as `divine`, `deepam`, `sri`, `om`, `lakshmi`, and `ganesh` appear ubiquitous across Indian SMBs of every sector (footwear, transport, restaurants, salons). In isolation, they convey almost zero mutual information regarding business type. This caused *Divine Footwear* and *Deepam Taxi* to be accepted.
4. **Absence of Negative Evidence (Vetoes)**: Words like "Footwear", "Taxi", "Vogue", "Pens", or known non-pooja brands had no negative weight or veto power to reject candidates.
5. **Substring Matching Without Tokenization**: Raw regex substring matching matched tokens inside unrelated words and failed to handle transliteration variants (e.g., `pooja` / `puja` / `poojan`, `agarbatti` / `agarbathi`).
6. **Single Hard Threshold Without Abstention**: Without an uncertain / review band, borderline candidates with ambiguous scores were forced into the accept tier.

---

## 2. Governing Principles for v2.1

> **Governing Principle**: *Broad recall in candidate generation, strict evidence-based acceptance.*  
> Every accepted lead must carry **at least one defining positive signal** and **no unresolved veto**.

### Key Tenets
1. **Explainable Cascade (R0–R6)**:
   - Candidates are scored through a multi-stage funnel: Tokenization & Normalization (R0) → Hard Gating (R1) → Feature Extraction (R2) → Semantic Retrieval against positive/negative exemplars (R3) → Calibrated Evidence Scoring (R4) → Cross-Encoder Re-ranking (R5) → Small-LLM Adjudication with strict quote validation (R6).
2. **Deterministic Pre-Resolution Execution**: R0–R5 run on raw candidates *before* entity resolution to keep computation cost minimal. Cluster relevance is recomputed after N5 as the max evidence over members, with hard vetoes propagated unless overridden by a defining signal.
3. **Three Persisted Outcomes**:
   - `accepted`: High-confidence, passed defining signal criteria. Displayed in primary UI and default export.
   - `review`: Borderline or uncertain candidates. Displayed in dedicated Review tab; excluded from default exports.
   - `rejected`: Explicitly rejected with structured `reason_code` in `rejected_candidates` for recall auditability.
4. **Execution Cascade Budget**:
   - R0–R4 resolve $\ge 80\%$ of candidates using lightweight fast ONNX bi-encoders and deterministic rules.
   - R5 Cross-Encoder touches $\le 20\%$ of borderline candidates.
   - R6 Small LLM touches $\le 10\%$ of candidates.
   - Operates with 100% functionality and zero failures when `LLM_ENABLED=false` (uncertain leads flow into `review`).

---

## 3. Threshold Calibration & Acceptance Criteria

- High Threshold ($\tau_{hi} = 0.75$ calibrated via F0.5 grid search)
- Low Threshold ($\tau_{lo} = 0.35$)
- Structural Requirement: $f_{\text{def\_name}} + f_{\text{def\_cat}} + f_{\text{def\_osm}} + f_{\text{def\_web}} \ge 1$ required for `accepted` status from R4.
- Cross-Encoder Re-ranking ($f_{ce} \ge 0.8 \rightarrow \text{accepted}$, $f_{ce} \le 0.2 \rightarrow \text{rejected}$).
- Small LLM Adjudication: Requires literal substring evidence containing a defining or supporting term; otherwise relegated to `review`.
