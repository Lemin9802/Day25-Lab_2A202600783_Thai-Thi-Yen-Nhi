"""M1 - Efficiency Audit: MFU/MBU, the GPU-Util lie, idle waste, and MBU right-sizing.

Extension 2 adds:
- $/GB-VRAM for each GPU type.
- MBU-aware right-sizing recommendations for inference/embed GPUs.
- outputs/ext2_rightsizing_mbu.csv with current vs recommended GPU and savings.
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from collections import defaultdict
import csv
import os
from missions._common import load_csv, num, catalog_by_type, ROOT
from finops import metrics


def dollars_per_gb_vram(catalog_row: dict) -> float:
    """On-demand hourly dollars per GB of VRAM."""
    hbm = num(catalog_row.get("hbm_gb"))
    if hbm <= 0:
        return 0.0
    return num(catalog_row.get("on_demand_hr")) / hbm


def recommend_gpu_for_observed_usage(summary_row: dict, catalog: dict) -> dict | None:
    """Find a cheaper GPU that satisfies observed memory and bandwidth needs.

    This is intentionally based on observed telemetry, not model name alone:
    - VRAM requirement: 20% headroom above max observed memory.
    - Bandwidth requirement: 20% headroom above average observed bandwidth.
    - Candidate must be cheaper than the current GPU.
    """
    current_type = summary_row["gpu_type"]
    current = catalog[current_type]
    current_price = num(current["on_demand_hr"])

    mem_required = max(1.0, summary_row.get("max_mem_used_gb", 0.0) * 1.10)
    bw_required = max(0.01, summary_row.get("avg_bw_tbs", 0.0) * 1.20)

    candidates = []
    for gpu_type, row in catalog.items():
        price = num(row["on_demand_hr"])
        hbm = num(row["hbm_gb"])
        peak_bw = num(row["peak_bw_tbs"])
        if price < current_price and hbm >= mem_required and peak_bw >= bw_required:
            candidates.append({
                "gpu_type": gpu_type,
                "on_demand_hr": price,
                "hbm_gb": hbm,
                "peak_bw_tbs": peak_bw,
                "usd_per_gb_vram": dollars_per_gb_vram(row),
            })

    if not candidates:
        return None

    candidates.sort(key=lambda x: (x["on_demand_hr"], x["usd_per_gb_vram"]))
    best = candidates[0]
    monthly_savings = (current_price - best["on_demand_hr"]) * 24 * 30
    return {
        "gpu_id": summary_row["gpu_id"],
        "workload": summary_row.get("workload", ""),
        "current_gpu": current_type,
        "recommended_gpu": best["gpu_type"],
        "current_hr": round(current_price, 2),
        "recommended_hr": round(best["on_demand_hr"], 2),
        "current_usd_per_gb_vram": round(dollars_per_gb_vram(current), 4),
        "recommended_usd_per_gb_vram": round(best["usd_per_gb_vram"], 4),
        "max_mem_used_gb": round(summary_row.get("max_mem_used_gb", 0.0), 1),
        "avg_bw_tbs": round(summary_row.get("avg_bw_tbs", 0.0), 3),
        "monthly_savings": round(monthly_savings),
        "reason": "Observed inference/embed usage fits cheaper GPU with VRAM and bandwidth headroom",
    }


def rightsize_by_mbu(summary: list[dict], catalog: dict) -> list[dict]:
    """Recommend right-sizing for under-efficient inference/embed GPUs.

    We target inference/embed because decode and serving are often memory-bound,
    and because over-provisioning expensive GPUs for small models is a common
    FinOps leak.
    """
    recs = []
    for s in summary:
        workload = s.get("workload", "")
        if workload not in ("infer", "embed"):
            continue

        low_efficiency = s["mfu"] < 0.35 or s["mbu"] < 0.35
        if not low_efficiency:
            continue

        rec = recommend_gpu_for_observed_usage(s, catalog)
        if rec:
            recs.append(rec)
    return recs


def write_rightsizing_csv(recs: list[dict]) -> str:
    out_path = os.path.join(ROOT, "outputs", "ext2_rightsizing_mbu.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    fields = [
        "gpu_id", "workload", "current_gpu", "recommended_gpu",
        "current_hr", "recommended_hr",
        "current_usd_per_gb_vram", "recommended_usd_per_gb_vram",
        "max_mem_used_gb", "avg_bw_tbs", "monthly_savings", "reason",
    ]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for r in recs:
            w.writerow(r)
    return out_path


def run(verbose: bool = True) -> dict:
    tel = load_csv("gpu_telemetry.csv")
    cat = catalog_by_type()

    # per-row MFU/MBU, then aggregate per GPU
    agg = defaultdict(lambda: {
        "util": [], "mfu": [], "mbu": [], "mem": [], "bw": [],
        "type": None, "workload": None, "idle_hours": 0,
    })
    for r in tel:
        gtype = r["gpu_type"]
        peak_fp16 = num(cat[gtype]["peak_tflops_fp16"])
        peak_bw = num(cat[gtype]["peak_bw_tbs"])
        mfu = metrics.compute_mfu(num(r["achieved_tflops"]), peak_fp16)
        mbu = metrics.compute_mbu(num(r["achieved_bw_tbs"]), peak_bw)

        a = agg[r["gpu_id"]]
        a["type"] = gtype
        a["workload"] = r.get("workload", "")
        a["util"].append(num(r["gpu_util_pct"]))
        a["mfu"].append(mfu)
        a["mbu"].append(mbu)
        a["mem"].append(num(r.get("mem_used_gb")))
        a["bw"].append(num(r.get("achieved_bw_tbs")))
        if num(r["gpu_util_pct"]) < 10:  # effectively idle this interval (1h)
            a["idle_hours"] += 1

    summary = []
    for gid, a in agg.items():
        summary.append({
            "gpu_id": gid,
            "gpu_type": a["type"],
            "workload": a["workload"],
            "gpu_util_pct": round(sum(a["util"]) / len(a["util"]), 1),
            "mfu": round(sum(a["mfu"]) / len(a["mfu"]), 3),
            "mbu": round(sum(a["mbu"]) / len(a["mbu"]), 3),
            "idle_hours": a["idle_hours"],
            "max_mem_used_gb": round(max(a["mem"]) if a["mem"] else 0.0, 1),
            "avg_bw_tbs": round(sum(a["bw"]) / len(a["bw"]) if a["bw"] else 0.0, 3),
        })

    lies = metrics.flag_util_lies(summary)
    idle_waste = 0.0
    for s in summary:
        on_demand = num(cat[s["gpu_type"]]["on_demand_hr"])
        idle_waste += metrics.idle_waste_usd(s["idle_hours"], on_demand)

    rightsizing_recs = rightsize_by_mbu(summary, cat)
    write_rightsizing_csv(rightsizing_recs)
    rightsize_monthly_savings = sum(r["monthly_savings"] for r in rightsizing_recs)

    if verbose:
        print("== M1 Efficiency Audit ==")
        print(f"{'GPU':14}{'type':7}{'workload':10}{'util%':>7}{'MFU':>7}{'MBU':>7}{'idle_h':>8}{'max_mem':>9}")
        for s in sorted(summary, key=lambda x: x["mfu"]):
            print(f"{s['gpu_id']:14}{s['gpu_type']:7}{s['workload']:10}{s['gpu_util_pct']:>7}{s['mfu']:>7}{s['mbu']:>7}{s['idle_hours']:>8}{s['max_mem_used_gb']:>9}")

        print(f"\nGPU-Util LIES (util>=90% but MFU<30%): {[l['gpu_id'] for l in lies]}")
        print(f"Idle waste (1 day): ${idle_waste:,.2f}  ->  ${idle_waste*30:,.0f}/month")

        print("\nExtension 2: MBU-aware right-sizing recommendations")
        if rightsizing_recs:
            print(f"{'gpu':14}{'current':9}{'target':9}{'$/GB cur':>10}{'$/GB tgt':>10}{'savings/mo':>12}")
            for r in rightsizing_recs:
                print(
                    f"{r['gpu_id']:14}{r['current_gpu']:9}{r['recommended_gpu']:9}"
                    f"{r['current_usd_per_gb_vram']:>10.4f}{r['recommended_usd_per_gb_vram']:>10.4f}"
                    f"${r['monthly_savings']:>11,}"
                )
            print(f"Right-sizing monthly savings: ${rightsize_monthly_savings:,.0f}")
            print("CSV -> outputs/ext2_rightsizing_mbu.csv")
        else:
            print("No safe cheaper GPU found with observed VRAM and bandwidth headroom.")

    return {
        "summary": summary,
        "lies": lies,
        "idle_waste_daily": round(idle_waste, 2),
        "rightsizing_recommendations": rightsizing_recs,
        "rightsize_monthly_savings": round(rightsize_monthly_savings),
    }


if __name__ == "__main__":
    run()
