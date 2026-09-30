"""Post-cost fixed-weight, split-adjusted share/cash ledger. No split is applied twice."""

import numpy as np
from numba import njit

FIELDS = [
    "price",
    "shares_before",
    "cash_before",
    "distribution_accrual",
    "distribution_settlement",
    "distribution_receivable",
    "equity_before_trade",
    "target_weight",
    "shares_after",
    "cash_after",
    "shares_traded",
    "traded_notional",
    "transaction_cost",
    "borrow_cost",
    "financing_cost",
    "eligible_cash_interest",
    "restricted_short_collateral",
    "eligible_cash_balance",
    "equity_after_trade",
    "marked_equity_next_boundary",
    "signal_switch",
    "rebalance_trade",
    "executed_trade",
    "insolvent",
    "self_financing_residual",
    "target_weight_residual",
    "accrual_days",
]


@njit(cache=True)
def solve_target(equity, holding_value, target, cost):
    a = target * equity - holding_value
    side = 1.0 if a >= 0 else -1.0
    delta = a / (1.0 + cost * target * side)
    if abs(delta) <= 1e-12 * max(1.0, abs(equity)):
        delta = 0.0
    fee = cost * abs(delta)
    return holding_value + delta, delta, fee


@njit(cache=True)
def execute(
    prices,
    targets,
    distributions,
    time_days,
    cost,
    initial=100.0,
    borrow_rate=0.0,
    financing_rate=0.0,
    cash_rate=0.0,
    settlement_delay_days=0.0,
):
    n = len(prices)
    log = np.zeros((n, 27))
    q, cash, recv = 0.0, initial, 0.0
    prev_target = 0.0
    pending_amount = np.zeros(n)
    pending_due = np.full(n, np.inf)
    pending_count = 0
    pending_head = 0
    assert 0.0 <= cost < 1.0 and settlement_delay_days >= 0
    assert len(targets) == n and len(distributions) == n and len(time_days) == n
    assert np.all(prices > 0.0) and np.all(np.isfinite(prices))
    assert np.all(np.abs(targets) <= 1.0) and np.all(np.diff(time_days) >= 0.0)
    insolvent = False
    path = np.empty(1 + 2 * n)
    path[0] = initial
    for k in range(n):
        p = prices[k]
        q0, c0 = q, cash
        days = 0.0 if k == 0 else time_days[k] - time_days[k - 1]
        restricted = max(-q * prices[max(0, k - 1)], 0.0)
        eligible = max(cash - restricted, 0.0)
        borrow = restricted * borrow_rate * days / 365.0 if not insolvent else 0.0
        finance = (
            max(-cash, 0.0) * financing_rate * days / 365.0 if not insolvent else 0.0
        )
        interest = eligible * cash_rate * days / 365.0 if not insolvent else 0.0
        cash += interest - borrow - finance
        distribution = q * distributions[k]
        recv += distribution
        settled = 0.0
        if settlement_delay_days == 0.0:
            settled = distribution
        else:
            if distribution != 0:
                pending_amount[pending_count] = distribution
                pending_due[pending_count] = time_days[k] + settlement_delay_days
                pending_count += 1
            while (
                pending_head < pending_count
                and pending_due[pending_head] <= time_days[k]
            ):
                settled += pending_amount[pending_head]
                pending_head += 1
        recv -= settled
        cash += settled
        e0 = cash + q * p + recv
        target = targets[k]
        if e0 <= 0.0:
            insolvent = True
        if insolvent:
            target = 0.0
        value, delta, fee = solve_target(e0, q * p, target, cost)
        q = value / p
        cash -= delta + fee
        e1 = cash + q * p + recv
        if e1 <= 0:
            insolvent = True
        switched = 1.0 if target != prev_target else 0.0
        traded = 1.0 if delta != 0.0 else 0.0
        path[1 + 2 * k] = e0
        path[2 + 2 * k] = e1
        log[k, 0] = p
        log[k, 1] = q0
        log[k, 2] = c0
        log[k, 3] = distribution
        log[k, 4] = settled
        log[k, 5] = recv
        log[k, 6] = e0
        log[k, 7] = target
        log[k, 8] = q
        log[k, 9] = cash
        log[k, 10] = delta / p
        log[k, 11] = abs(delta)
        log[k, 12] = fee
        log[k, 13] = borrow
        log[k, 14] = finance
        log[k, 15] = interest
        log[k, 16] = restricted
        log[k, 17] = eligible
        log[k, 18] = e1
        log[k, 19] = np.nan
        log[k, 20] = switched
        log[k, 21] = traded * (1 - switched)
        log[k, 22] = traded
        log[k, 23] = 1.0 if insolvent else 0.0
        log[k, 24] = e1 - (e0 - fee)
        log[k, 25] = q * p - target * e1
        log[k, 26] = days
        prev_target = target
        if k > 0:
            log[k - 1, 19] = e0
    return log, path


def daily_from_log(log, initial=100.0):
    # Close trades fund next night. Final-day return includes final liquidation.
    marks = log[2::2, 6].copy()
    marks[-1] = log[-1, 18]
    prev = np.r_[initial, marks[:-1]]
    with np.errstate(divide="ignore", invalid="ignore"):
        result = marks / prev - 1
    result[prev <= 0] = 0.0
    return result
