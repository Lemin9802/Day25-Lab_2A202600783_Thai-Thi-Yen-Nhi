# Lab 25 Submission Summary - GPU FinOps Workshop

**Student:** Thái Thị Yến Nhi  
**Student ID:** 2A202600783  

---

## 1. Core Lab Result

### Final validation

- [`outputs/final_verify.log`](outputs/final_verify.log): `python verify.py` -> **11/11 checks passed**
- [`outputs/final_pytest.log`](outputs/final_pytest.log): `pytest -q` -> **15 passed**
- [`outputs/final_run_all.log`](outputs/final_run_all.log): final M1-M5 pipeline run

### Final report files

- [`outputs/report.md`](outputs/report.md): final GPU cost optimization report
- [`outputs/savings.png`](outputs/savings.png): savings waterfall chart
- [`outputs/focus_export.csv`](outputs/focus_export.csv): FOCUS-style cost allocation export
- [`outputs/core_analysis_notes.md`](outputs/core_analysis_notes.md): M1-M5 analysis notes

### Final monthly result

- **Baseline spend:** `$27,133`
- **Optimized spend:** `$14,586`
- **Projected savings:** `$12,547`
- **Savings rate:** `46%`

### Savings by lever

| Lever | Monthly savings |
|---|---:|
| Inference optimization | `$1,176` |
| Purchasing strategy | `$10,116` |
| Right-size util-lies | `$655` |
| Kill idle GPUs | `$600` |

### Core findings

- **M1:** GPU-Util lies found on `gpu-h100-4` and `gpu-a10g-1`; idle waste = `$600/month`.
- **M2:** `$ / 1M-token` drops from `$6.488` to `$1.282` after cascade/cache/batch policy.
- **M3:** On-demand `$25,667/month` -> optimized `$15,551/month` with spot/reserved policy.
- **M4:** Tag coverage = `92%`, chargeback gate open.
- **M5:** Final report written with savings waterfall and sustainability metrics.

---

## 2. Your Turn Extensions Implemented

All **5/5 Your Turn extensions** were implemented.

Full summary:
- [`outputs/extensions_summary.md`](outputs/extensions_summary.md)

---

## Extension 1 - Improved Purchasing Tier Policy

### Files changed

- [`finops/pricing.py`](finops/pricing.py)
- [`missions/m3_purchasing.py`](missions/m3_purchasing.py)

### Evidence

- [`outputs/ext1_purchasing_policy.log`](outputs/ext1_purchasing_policy.log)

### What changed

- Added GPU-specific spot interruption rates.
- Added reserved 1yr vs 3yr duration comparison.
- Kept the original `recommend_tier()` API backward compatible so existing tests still pass.

### Measured result

- On-demand monthly cost: `$25,667`
- Optimized monthly cost: `$15,551`
- Purchasing savings: `39.4%`

### Key insight

Spot is best for interruptible jobs only when interruption risk is acceptable and checkpoint/resume is available. Reserved capacity is best for stable long-lived inference workloads.

---

## Extension 2 - MBU-aware Right-sizing

### File changed

- [`missions/m1_efficiency_audit.py`](missions/m1_efficiency_audit.py)

### Evidence

- [`outputs/ext2_rightsizing_mbu.log`](outputs/ext2_rightsizing_mbu.log)
- [`outputs/ext2_rightsizing_mbu.csv`](outputs/ext2_rightsizing_mbu.csv)

### What changed

- Added `$ / GB-VRAM` calculation.
- Added MBU-aware right-sizing for inference/embed GPUs.
- Added VRAM and bandwidth headroom checks before recommending a cheaper GPU.

### Measured result

| GPU | Current | Recommended | Monthly savings |
|---|---|---|---:|
| `gpu-a10g-0` | A10G | L4 | `$144` |
| `gpu-a10g-1` | A10G | L4 | `$144` |

Total right-sizing savings: **`$288/month`**

### Key insight

Right-sizing should not simply choose the cheapest GPU by `$ / GPU-hour`. The replacement GPU must still satisfy observed VRAM and bandwidth needs.

---

## Extension 3 - Cache Economics

### Files changed

- [`finops/pricing.py`](finops/pricing.py)
- [`missions/m2_inference_levers.py`](missions/m2_inference_levers.py)

### Evidence

- [`outputs/ext3_cache_economics.log`](outputs/ext3_cache_economics.log)
- [`outputs/ext3_cache_economics.csv`](outputs/ext3_cache_economics.csv)

### What changed

- Added `cache_break_even_reads()`.
- Added `cache_is_worth_it()`.
- M2 now applies prompt cache only when observed reuse exceeds break-even reads.

### Measured result

| Tier | Avg cache reads | Break-even reads | Use cache |
|---|---:|---:|---|
| large | `0.467` | `1.389` | False |
| small | `0.468` | `1.389` | False |

Optimized unit cost remains strong:

    $6.488 -> $1.282 per 1M tokens

Savings: **`80.2%`**

### Key insight

Prompt caching should not be assumed to save money. It only pays off when repeated reads are high enough to cover the write/setup cost.

---

## Extension 4 - Reasoning Budget

### File changed

- [`missions/m2_inference_levers.py`](missions/m2_inference_levers.py)

### Evidence

- [`outputs/ext4_reasoning_budget.log`](outputs/ext4_reasoning_budget.log)
- [`outputs/ext4_reasoning_budget.csv`](outputs/ext4_reasoning_budget.csv)

### What changed

- Added reasoning vs non-reasoning cost split.
- Added reasoning vs non-reasoning energy split.
- Simulated a policy cap of 10% reasoning traffic.

### Measured result

- Reasoning traffic: `201 / 2,400 requests = 8.4%`
- Reasoning cost share: `14.6%`
- Reasoning energy share: `94.0%`
- 10% reasoning cap causes no extra savings because current reasoning traffic is already below cap.

### Key insight

Reasoning traffic is small by request count but dominates energy. It should be gated by task complexity, confidence, or explicit user need.

---

## Extension 5 - Carbon-aware Scheduling

### File added

- [`missions/ext5_carbon_aware.py`](missions/ext5_carbon_aware.py)

### Evidence

- [`outputs/ext5_carbon_aware.log`](outputs/ext5_carbon_aware.log)
- [`outputs/ext5_carbon_by_job.csv`](outputs/ext5_carbon_by_job.csv)
- [`outputs/ext5_carbon_regions.csv`](outputs/ext5_carbon_regions.csv)
- [`outputs/final_ext5_carbon_aware.log`](outputs/final_ext5_carbon_aware.log)

### What changed

- Added region-level carbon and electricity comparison for interruptible jobs.
- Compared baseline `us-east-1` against all regions in the sustainability module.
- Generated per-job and per-region CSV exports.

### Measured result

- Interruptible jobs analyzed: `5`
- Cheapest region: `us-east-wa`, electricity cost = `$98.39`
- Cleanest region: `europe-north1`, carbon = `53,670 gCO2e`
- Balanced region: `us-east-wa`, score = `0.0476`
- Moving interruptible jobs from `us-east-1` to `europe-north1` saves `626,150 gCO2e`, or `92.1%`.

### Key insight

The best region depends on business priority. `us-east-wa` is best for balanced cost+carbon, while `europe-north1` is best for pure carbon reduction. Use this mainly for interruptible/offline jobs because clean regions may add latency or data-residency constraints.

---

## 3. Bonus Work Completed

All bonus demos were attempted, and all three ran successfully after installing local model dependencies.

---

## Bonus 1 - LiteLLM-style Token Cost Tracker

### Source files

- [`bonus/litellm_tracker/demo.py`](bonus/litellm_tracker/demo.py)
- [`bonus/litellm_tracker/tracker.py`](bonus/litellm_tracker/tracker.py)

### Evidence

- [`outputs/bonus_litellm_tracker.log`](outputs/bonus_litellm_tracker.log)

### Result

- `team-chat` blocked when next request would exceed `$0.05` cap.
- Final spend:
  - `team-chat = $0.046`
  - `team-eval = $0.0003`
- Requests logged: `15`

### Key insight

The tracker shows team-level API spend visibility and budget hard-stop behavior.

---

## Bonus 2 - Local Model Cost Comparison

### Source files

- [`bonus/local_model/run_local.py`](bonus/local_model/run_local.py)

### Evidence

- [`outputs/bonus_local_model.log`](outputs/bonus_local_model.log)

### Result

- Model: `sshleifer/tiny-gpt2`
- New tokens: `64`
- Time: `0.23s`
- CPU throughput: `276.1 tok/s`
- Estimated real cost: `~$0.10/1M-token`
- Comparison: simulated small-model cost was `~$0.30/1M-token`

### Key insight

Token throughput and utilization drive `$ / token` more than the sticker `$ / hour`.

---

## Bonus 3 - Prometheus/Grafana Dashboard

### Source files

- [`bonus/docker/exporter.py`](bonus/docker/exporter.py)
- [`bonus/docker/docker-compose.yml`](bonus/docker/docker-compose.yml)
- [`bonus/docker/README.md`](bonus/docker/README.md)

### Evidence

- [`outputs/bonus_docker_metrics.log`](outputs/bonus_docker_metrics.log)

### Runtime dashboard URLs

These are local runtime URLs when Docker Compose is running:

- Prometheus: http://localhost:9090
- Grafana: http://localhost:3000
- Exporter metrics: http://localhost:9101/metrics

### Result

- Docker Compose launched exporter, Prometheus, and Grafana.
- Exporter exposed GPU FinOps metrics on port `9101`.
- Prometheus available on port `9090`.
- Grafana available on port `3000`.

### Key metric example

From [`outputs/bonus_docker_metrics.log`](outputs/bonus_docker_metrics.log):

    gpu_util_pct{gpu_id="gpu-h100-4",gpu_type="H100"} 98.16
    gpu_mfu{gpu_id="gpu-h100-4",gpu_type="H100"} 0.1943
    gpu_wasted_cost_usd_per_hr{gpu_id="gpu-h100-4",gpu_type="H100"} 2.0143

This shows why GPU-Util alone is misleading.

---

## 4. Final Validation Evidence

| Check | Evidence file | Result |
|---|---|---|
| `python verify.py` | [`outputs/final_verify.log`](outputs/final_verify.log) | 11/11 passed |
| `pytest -q` | [`outputs/final_pytest.log`](outputs/final_pytest.log) | 15 passed |
| Full M1-M5 run | [`outputs/final_run_all.log`](outputs/final_run_all.log) | Completed |
| Final report | [`outputs/report.md`](outputs/report.md) | Written |
| Savings chart | [`outputs/savings.png`](outputs/savings.png) | Written |
| Extension summary | [`outputs/extensions_summary.md`](outputs/extensions_summary.md) | Written |

---

## 5. Final Notes

The implementation preserves the original lab grading path:

- Core verify still passes.
- Pytest still passes.
- Extensions are additive and documented.
- Bonus outputs are saved as evidence.
- All important evidence files are linked in this summary for easier grading.
