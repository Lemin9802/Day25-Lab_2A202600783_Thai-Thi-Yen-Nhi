"""Extension 5 - Carbon-aware scheduling for interruptible GPU jobs.

This extension estimates electricity cost and carbon for interruptible jobs
across available regions, then recommends:
- cheapest region
- cleanest region
- balanced region using normalized cost + normalized carbon
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import csv
import os
from missions._common import load_csv, num, catalog_by_type, ROOT
from finops import sustainability


BASELINE_REGION = "us-east-1"


def interruptible_jobs() -> list[dict]:
    jobs = load_csv("workloads.csv")
    catalog = catalog_by_type()
    out = []

    for j in jobs:
        if int(num(j["interruptible"])) != 1:
            continue

        gtype = j["gpu_type"]
        watts = num(catalog[gtype]["watts"])
        ngpu = int(num(j["num_gpus"]))
        hours_per_day = num(j["hours_per_day"])
        days = num(j["days"])
        kwh = watts * ngpu * hours_per_day * days / 1000.0

        out.append({
            "job_id": j["job_id"],
            "team": j["team"],
            "kind": j["kind"],
            "gpu_type": gtype,
            "num_gpus": ngpu,
            "hours_per_day": hours_per_day,
            "days": days,
            "kwh": kwh,
        })

    return out


def region_totals(jobs: list[dict]) -> list[dict]:
    total_kwh = sum(j["kwh"] for j in jobs)
    rows = []
    for region in sustainability.REGION_CARBON:
        price = sustainability.REGION_PRICE_KWH[region]
        carbon_intensity = sustainability.REGION_CARBON[region]
        electricity_cost = total_kwh * price
        carbon_g = total_kwh * carbon_intensity

        rows.append({
            "region": region,
            "total_kwh": round(total_kwh, 3),
            "usd_per_kwh": price,
            "gco2_per_kwh": carbon_intensity,
            "electricity_cost_usd": round(electricity_cost, 4),
            "carbon_gco2e": round(carbon_g, 2),
        })
    return rows


def add_balanced_score(rows: list[dict]) -> list[dict]:
    costs = [r["electricity_cost_usd"] for r in rows]
    carbons = [r["carbon_gco2e"] for r in rows]
    min_cost, max_cost = min(costs), max(costs)
    min_carbon, max_carbon = min(carbons), max(carbons)

    for r in rows:
        cost_norm = 0.0 if max_cost == min_cost else (r["electricity_cost_usd"] - min_cost) / (max_cost - min_cost)
        carbon_norm = 0.0 if max_carbon == min_carbon else (r["carbon_gco2e"] - min_carbon) / (max_carbon - min_carbon)
        r["balanced_score"] = round(0.5 * cost_norm + 0.5 * carbon_norm, 4)
    return rows


def job_region_rows(jobs: list[dict]) -> list[dict]:
    cleanest_region = min(sustainability.REGION_CARBON, key=sustainability.REGION_CARBON.get)
    rows = []

    for j in jobs:
        baseline_carbon = j["kwh"] * sustainability.REGION_CARBON[BASELINE_REGION]
        clean_carbon = j["kwh"] * sustainability.REGION_CARBON[cleanest_region]
        baseline_cost = j["kwh"] * sustainability.REGION_PRICE_KWH[BASELINE_REGION]
        clean_cost = j["kwh"] * sustainability.REGION_PRICE_KWH[cleanest_region]

        rows.append({
            "job_id": j["job_id"],
            "team": j["team"],
            "kind": j["kind"],
            "gpu_type": j["gpu_type"],
            "num_gpus": j["num_gpus"],
            "kwh": round(j["kwh"], 3),
            "baseline_region": BASELINE_REGION,
            "cleanest_region": cleanest_region,
            "baseline_cost_usd": round(baseline_cost, 4),
            "clean_region_cost_usd": round(clean_cost, 4),
            "baseline_carbon_gco2e": round(baseline_carbon, 2),
            "clean_region_carbon_gco2e": round(clean_carbon, 2),
            "carbon_saved_gco2e": round(baseline_carbon - clean_carbon, 2),
            "carbon_reduction_pct": round((1 - clean_carbon / baseline_carbon) * 100, 1) if baseline_carbon else 0.0,
        })
    return rows


def write_csv(path: str, rows: list[dict]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if not rows:
        return
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)


def run(verbose: bool = True) -> dict:
    jobs = interruptible_jobs()
    by_job = job_region_rows(jobs)
    regions = add_balanced_score(region_totals(jobs))

    out_jobs = os.path.join(ROOT, "outputs", "ext5_carbon_by_job.csv")
    out_regions = os.path.join(ROOT, "outputs", "ext5_carbon_regions.csv")
    write_csv(out_jobs, by_job)
    write_csv(out_regions, regions)

    cheapest = min(regions, key=lambda r: r["electricity_cost_usd"])
    cleanest = min(regions, key=lambda r: r["carbon_gco2e"])
    balanced = min(regions, key=lambda r: r["balanced_score"])

    baseline_total = next(r for r in regions if r["region"] == BASELINE_REGION)
    total_saved = baseline_total["carbon_gco2e"] - cleanest["carbon_gco2e"]
    total_reduction = (1 - cleanest["carbon_gco2e"] / baseline_total["carbon_gco2e"]) * 100 if baseline_total["carbon_gco2e"] else 0.0

    if verbose:
        print("== Extension 5: Carbon-aware Scheduling ==")
        print(f"interruptible jobs: {len(jobs)}")
        print(f"baseline region: {BASELINE_REGION}")
        print(f"cheapest region: {cheapest['region']} (${cheapest['electricity_cost_usd']:.2f})")
        print(f"cleanest region: {cleanest['region']} ({cleanest['carbon_gco2e']:.2f} gCO2e)")
        print(f"balanced region: {balanced['region']} (score={balanced['balanced_score']})")
        print(f"carbon saved by moving interruptible jobs to cleanest region: {total_saved:.2f} gCO2e ({total_reduction:.1f}%)")

        print("\nRegion comparison:")
        print(f"{'region':18}{'$/kWh':>8}{'gCO2/kWh':>12}{'cost':>12}{'carbon':>14}{'score':>9}")
        for r in sorted(regions, key=lambda x: x["balanced_score"]):
            print(
                f"{r['region']:18}{r['usd_per_kwh']:>8.3f}"
                f"{r['gco2_per_kwh']:>12.0f}"
                f"${r['electricity_cost_usd']:>11.2f}"
                f"{r['carbon_gco2e']:>14.2f}"
                f"{r['balanced_score']:>9.4f}"
            )

        print(f"\nCSV -> {out_jobs}")
        print(f"CSV -> {out_regions}")
        print("Trade-off note: the cleanest region may add latency or data-residency constraints, so production rollout should use carbon-aware scheduling mainly for interruptible/offline jobs.")

    return {
        "interruptible_jobs": len(jobs),
        "cheapest_region": cheapest["region"],
        "cleanest_region": cleanest["region"],
        "balanced_region": balanced["region"],
        "carbon_saved_gco2e": round(total_saved, 2),
        "carbon_reduction_pct": round(total_reduction, 1),
    }


if __name__ == "__main__":
    run()
