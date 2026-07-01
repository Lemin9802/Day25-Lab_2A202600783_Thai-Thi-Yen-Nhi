"""Pricing & purchasing economics - measure in $/1M-token, not $/GPU-hr.

Figures are June-2026 as-of snapshots from the deck's RESEARCH dossier; treat
live prices as fast-moving (re-baseline before each cohort).
"""
from __future__ import annotations


def request_cost(
    input_tok: int,
    output_tok: int,
    price_in_per_m: float,
    price_out_per_m: float,
    cached_in: int = 0,
    cache_discount: float = 0.10,   # Anthropic cached-read ~0.1x (=-90%)
    batch: bool = False,
    batch_discount: float = 0.50,   # Batch API ~ -50%
) -> float:
    """USD cost of a single request. Cached input billed at cache_discount x price."""
    cached_in = min(max(0, cached_in), input_tok)
    uncached_in = input_tok - cached_in
    cost = (
        (uncached_in / 1e6) * price_in_per_m
        + (cached_in / 1e6) * price_in_per_m * cache_discount
        + (output_tok / 1e6) * price_out_per_m
    )
    if batch:
        cost *= batch_discount
    return cost


def dollars_per_million(total_cost_usd: float, total_tokens: int) -> float:
    """Aggregate unit economics: $ per 1,000,000 tokens served."""
    if total_tokens <= 0:
        return 0.0
    return total_cost_usd / (total_tokens / 1e6)


def discount_stack(
    batch: bool = False,
    cache_hit_frac: float = 0.0,
    batch_discount: float = 0.50,
    cache_discount: float = 0.10,
) -> float:
    """Effective fraction of the naive bill after stacking discounts.

    Discounts MULTIPLY: cache applies to the cached share of input, batch to the
    whole bill. batch + 100% cache-hit -> 0.5 * 0.1 = 0.05 (~95% off).
    """
    cache_mult = cache_hit_frac * cache_discount + (1.0 - cache_hit_frac)
    batch_mult = batch_discount if batch else 1.0
    return cache_mult * batch_mult


def break_even_utilization(discount_frac: float) -> float:
    """Utilization at which a commitment pays off ~= 1 - discount.

    A 45% reserved discount needs ~55% utilization (~13.2h/day) to beat on-demand.
    """
    return max(0.0, min(1.0, 1.0 - discount_frac))


# Extension 1: GPU-specific spot interruption assumptions.
SPOT_INTERRUPTION_RATES = {
    "H100": 0.03,
    "H200": 0.04,
    "A100": 0.05,
    "A10G": 0.08,
    "L4": 0.06,
    "B200": 0.04,
    "MI300X": 0.07,
}


def spot_interruption_rate(gpu_type: str | None, default: float = 0.05) -> float:
    """Return expected hourly spot interruption rate for a GPU type."""
    if not gpu_type:
        return default
    return SPOT_INTERRUPTION_RATES.get(str(gpu_type), default)


def recommend_reserved_term(
    hours_per_day: float,
    expected_months: float | None = None,
    reserved_1yr_discount: float = 0.20,
    reserved_3yr_discount: float = 0.45,
) -> dict:
    """Compare 1yr vs 3yr reserved plans using duty cycle and expected duration.

    Returns a small decision record. The main tier remains "reserved" so the
    original lab API stays compatible, while this function explains whether
    1yr, 3yr, or on-demand is the safer commitment.
    """
    duty = max(0.0, hours_per_day) / 24.0
    be_1yr = break_even_utilization(reserved_1yr_discount)
    be_3yr = break_even_utilization(reserved_3yr_discount)

    months = 36.0 if expected_months is None else max(0.0, float(expected_months))

    if duty < be_3yr:
        return {
            "term": "on_demand",
            "discount": 0.0,
            "break_even_util": round(be_3yr, 3),
            "reason": "duty cycle below 3yr break-even",
        }

    if months >= 24:
        return {
            "term": "reserved_3yr",
            "discount": reserved_3yr_discount,
            "break_even_util": round(be_3yr, 3),
            "reason": "stable long-lived workload; 3yr has better hourly rate",
        }

    if months >= 12 and duty >= be_1yr:
        return {
            "term": "reserved_1yr",
            "discount": reserved_1yr_discount,
            "break_even_util": round(be_1yr, 3),
            "reason": "medium duration workload; 1yr limits commitment risk",
        }

    return {
        "term": "on_demand",
        "discount": 0.0,
        "break_even_util": round(be_3yr, 3),
        "reason": "duration too short for reserved commitment",
    }


def recommend_tier(
    hours_per_day: float,
    interruptible: bool,
    reserved_discount: float = 0.45,
    gpu_type: str | None = None,
    job_days: float | None = None,
    expected_months: float | None = None,
    max_spot_interrupt_rate: float = 0.10,
) -> str:
    """Pick a purchasing tier from duty cycle, interruptibility, and commitment risk.

    Backward-compatible behavior is preserved:
      - interruptible & not 24/7  -> 'spot'
      - duty cycle >= break-even  -> 'reserved'
      - otherwise                 -> 'on_demand'

    Extension behavior:
      - GPU-specific spot interruption rate blocks overly risky spot choices.
      - expected_months can force a reserved duration comparison before committing.
    """
    duty = max(0.0, hours_per_day) / 24.0
    be = break_even_utilization(reserved_discount)

    if interruptible and hours_per_day < 24:
        intr = spot_interruption_rate(gpu_type)
        if intr <= max_spot_interrupt_rate:
            return "spot"
        return "on_demand"

    if expected_months is not None:
        term = recommend_reserved_term(hours_per_day, expected_months)
        if term["term"].startswith("reserved"):
            return "reserved"
        return "on_demand"

    if duty >= be:
        return "reserved"
    return "on_demand"


def spot_checkpoint_cost(
    job_hours: float,
    spot_hr: float,
    on_demand_hr: float,
    interrupt_rate: float = 0.05,      # per-hour chance
    ckpt_overhead_frac: float = 0.03,  # steady cost of writing checkpoints
    rework_hours_per_interrupt: float = 0.5,
) -> dict:
    """Effective cost of running a checkpointable job on spot vs on-demand.

    Interruptions waste the compute since the last checkpoint (rework); checkpointing
    adds a small steady overhead. Spot still wins for interruptible jobs.
    """
    expected_interrupts = job_hours * interrupt_rate
    rework_hours = expected_interrupts * rework_hours_per_interrupt
    effective_hours = job_hours * (1.0 + ckpt_overhead_frac) + rework_hours
    spot_cost = effective_hours * spot_hr
    on_demand_cost = job_hours * on_demand_hr
    savings_pct = (1.0 - spot_cost / on_demand_cost) * 100.0 if on_demand_cost > 0 else 0.0
    return {
        "spot_effective_hours": round(effective_hours, 2),
        "spot_cost": round(spot_cost, 2),
        "on_demand_cost": round(on_demand_cost, 2),
        "savings_pct": round(savings_pct, 1),
    }

def cache_break_even_reads(write_cost: float, read_discount: float = 0.10) -> float:
    """Minimum repeated reads needed for prompt cache to pay back its write cost.

    We model write_cost as a multiple of the normal input-token price.
    Each cached read saves (1 - read_discount) of the normal input-token price.
    Example: write_cost=1.25 and read_discount=0.10 -> 1.25 / 0.90 = 1.39 reads.
    """
    saved_per_read = max(0.0, 1.0 - read_discount)
    if saved_per_read <= 0:
        return float("inf")
    return write_cost / saved_per_read


def cache_is_worth_it(
    avg_cache_reads: float,
    write_cost: float,
    read_discount: float = 0.10,
) -> bool:
    """Return True when repeated cached reads pay back the cache write cost."""
    return avg_cache_reads >= cache_break_even_reads(write_cost, read_discount)
