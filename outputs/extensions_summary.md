# Lab 25 - Your Turn Extensions Summary

Student: Thai Thi Yen Nhi  
Student ID: 2A202600783  

This file summarizes all five Your Turn extensions implemented for Lab 25.

---

## Extension 1 - Improved Purchasing Tier Policy

Files changed:
- `finops/pricing.py`
- `missions/m3_purchasing.py`

What changed:
- Added GPU-specific spot interruption rates.
- Added reserved 1yr vs 3yr duration comparison.
- Kept the original `recommend_tier()` API backward compatible so existing tests still pass.

Measured result:
- On-demand monthly cost: $25,667
- Optimized monthly cost: $15,551
- Purchasing savings: 39.4%

Key insight:
Spot is best for interruptible jobs only when interruption risk is acceptable and checkpoint/resume is available. Reserved capacity is best for stable long-lived inference workloads.

Evidence:
- `outputs/ext1_purchasing_policy.log`

---

## Extension 2 - MBU-aware Right-sizing

Files changed:
- `missions/m1_efficiency_audit.py`

What changed:
- Added `$ / GB-VRAM` calculation.
- Added MBU-aware right-sizing for inference/embed GPUs.
- Added VRAM and bandwidth headroom checks before recommending a cheaper GPU.

Measured result:
- `gpu-a10g-0`: A10G -> L4, saves $144/month.
- `gpu-a10g-1`: A10G -> L4, saves $144/month.
- Total right-sizing savings: $288/month.

Key insight:
Right-sizing should not simply choose the cheapest GPU by `$ / GPU-hour`. The replacement GPU must still satisfy observed VRAM and bandwidth needs.

Evidence:
- `outputs/ext2_rightsizing_mbu.log`
- `outputs/ext2_rightsizing_mbu.csv`

---

## Extension 3 - Cache Economics

Files changed:
- `finops/pricing.py`
- `missions/m2_inference_levers.py`

What changed:
- Added `cache_break_even_reads()`.
- Added `cache_is_worth_it()`.
- M2 now applies prompt cache only when observed reuse exceeds break-even reads.

Measured result:
- Large tier: avg cache reads = 0.467, break-even = 1.389, use_cache = False.
- Small tier: avg cache reads = 0.468, break-even = 1.389, use_cache = False.
- Optimized unit cost remains strong: $6.488 -> $1.282 per 1M tokens.
- Savings: 80.2%.

Key insight:
Prompt caching should not be assumed to save money. It only pays off when repeated reads are high enough to cover the write/setup cost.

Evidence:
- `outputs/ext3_cache_economics.log`
- `outputs/ext3_cache_economics.csv`

---

## Extension 4 - Reasoning Budget

Files changed:
- `missions/m2_inference_levers.py`

What changed:
- Added reasoning vs non-reasoning cost split.
- Added reasoning vs non-reasoning energy split.
- Simulated a policy cap of 10% reasoning traffic.

Measured result:
- Reasoning traffic: 201 / 2,400 requests = 8.4%.
- Reasoning cost share: 14.6%.
- Reasoning energy share: 94.0%.
- Cap at 10% creates no extra savings in this dataset because current reasoning traffic is already below cap.

Key insight:
Reasoning traffic is small by request count but dominates energy. It should be gated by task complexity, confidence, or explicit user need.

Evidence:
- `outputs/ext4_reasoning_budget.log`
- `outputs/ext4_reasoning_budget.csv`

---

## Extension 5 - Carbon-aware Scheduling

Files added:
- `missions/ext5_carbon_aware.py`

What changed:
- Added region-level carbon and electricity comparison for interruptible jobs.
- Compared baseline `us-east-1` against all regions in the sustainability module.
- Generated per-job and per-region CSV exports.

Measured result:
- Interruptible jobs analyzed: 5.
- Cheapest region: `us-east-wa`, electricity cost = $98.39.
- Cleanest region: `europe-north1`, carbon = 53,670 gCO2e.
- Balanced region: `us-east-wa`, score = 0.0476.
- Moving interruptible jobs from `us-east-1` to `europe-north1` saves 626,150 gCO2e, a 92.1% reduction.

Key insight:
The best region depends on business priority. `us-east-wa` is best for balanced cost+carbon, while `europe-north1` is best for pure carbon reduction. Use this mainly for interruptible/offline jobs because clean regions may add latency or data-residency constraints.

Evidence:
- `outputs/ext5_carbon_aware.log`
- `outputs/ext5_carbon_by_job.csv`
- `outputs/ext5_carbon_regions.csv`

---

## Final Validation

Current validation status after all extensions:
- `python verify.py`: 11/11 checks passed.
- `pytest -q`: 15 passed.

The extensions are additive and preserve the original lab grading path.
