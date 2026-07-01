"""M2 - Inference Cost Levers: $/1M-token, batch x cache x cascade.

Extension 3:
- cache_is_worth_it(avg_cache_reads, write_cost, read_discount)
- break-even reads per model tier
- outputs/ext3_cache_economics.csv

Extension 4:
- reasoning vs non-reasoning cost and energy split
- 10% reasoning traffic cap simulation
- outputs/ext4_reasoning_budget.csv
"""
from __future__ import annotations
import os as _os, sys as _sys
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import csv
import os
from collections import defaultdict
from missions._common import load_csv, num, ROOT
from finops import pricing, sustainability

# $/1M tokens (input, output) - illustrative 2026.
MODEL_PRICES = {"small": (0.20, 0.40), "large": (3.00, 15.00)}

# Prompt-cache write cost as a multiple of normal input price.
CACHE_WRITE_COST_MULT = {"small": 1.25, "large": 1.25}
CACHE_READ_DISCOUNT = 0.10

REASONING_TRAFFIC_CAP = 0.10


def cache_stats_by_tier(rows: list[dict]) -> dict:
    """Compute a simple observed cache-read proxy for each model tier."""
    stats = defaultdict(lambda: {
        "requests": 0,
        "input_tokens": 0,
        "cached_tokens": 0,
        "uncached_tokens": 0,
    })

    for r in rows:
        tier = r["route_tier"]
        inp = int(num(r["input_tokens"]))
        cached = min(int(num(r["cached_input_tokens"])), inp)
        stats[tier]["requests"] += 1
        stats[tier]["input_tokens"] += inp
        stats[tier]["cached_tokens"] += cached
        stats[tier]["uncached_tokens"] += inp - cached

    out = {}
    for tier, s in stats.items():
        write_volume = max(1, s["uncached_tokens"])
        avg_reads = s["cached_tokens"] / write_volume
        write_cost = CACHE_WRITE_COST_MULT.get(tier, 1.25)
        break_even = pricing.cache_break_even_reads(write_cost, CACHE_READ_DISCOUNT)
        use_cache = pricing.cache_is_worth_it(avg_reads, write_cost, CACHE_READ_DISCOUNT)
        out[tier] = {
            **s,
            "avg_cache_reads": round(avg_reads, 3),
            "write_cost_mult": write_cost,
            "break_even_reads": round(break_even, 3),
            "cache_is_worth_it": use_cache,
        }
    return out


def write_cache_csv(stats: dict) -> str:
    out_path = os.path.join(ROOT, "outputs", "ext3_cache_economics.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fields = [
        "tier", "requests", "input_tokens", "cached_tokens", "uncached_tokens",
        "avg_cache_reads", "write_cost_mult", "break_even_reads", "cache_is_worth_it",
    ]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for tier, s in sorted(stats.items()):
            w.writerow({"tier": tier, **s})
    return out_path


def optimized_request_cost(row: dict, cache_stats: dict) -> tuple[float, int, int, bool]:
    """Return optimized request cost and effective token fields."""
    inp = int(num(row["input_tokens"]))
    out = int(num(row["output_tokens"]))
    cached = int(num(row["cached_input_tokens"]))
    is_batch = bool(int(num(row["is_batch"])))
    tier = row["route_tier"]
    pin, pout = MODEL_PRICES[tier]

    effective_cached = cached if cache_stats[tier]["cache_is_worth_it"] else 0
    cost = pricing.request_cost(inp, out, pin, pout, cached_in=effective_cached, batch=is_batch)
    return cost, inp, out, is_batch


def reasoning_budget(rows: list[dict], cache_stats: dict) -> dict:
    """Split cost and Wh by reasoning flag and simulate a 10% traffic cap."""
    buckets = {
        "reasoning": {"requests": 0, "tokens": 0, "cost": 0.0, "wh": 0.0, "extra_cost": 0.0, "extra_wh": 0.0},
        "non_reasoning": {"requests": 0, "tokens": 0, "cost": 0.0, "wh": 0.0, "extra_cost": 0.0, "extra_wh": 0.0},
    }

    reasoning_extras = []

    for r in rows:
        is_reasoning = bool(int(num(r["is_reasoning"])))
        cost, inp, out, is_batch = optimized_request_cost(r, cache_stats)
        total_tok = inp + out
        wh = sustainability.wh_per_query(total_tok, is_reasoning=is_reasoning)

        key = "reasoning" if is_reasoning else "non_reasoning"
        buckets[key]["requests"] += 1
        buckets[key]["tokens"] += total_tok
        buckets[key]["cost"] += cost
        buckets[key]["wh"] += wh

        if is_reasoning:
            tier = r["route_tier"]
            pin, pout = MODEL_PRICES[tier]
            cached = int(num(r["cached_input_tokens"]))
            effective_cached = cached if cache_stats[tier]["cache_is_worth_it"] else 0

            # Data generator multiplies reasoning output by 6. This estimates a
            # non-reasoning route for requests beyond the reasoning budget.
            non_reasoning_out = max(1, int(out / 6))
            cf_cost = pricing.request_cost(
                inp,
                non_reasoning_out,
                pin,
                pout,
                cached_in=effective_cached,
                batch=is_batch,
            )
            cf_wh = sustainability.wh_per_query(inp + non_reasoning_out, is_reasoning=False)
            extra_cost = max(0.0, cost - cf_cost)
            extra_wh = max(0.0, wh - cf_wh)
            buckets[key]["extra_cost"] += extra_cost
            buckets[key]["extra_wh"] += extra_wh
            reasoning_extras.append({"extra_cost": extra_cost, "extra_wh": extra_wh})

    total_requests = len(rows)
    reasoning_requests = buckets["reasoning"]["requests"]
    allowed_reasoning = int(total_requests * REASONING_TRAFFIC_CAP)
    excess_reasoning = max(0, reasoning_requests - allowed_reasoning)

    # Cap savings: remove the largest extra reasoning costs first.
    reasoning_extras.sort(key=lambda x: x["extra_cost"], reverse=True)
    capped = reasoning_extras[:excess_reasoning]
    cap_cost_savings = sum(x["extra_cost"] for x in capped)
    cap_wh_savings = sum(x["extra_wh"] for x in capped)

    total_cost = buckets["reasoning"]["cost"] + buckets["non_reasoning"]["cost"]
    total_wh = buckets["reasoning"]["wh"] + buckets["non_reasoning"]["wh"]

    return {
        "buckets": buckets,
        "total_requests": total_requests,
        "reasoning_requests": reasoning_requests,
        "reasoning_request_pct": reasoning_requests / total_requests * 100 if total_requests else 0.0,
        "reasoning_cost_pct": buckets["reasoning"]["cost"] / total_cost * 100 if total_cost else 0.0,
        "reasoning_wh_pct": buckets["reasoning"]["wh"] / total_wh * 100 if total_wh else 0.0,
        "allowed_reasoning_at_10pct": allowed_reasoning,
        "excess_reasoning": excess_reasoning,
        "cap_cost_savings_daily": cap_cost_savings,
        "cap_wh_savings_daily": cap_wh_savings,
    }


def write_reasoning_csv(rb: dict) -> str:
    out_path = os.path.join(ROOT, "outputs", "ext4_reasoning_budget.csv")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    fields = ["bucket", "requests", "tokens", "cost_daily", "wh_daily", "extra_cost_daily", "extra_wh_daily"]
    with open(out_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        for bucket, s in rb["buckets"].items():
            w.writerow({
                "bucket": bucket,
                "requests": s["requests"],
                "tokens": s["tokens"],
                "cost_daily": round(s["cost"], 4),
                "wh_daily": round(s["wh"], 4),
                "extra_cost_daily": round(s["extra_cost"], 4),
                "extra_wh_daily": round(s["extra_wh"], 4),
            })
    return out_path


def run(verbose: bool = True) -> dict:
    rows = load_csv("token_usage.csv")
    cache_stats = cache_stats_by_tier(rows)
    write_cache_csv(cache_stats)

    base_cost = opt_cost = 0.0
    total_tokens = 0
    cache_tokens_used = 0
    cache_tokens_skipped = 0

    for r in rows:
        inp, out = int(num(r["input_tokens"])), int(num(r["output_tokens"]))
        cached = int(num(r["cached_input_tokens"]))
        is_batch = bool(int(num(r["is_batch"])))
        total_tokens += inp + out

        # BASELINE: naive deployment - everything on the large model, no cache, no batch.
        lin, lout = MODEL_PRICES["large"]
        base_cost += pricing.request_cost(inp, out, lin, lout)

        # OPTIMIZED: cascade, economically justified prompt cache, batch API.
        tier = r["route_tier"]
        pin, pout = MODEL_PRICES[tier]
        if cache_stats[tier]["cache_is_worth_it"]:
            effective_cached = cached
            cache_tokens_used += min(cached, inp)
        else:
            effective_cached = 0
            cache_tokens_skipped += min(cached, inp)

        opt_cost += pricing.request_cost(
            inp,
            out,
            pin,
            pout,
            cached_in=effective_cached,
            batch=is_batch,
        )

    rb = reasoning_budget(rows, cache_stats)
    write_reasoning_csv(rb)

    base_pm = pricing.dollars_per_million(base_cost, total_tokens)
    opt_pm = pricing.dollars_per_million(opt_cost, total_tokens)
    savings_pct = (1 - opt_cost / base_cost) * 100 if base_cost else 0.0

    if verbose:
        print("== M2 Inference Cost Levers ==")
        print(f"requests={len(rows)}  tokens={total_tokens:,}")
        print(f"baseline  : ${base_cost:,.2f}/day   ${base_pm:.3f}/1M-token")
        print(f"optimized : ${opt_cost:,.2f}/day   ${opt_pm:.3f}/1M-token")
        print(f"savings   : {savings_pct:.1f}%  (cascade + caching + batch)")
        print(f"discount stack (batch + 100% cache): {pricing.discount_stack(batch=True, cache_hit_frac=1.0):.3f} of naive")

        print("\nExtension 3: cache economics")
        print(f"{'tier':8}{'avg_reads':>12}{'break_even':>14}{'use_cache':>12}{'cached_tok':>14}")
        for tier, s in sorted(cache_stats.items()):
            print(
                f"{tier:8}{s['avg_cache_reads']:>12.3f}"
                f"{s['break_even_reads']:>14.3f}"
                f"{str(s['cache_is_worth_it']):>12}"
                f"{s['cached_tokens']:>14,}"
            )
        print(f"cache tokens used: {cache_tokens_used:,}; skipped: {cache_tokens_skipped:,}")
        print("CSV -> outputs/ext3_cache_economics.csv")

        print("\nExtension 4: reasoning budget")
        print(
            f"reasoning traffic: {rb['reasoning_requests']}/{rb['total_requests']} "
            f"({rb['reasoning_request_pct']:.1f}% requests)"
        )
        print(f"reasoning cost share: {rb['reasoning_cost_pct']:.1f}%")
        print(f"reasoning energy share: {rb['reasoning_wh_pct']:.1f}%")
        print(
            f"cap reasoning at 10% -> excess requests={rb['excess_reasoning']}, "
            f"save ${rb['cap_cost_savings_daily']:.4f}/day and {rb['cap_wh_savings_daily']:.2f} Wh/day"
        )
        print("CSV -> outputs/ext4_reasoning_budget.csv")

    return {
        "baseline_daily": round(base_cost, 2),
        "optimized_daily": round(opt_cost, 2),
        "baseline_per_m": round(base_pm, 3),
        "optimized_per_m": round(opt_pm, 3),
        "savings_pct": round(savings_pct, 1),
        "total_tokens": total_tokens,
        "cache_stats": cache_stats,
        "reasoning_budget": rb,
    }


if __name__ == "__main__":
    run()
