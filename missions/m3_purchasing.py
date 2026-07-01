"""M3 - Purchasing Strategy: break-even, tier choice, spot-checkpoint sim.

Extension 1 adds:
- GPU-specific spot interruption rates.
- 1yr vs 3yr reserved comparison using expected workload duration.
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
from missions._common import load_csv, num, catalog_by_type
from finops import pricing

DAYS = 30


def expected_months_for_job(job: dict) -> float:
    """Simple FinOps assumption for commitment planning.

    Inference services that run steadily are treated as long-lived platform
    services. Batch/dev/training jobs are treated as short-lived unless the data
    says otherwise.
    """
    hpd = num(job["hours_per_day"])
    interruptible = bool(int(num(job["interruptible"])))
    kind = job.get("kind", "")
    days = num(job.get("days", 30))

    if kind == "infer" and not interruptible and hpd >= 18:
        return 36.0
    return max(1.0, days / 30.0)


def run(verbose: bool = True) -> dict:
    jobs = load_csv("workloads.csv")
    cat = catalog_by_type()
    on_demand_monthly = optimized_monthly = 0.0
    recs = []

    for j in jobs:
        gtype = j["gpu_type"]
        ngpu = int(num(j["num_gpus"]))
        hpd = num(j["hours_per_day"])
        days = num(j["days"])
        interruptible = bool(int(num(j["interruptible"])))
        expected_months = expected_months_for_job(j)

        c = cat[gtype]
        gpu_hours = hpd * DAYS * ngpu
        od = num(c["on_demand_hr"])
        on_demand_cost = gpu_hours * od

        tier = pricing.recommend_tier(
            hpd,
            interruptible,
            gpu_type=gtype,
            job_days=days,
            expected_months=expected_months,
        )

        plan = tier
        intr_rate = pricing.spot_interruption_rate(gtype)
        if tier == "spot":
            sim = pricing.spot_checkpoint_cost(
                gpu_hours,
                num(c["spot_hr"]),
                od,
                interrupt_rate=intr_rate,
            )
            opt_cost = sim["spot_cost"]
            plan = f"spot@{intr_rate:.0%}intr"
        elif tier == "reserved":
            term = pricing.recommend_reserved_term(hpd, expected_months)
            if term["term"] == "reserved_1yr":
                opt_cost = gpu_hours * num(c["reserved_1yr_hr"])
            else:
                opt_cost = gpu_hours * num(c["reserved_3yr_hr"])
            plan = f"{term['term']}/{expected_months:.0f}mo"
        else:
            opt_cost = on_demand_cost
            plan = f"on_demand/{expected_months:.0f}mo"

        on_demand_monthly += on_demand_cost
        optimized_monthly += opt_cost
        recs.append({
            "job_id": j["job_id"],
            "gpu_type": gtype,
            "tier": tier,
            "plan": plan,
            "expected_months": round(expected_months, 1),
            "spot_interrupt_rate": round(intr_rate, 3),
            "on_demand": round(on_demand_cost),
            "optimized": round(opt_cost),
        })

    savings = on_demand_monthly - optimized_monthly
    savings_pct = savings / on_demand_monthly * 100 if on_demand_monthly else 0.0

    if verbose:
        print("== M3 Purchasing Strategy ==")
        print(f"break-even utilization @ 45% reserved discount = {pricing.break_even_utilization(0.45):.0%}")
        print("Extension 1: tier policy uses GPU-specific spot interruption rates and reserved 1yr/3yr duration comparison.")
        print(f"{'job':18}{'gpu':7}{'tier':11}{'plan':18}{'on-demand':>12}{'optimized':>12}")
        for r in recs:
            print(f"{r['job_id']:18}{r['gpu_type']:7}{r['tier']:11}{r['plan']:18}${r['on_demand']:>11,}${r['optimized']:>11,}")
        print(f"\nmonthly: on-demand ${on_demand_monthly:,.0f} -> optimized ${optimized_monthly:,.0f}  ({savings_pct:.1f}% saved)")

    return {
        "recommendations": recs,
        "on_demand_monthly": round(on_demand_monthly),
        "optimized_monthly": round(optimized_monthly),
        "savings_pct": round(savings_pct, 1),
    }


if __name__ == "__main__":
    run()
