# Lab 25 — GPU FinOps Cost Optimization Workshop

**Student:** Thái Thị Yến Nhi  
**Student ID:** 2A202600783  

This repository contains my completed implementation for **Lab 25 — GPU FinOps Workshop**.  
The lab simulates a GPU cost optimization project for **NimbusAI**, where the goal is to audit GPU efficiency, reduce inference cost, choose better purchasing tiers, allocate cost by team, and produce a final GPU FinOps report.

The final result is a monthly cost optimization report showing:

- Baseline spend: **$27,133/month**
- Optimized spend: **$14,586/month**
- Projected savings: **$12,547/month**
- Savings rate: **46%**
- Final validation: **11/11 verify checks passed**
- Pytest: **15 passed**

---

## Quick Grading Links

| Item | File |
|---|---|
| Final submission summary | [LAB25_SUBMISSION_SUMMARY.md](LAB25_SUBMISSION_SUMMARY.md) |
| Final cost report | [outputs/report.md](outputs/report.md) |
| Savings chart | [outputs/savings.png](outputs/savings.png) |
| Final full run log | [outputs/final_run_all.log](outputs/final_run_all.log) |
| Final verify log | [outputs/final_verify.log](outputs/final_verify.log) |
| Final pytest log | [outputs/final_pytest.log](outputs/final_pytest.log) |
| Core analysis notes | [outputs/core_analysis_notes.md](outputs/core_analysis_notes.md) |
| Extension summary | [outputs/extensions_summary.md](outputs/extensions_summary.md) |
| FOCUS-style cost export | [outputs/focus_export.csv](outputs/focus_export.csv) |

---

## Final Validation

The final validation logs are saved in:

- [outputs/final_verify.log](outputs/final_verify.log)
- [outputs/final_pytest.log](outputs/final_pytest.log)

Final verify result:

    LAB 25 VERIFY
    [PASS] M1 flags the GPU-Util lie (gpu-h100-4)
    [PASS] M1 detects idle waste
    [PASS] M2 $/1M-token drops after optimization
    [PASS] M2 inference savings in 60-95% band
    [PASS] M3 recommends a spot tier
    [PASS] M3 recommends a reserved tier
    [PASS] M3 purchasing saves money
    [PASS] M4 tag coverage 85-100%
    [PASS] M4 chargeback gate is open
    [PASS] M5 total savings in 40-95% band
    [PASS] M5 report.md written
    11/11 checks passed

Final pytest result:

    15 passed

---

## Final Cost Optimization Result

The final report is available here:

- [outputs/report.md](outputs/report.md)
- [outputs/savings.png](outputs/savings.png)

Final monthly result:

| Metric | Value |
|---|---:|
| Baseline spend | $27,133 |
| Optimized spend | $14,586 |
| Projected savings | $12,547 |
| Savings rate | 46% |

Savings by lever:

| Lever | Savings |
|---|---:|
| Purchasing strategy | $10,116/month |
| Inference optimization | $1,176/month |
| Right-size util-lies | $655/month |
| Kill idle GPUs | $600/month |

Excerpt from [outputs/report.md](outputs/report.md):

    # NimbusAI — GPU Cost Optimization Report

    Period: monthly
    Baseline spend: $27,133
    Optimized spend: $14,586
    Projected savings: $12,547  (46%)

    Savings by lever:
    - Inference (cascade/cache/batch): $1,176
    - Purchasing (spot/reserved): $10,116
    - Right-size util-lies: $655
    - Kill idle GPUs: $600

---

## What I Implemented

The original lab path has five core missions. I completed all five and added all five Your Turn extensions plus three bonus demos.

### Core Missions

| Mission | Topic | Main file | Evidence |
|---|---|---|---|
| M1 | GPU efficiency audit, MFU/MBU, GPU-Util lie | [missions/m1_efficiency_audit.py](missions/m1_efficiency_audit.py) | [outputs/final_run_all.log](outputs/final_run_all.log) |
| M2 | Inference cost levers, $/1M-token, cache, batch, cascade | [missions/m2_inference_levers.py](missions/m2_inference_levers.py) | [outputs/final_run_all.log](outputs/final_run_all.log) |
| M3 | Purchasing strategy, spot/reserved/on-demand | [missions/m3_purchasing.py](missions/m3_purchasing.py) | [outputs/final_run_all.log](outputs/final_run_all.log) |
| M4 | Cost allocation, tag coverage, FOCUS export | [missions/m4_allocation.py](missions/m4_allocation.py) | [outputs/focus_export.csv](outputs/focus_export.csv) |
| M5 | Final report and savings waterfall | [missions/m5_report.py](missions/m5_report.py) | [outputs/report.md](outputs/report.md), [outputs/savings.png](outputs/savings.png) |

---

## M1 — GPU Efficiency Audit

Source file:

- [missions/m1_efficiency_audit.py](missions/m1_efficiency_audit.py)

Evidence:

- [outputs/final_run_all.log](outputs/final_run_all.log)
- [outputs/core_analysis_notes.md](outputs/core_analysis_notes.md)

Key finding:

- `gpu-h100-4` has **98.2% GPU-Util** but only **0.194 MFU**
- `gpu-a10g-1` has **96.9% GPU-Util** but only **0.268 MFU**
- `gpu-h100-5` has 8 idle hours/day
- Idle waste = **$20/day = $600/month**

Excerpt:

    GPU-Util LIES (util>=90% but MFU<30%): ['gpu-h100-4', 'gpu-a10g-1']
    Idle waste (1 day): $20.00  ->  $600/month

Interpretation:

GPU-Util alone is misleading because it measures time-active utilization, not useful model efficiency. MFU and MBU are better for deciding whether to right-size, optimize kernels, improve batching, or move workloads to cheaper GPUs.

---

## M2 — Inference Cost Levers

Source file:

- [missions/m2_inference_levers.py](missions/m2_inference_levers.py)

Evidence:

- [outputs/final_run_all.log](outputs/final_run_all.log)
- [outputs/ext3_cache_economics.csv](outputs/ext3_cache_economics.csv)
- [outputs/ext4_reasoning_budget.csv](outputs/ext4_reasoning_budget.csv)

Final result:

| Metric | Value |
|---|---:|
| Requests | 2,400 |
| Total tokens | 7,533,027 |
| Baseline unit cost | $6.488 / 1M tokens |
| Optimized unit cost | $1.282 / 1M tokens |
| Savings | 80.2% |

Excerpt:

    == M2 Inference Cost Levers ==
    requests=2400  tokens=7,533,027
    baseline  : $48.87/day   $6.488/1M-token
    optimized : $9.66/day    $1.282/1M-token
    savings   : 80.2%

Implementation details:

- Model cascade: simple requests route to cheaper model tier.
- Batch discount: offline requests use batch pricing.
- Cache economics: prompt cache is only applied when measured reuse exceeds break-even reads.
- Reasoning budget: reasoning traffic is tracked separately for cost and energy.

---

## M3 — Purchasing Strategy

Source files:

- [finops/pricing.py](finops/pricing.py)
- [missions/m3_purchasing.py](missions/m3_purchasing.py)

Evidence:

- [outputs/final_run_all.log](outputs/final_run_all.log)
- [outputs/ext1_purchasing_policy.log](outputs/ext1_purchasing_policy.log)

Final result:

| Metric | Value |
|---|---:|
| On-demand monthly cost | $25,667 |
| Optimized monthly cost | $15,551 |
| Savings | 39.4% |

Excerpt:

    == M3 Purchasing Strategy ==
    break-even utilization @ 45% reserved discount = 55%
    Extension 1: tier policy uses GPU-specific spot interruption rates and reserved 1yr/3yr duration comparison.

    job-train-llm      H100   spot       spot@3%intr
    job-infer-chat     A10G   reserved   reserved_3yr/36mo
    job-infer-rag      A100   reserved   reserved_3yr/36mo
    job-infer-search   L4     reserved   reserved_3yr/36mo

    monthly: on-demand $25,667 -> optimized $15,551  (39.4% saved)

Implementation details:

- Spot is used for interruptible jobs.
- Reserved capacity is used for stable inference workloads.
- The tier policy includes GPU-specific interruption rates.
- The reserved policy compares 1-year vs 3-year commitment assumptions.

---

## M4 — Cost Allocation and Chargeback

Source files:

- [finops/allocation.py](finops/allocation.py)
- [missions/m4_allocation.py](missions/m4_allocation.py)

Evidence:

- [outputs/focus_export.csv](outputs/focus_export.csv)
- [outputs/final_run_all.log](outputs/final_run_all.log)

Final result:

| Team | Daily cost |
|---|---:|
| assistant | $2.59 |
| search | $2.49 |
| eval | $1.79 |
| rag | $1.60 |

Tag coverage:

    92%

Chargeback status:

    True

Excerpt:

    == M4 Cost Allocation ==
    cost by team ($/day):
      assistant    $    2.59
      search       $    2.49
      eval         $    1.79
      rag          $    1.60
    tag coverage: 92%  ->  chargeback ready? True
    FOCUS export -> outputs/focus_export.csv (50 rows)

Interpretation:

Tag coverage is above the 80% threshold, so the platform can move from showback to chargeback. The FOCUS-style export makes the cost allocation portable and easier to review.

---

## M5 — Final Optimization Report

Source files:

- [finops/report.py](finops/report.py)
- [missions/m5_report.py](missions/m5_report.py)

Evidence:

- [outputs/report.md](outputs/report.md)
- [outputs/savings.png](outputs/savings.png)
- [outputs/final_run_all.log](outputs/final_run_all.log)

Final report summary:

| Metric | Value |
|---|---:|
| Baseline spend | $27,133 |
| Optimized spend | $14,586 |
| Projected savings | $12,547 |
| Savings rate | 46% |

Sustainability metrics:

| Metric | Value |
|---|---:|
| Energy per query | 0.24 Wh |
| Carbon per query | 0.091 gCO2e |
| Cheapest + cleanest region | europe-north1 |

---

# Your Turn Extensions

I implemented all **5/5 Your Turn extensions**. Full extension summary:

- [outputs/extensions_summary.md](outputs/extensions_summary.md)

---

## Extension 1 — Improved Purchasing Tier Policy

Source files:

- [finops/pricing.py](finops/pricing.py)
- [missions/m3_purchasing.py](missions/m3_purchasing.py)

Evidence:

- [outputs/ext1_purchasing_policy.log](outputs/ext1_purchasing_policy.log)

What changed:

- Added GPU-specific spot interruption rates.
- Added reserved 1-year vs 3-year duration comparison.
- Kept the original API backward compatible.

Result:

    On-demand monthly cost: $25,667
    Optimized monthly cost: $15,551
    Purchasing savings: 39.4%

Key insight:

Spot is useful only when the job is interruptible and checkpoint/resume is available. Reserved capacity is best for stable, long-lived inference workloads.

---

## Extension 2 — MBU-aware Right-sizing

Source file:

- [missions/m1_efficiency_audit.py](missions/m1_efficiency_audit.py)

Evidence:

- [outputs/ext2_rightsizing_mbu.log](outputs/ext2_rightsizing_mbu.log)
- [outputs/ext2_rightsizing_mbu.csv](outputs/ext2_rightsizing_mbu.csv)

What changed:

- Added `$ / GB-VRAM`.
- Added MBU-aware right-sizing.
- Added VRAM and bandwidth headroom checks.

Result:

| GPU | Current GPU | Recommended GPU | Monthly savings |
|---|---|---|---:|
| gpu-a10g-0 | A10G | L4 | $144 |
| gpu-a10g-1 | A10G | L4 | $144 |

Total right-sizing savings:

    $288/month

Excerpt:

    Extension 2: MBU-aware right-sizing recommendations
    gpu-a10g-0    A10G     L4     savings/mo $144
    gpu-a10g-1    A10G     L4     savings/mo $144
    Right-sizing monthly savings: $288

Key insight:

The cheaper GPU is only recommended when it still satisfies observed VRAM and bandwidth requirements. A100 inference workloads were not forced onto 24GB GPUs because they used around 67GB VRAM.

---

## Extension 3 — Cache Economics

Source files:

- [finops/pricing.py](finops/pricing.py)
- [missions/m2_inference_levers.py](missions/m2_inference_levers.py)

Evidence:

- [outputs/ext3_cache_economics.log](outputs/ext3_cache_economics.log)
- [outputs/ext3_cache_economics.csv](outputs/ext3_cache_economics.csv)

What changed:

- Added `cache_break_even_reads()`.
- Added `cache_is_worth_it()`.
- M2 now applies cache only when it is economically justified.

Result:

| Tier | Avg cache reads | Break-even reads | Use cache |
|---|---:|---:|---|
| large | 0.467 | 1.389 | False |
| small | 0.468 | 1.389 | False |

Excerpt:

    Extension 3: cache economics
    tier       avg_reads    break_even   use_cache
    large          0.467         1.389       False
    small          0.468         1.389       False
    cache tokens used: 0; skipped: 1,703,990

Key insight:

Prompt caching should not be blindly counted as savings. In this dataset, average reads are below break-even, so cache savings are not applied.

---

## Extension 4 — Reasoning Budget

Source file:

- [missions/m2_inference_levers.py](missions/m2_inference_levers.py)

Evidence:

- [outputs/ext4_reasoning_budget.log](outputs/ext4_reasoning_budget.log)
- [outputs/ext4_reasoning_budget.csv](outputs/ext4_reasoning_budget.csv)

What changed:

- Split cost by reasoning vs non-reasoning traffic.
- Split energy by reasoning vs non-reasoning traffic.
- Simulated a 10% reasoning traffic cap.

Result:

| Metric | Value |
|---|---:|
| Reasoning traffic | 201 / 2400 requests = 8.4% |
| Reasoning cost share | 14.6% |
| Reasoning energy share | 94.0% |
| Excess over 10% cap | 0 requests |

Excerpt:

    Extension 4: reasoning budget
    reasoning traffic: 201/2400 (8.4% requests)
    reasoning cost share: 14.6%
    reasoning energy share: 94.0%
    cap reasoning at 10% -> excess requests=0

Key insight:

Reasoning traffic is small by request count but dominates energy. It should be gated by task difficulty, confidence, or explicit user need.

---

## Extension 5 — Carbon-aware Scheduling

Source file:

- [missions/ext5_carbon_aware.py](missions/ext5_carbon_aware.py)

Evidence:

- [outputs/ext5_carbon_aware.log](outputs/ext5_carbon_aware.log)
- [outputs/ext5_carbon_by_job.csv](outputs/ext5_carbon_by_job.csv)
- [outputs/ext5_carbon_regions.csv](outputs/ext5_carbon_regions.csv)
- [outputs/final_ext5_carbon_aware.log](outputs/final_ext5_carbon_aware.log)

What changed:

- Added region-level electricity and carbon comparison.
- Analyzed interruptible jobs only.
- Generated per-job and per-region CSV evidence.

Result:

| Metric | Value |
|---|---:|
| Interruptible jobs analyzed | 5 |
| Cheapest region | us-east-wa |
| Cleanest region | europe-north1 |
| Balanced region | us-east-wa |
| Carbon saved by moving to cleanest region | 626,150 gCO2e |
| Carbon reduction | 92.1% |

Excerpt:

    == Extension 5: Carbon-aware Scheduling ==
    interruptible jobs: 5
    baseline region: us-east-1
    cheapest region: us-east-wa ($98.39)
    cleanest region: europe-north1 (53670.00 gCO2e)
    balanced region: us-east-wa (score=0.0476)
    carbon saved by moving interruptible jobs to cleanest region: 626150.00 gCO2e (92.1%)

Key insight:

The best region depends on business priority. `us-east-wa` is best for balanced cost and carbon, while `europe-north1` is best for pure carbon reduction. This should be applied first to interruptible or offline jobs because clean regions may add latency or data-residency constraints.

---

# Bonus Work Completed

I also completed all three bonus demos.

---

## Bonus 1 — LiteLLM-style Token Cost Tracker

Source files:

- [bonus/litellm_tracker/demo.py](bonus/litellm_tracker/demo.py)
- [bonus/litellm_tracker/tracker.py](bonus/litellm_tracker/tracker.py)

Evidence:

- [outputs/bonus_litellm_tracker.log](outputs/bonus_litellm_tracker.log)

Result:

    BLOCKED after 10 chat requests: key=team-chat would spend $0.0507 > cap $0.05

    per-key spend: {'team-chat': 0.046, 'team-eval': 0.0003}
    requests logged: 15

Key insight:

This demonstrates per-team spend tracking and a hard budget cap.

---

## Bonus 2 — Local Model Cost Comparison

Source file:

- [bonus/local_model/run_local.py](bonus/local_model/run_local.py)

Evidence:

- [outputs/bonus_local_model.log](outputs/bonus_local_model.log)

Result:

    model=sshleifer/tiny-gpt2  new_tokens=64  time=0.23s
    REAL throughput: 276.1 tok/s on CPU
    REAL ~$0.10/1M-token  (vs sim small-model ~$0.30/1M-token)
    Takeaway: tok/s and utilization drive $/token far more than the sticker $/hr.

Key insight:

Local inference can be cost-effective when throughput is high. The real FinOps metric is `$ / token`, not only hardware price per hour.

---

## Bonus 3 — Prometheus and Grafana Dashboard

Source files:

- [bonus/docker/exporter.py](bonus/docker/exporter.py)
- [bonus/docker/docker-compose.yml](bonus/docker/docker-compose.yml)
- [bonus/docker/README.md](bonus/docker/README.md)

Evidence:

- [outputs/bonus_docker_metrics.log](outputs/bonus_docker_metrics.log)

Runtime services after `docker compose up -d`:

| Service | URL |
|---|---|
| Exporter metrics | http://localhost:9101/metrics |
| Prometheus | http://localhost:9090 |
| Grafana | http://localhost:3000 |

Result:

- Docker Compose started exporter, Prometheus, and Grafana.
- Exporter exposes GPU FinOps metrics.
- Metrics include GPU-Util, MFU, hourly cost, and wasted cost.

Key metric example:

    gpu_util_pct{gpu_id="gpu-h100-4",gpu_type="H100"} 98.16
    gpu_mfu{gpu_id="gpu-h100-4",gpu_type="H100"} 0.1943
    gpu_wasted_cost_usd_per_hr{gpu_id="gpu-h100-4",gpu_type="H100"} 2.0143

Key insight:

`gpu-h100-4` looks highly utilized by GPU-Util, but it wastes about `$2.0143/hr` because MFU is only `0.1943`.

---

# How to Reproduce

Create the virtual environment and install dependencies:

    python -m venv .venv
    .venv\Scripts\activate
    pip install -r requirements.txt

Generate deterministic synthetic data:

    python data/generate.py

Run the full lab:

    python missions/run_all.py

Run final validation:

    python verify.py
    pytest -q

Run all extension and bonus evidence:

    python missions/ext5_carbon_aware.py

    cd bonus\litellm_tracker
    python demo.py
    cd ..\..

    cd bonus\local_model
    python run_local.py
    cd ..\..

    cd bonus\docker
    docker compose up -d
    cd ..\..

---

# Project Structure

| Path | Purpose |
|---|---|
| [data/generate.py](data/generate.py) | Deterministic synthetic data generator |
| [data/price_catalog.csv](data/price_catalog.csv) | GPU price and hardware catalog |
| [data/gpu_telemetry.csv](data/gpu_telemetry.csv) | 24-hour telemetry for 11 GPUs |
| [data/token_usage.csv](data/token_usage.csv) | 2,400 LLM requests |
| [data/workloads.csv](data/workloads.csv) | Training/inference workload definitions |
| [finops/metrics.py](finops/metrics.py) | MFU, MBU, GPU-Util lie detection |
| [finops/pricing.py](finops/pricing.py) | Request cost, cache economics, purchasing tier policy |
| [finops/allocation.py](finops/allocation.py) | Tag-based cost allocation and chargeback gate |
| [finops/sustainability.py](finops/sustainability.py) | Energy, carbon, and region modeling |
| [finops/report.py](finops/report.py) | Markdown report and savings waterfall |
| [missions/m1_efficiency_audit.py](missions/m1_efficiency_audit.py) | M1 efficiency audit and right-sizing extension |
| [missions/m2_inference_levers.py](missions/m2_inference_levers.py) | M2 inference optimization, cache economics, reasoning budget |
| [missions/m3_purchasing.py](missions/m3_purchasing.py) | M3 purchasing strategy extension |
| [missions/m4_allocation.py](missions/m4_allocation.py) | M4 cost allocation |
| [missions/m5_report.py](missions/m5_report.py) | M5 final report |
| [missions/ext5_carbon_aware.py](missions/ext5_carbon_aware.py) | Extension 5 carbon-aware scheduling |
| [bonus/litellm_tracker/](bonus/litellm_tracker/) | Bonus API-key cost tracker |
| [bonus/local_model/](bonus/local_model/) | Bonus local model cost comparison |
| [bonus/docker/](bonus/docker/) | Bonus Prometheus/Grafana dashboard |
| [outputs/](outputs/) | Generated evidence files |

---

# Notes

- The lab runs without a GPU, cloud account, or API key.
- Docker is only required for the optional Prometheus/Grafana bonus.
- The synthetic data is deterministic with seed 25.
- Prices are lab snapshots and should be re-baselined before real-world use.
- The main FinOps lesson is to optimize by `$ / token`, MFU/MBU, and workload behavior rather than by GPU-Util or sticker `$ / GPU-hour`.
