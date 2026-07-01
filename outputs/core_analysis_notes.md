# Core Analysis Notes - Lab 25

## M1 - Efficiency Audit

Findings:
- gpu-h100-4 is the strongest GPU-Util lie: GPU-Util = 98.2%, but MFU = 0.194 and MBU = 0.207.
- gpu-a10g-1 is also a util-lie: GPU-Util = 96.9%, but MFU = 0.268.
- gpu-h100-5 has 8 idle hours per day.
- H100 on-demand price = $2.50/hr, so idle waste = 8 * $2.50 = $20/day = $600/month.

Interpretation:
GPU-Util measures time-active utilization, not useful model efficiency. A GPU can appear busy while the model only uses a small fraction of available FLOPs. MFU and MBU are better signals for deciding whether to right-size, batch, optimize kernels, or move workloads to cheaper GPUs.

Recommended actions:
1. Kill idle GPUs first because it is immediate and low risk.
2. Investigate util-lie GPUs, especially gpu-h100-4, because H100 cost is high and MFU is only 19.4%.
3. Right-size inference or memory-bound workloads to cheaper GPUs when peak H100 capability is not needed.

## M2 - Inference Cost Levers

Findings:
- Total requests = 2,400.
- Total tokens = 7,533,027.
- Baseline cost = $48.87/day, equal to $6.488 per 1M tokens.
- Optimized cost = $8.48/day, equal to $1.126 per 1M tokens.
- Inference savings = 82.6%.

Interpretation:
The baseline assumes every request uses the large model with no cache and no batch discount. The optimized path combines three levers:
1. Cascade: simple requests are routed to a cheaper small model.
2. Prompt caching: repeated input tokens are charged at a discounted rate.
3. Batch API: non-real-time requests receive an additional batch discount.

Why this matters:
$/GPU-hour only tells how much we pay for infrastructure. $/1M-token tells how efficiently the platform converts infrastructure into useful model output. In this lab, optimized serving reduces unit cost from $6.488/1M-token to $1.126/1M-token.

Recommended actions:
1. Keep model cascading for easy requests because it has large ROI.
2. Use prompt caching for repeated system prompts and RAG prefixes.
3. Use batch mode only for offline/eval traffic, not latency-sensitive chat traffic.

## M3 - Purchasing Strategy

Findings:
- On-demand monthly cost = $25,667.
- Optimized monthly cost = $15,627.
- Purchasing savings = 39.1%.
- Spot tier jobs: job-train-llm, job-train-embed, job-finetune, job-dev-sandbox, job-batch-eval.
- Reserved tier jobs: job-infer-chat, job-infer-rag, job-infer-search.

Interpretation:
Spot is recommended for interruptible jobs because these workloads can tolerate preemption if checkpoint/resume is implemented. Reserved is recommended for stable high-duty workloads because a 45% reserved discount breaks even at about 55% utilization, or 13.2 hours/day.

Why effective spot hours can be higher:
Spot jobs include checkpoint overhead and expected rework after interruptions. Even with those extra effective hours, spot is still cheaper than on-demand for interruptible workloads.

Recommended actions:
1. Use spot for training, batch evaluation, and development jobs with checkpoint/resume.
2. Use reserved capacity for steady 24/7 inference services.
3. Keep on-demand for spiky, non-interruptible, low-duty workloads.
4. Test resume flow before running long spot training jobs.

## M4 - Cost Allocation and Chargeback

Findings:
- Cost by team per day:
  - assistant: $2.59/day
  - search: $2.49/day
  - eval: $1.79/day
  - rag: $1.60/day
- Tag coverage = 92%.
- Chargeback ready = True.
- FOCUS export generated at outputs/focus_export.csv.

Interpretation:
M4 turns a shared GPU/inference bill into accountability by team and project. This supports the FinOps maturity path from visibility to showback and then chargeback. Because tag coverage is 92%, the allocation data is reliable enough to charge costs back to teams.

Why tag coverage matters:
If too many rows are untagged, chargeback becomes unfair because the platform cannot confidently assign costs to owners. A threshold such as 80% prevents billing teams based on noisy or incomplete metadata.

Recommended actions:
1. Keep enforcing required tags: team and project.
2. Use showback dashboards first so teams can see their daily spend.
3. Move to chargeback only after tag coverage stays above 80%.
4. Investigate untagged traffic and add policy checks to block missing tags in production.

## M5 - Final Cost Optimization Report

Findings:
- Baseline monthly spend = $27,133.
- Optimized monthly spend = $14,626.
- Projected monthly savings = $12,507.
- Total savings rate = 46%.

Savings by lever:
- Purchasing (spot/reserved): $10,040/month.
- Inference (cascade/cache/batch): $1,212/month.
- Right-size util-lies: $655/month.
- Kill idle GPUs: $600/month.

Interpretation:
The largest savings lever is purchasing strategy, especially spot and reserved capacity. However, implementation priority should also consider engineering risk. Idle shutdown is the quickest low-risk win. Inference optimization directly improves $/1M-token. Purchasing optimization needs checkpoint/resume and capacity planning. Right-sizing util-lie GPUs needs benchmark validation before production rollout.

Recommended ROI priority:
1. Kill idle GPUs immediately.
2. Keep cascade/cache/batch for inference serving.
3. Move interruptible jobs to spot with tested checkpoint/resume.
4. Use reserved capacity for stable inference services.
5. Right-size util-lie GPUs after benchmarking latency and throughput.

Sustainability:
The report estimates 0.24 Wh/query and 0.091 gCO2e/query. The cleanest region is europe-north1. Region selection can reduce both carbon and electricity cost, but production rollout must also consider latency and data residency.
