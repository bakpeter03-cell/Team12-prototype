"""
calculations.py
===============

PURPOSE
-------
This file is THE SYSTEM'S BRAIN. It works out what each of the three
responses is likely to cost, in two different ways, and the difference
between them is the whole experiment:

  1. BASELINE estimate
     Uses the WHOLE database, but ignores comparability completely.
     It does not care what material is involved or how similar any past
     case is. It just averages everything.

  2. HISTORY-CORRECTED estimate
     Uses only the handful of MOST COMPARABLE past cases.

  3. BLENDED estimate (what the prototype recommends on)
     Half of each.

THE QUESTION THIS SETS UP
-------------------------
    Does it matter WHICH past cases you use,
    or is any history as good as any other?

That is the research question, stated as arithmetic.

WHERE THE BASELINE NUMBERS COME FROM
------------------------------------
They are not invented, and they do not come from inside the simulator.
Every one of them is a plain average taken from the historical database
itself - the same database the system is allowed to see, under the same
cross-project rule. You could reproduce any of them in a spreadsheet.
"""

import statistics

ACTIONS = ["Accept", "Switch", "Expedite"]

PROJECT_SIZES = ["Small", "Medium", "Large"]

# How much we trust the comparable cases versus the whole-database
# average. 0.0 = ignore comparability, 1.0 = trust it completely.
BLEND_WEIGHT_HISTORY = 0.5


def round_to_hundred(amount):
    """Round a money amount to the nearest €100 so the numbers look tidy."""
    return int(round(amount / 100.0) * 100)


# ---------------------------------------------------------------------
# 1. FITTING THE BASELINE FROM THE DATABASE
# ---------------------------------------------------------------------
def fit_baseline(cases):
    """
    Work out the generic rules by averaging the whole database.

    Three numbers per project size, each a plain average:

        accept_per_day    average of (accept cost / delay days)
        switch_flat       average switching cost
        expedite_per_day  average of (expedite cost / delay days)

    Accepting and expediting both scale with how long the delay is, so
    we average them per day. Switching is dominated by a one-off fee, so
    we average it as a flat amount.

    NOTE: switching cost does drift upward slightly with longer delays
    (roughly 25% across our range), because a few days are still lost
    after switching. The flat average does not capture that. This is
    deliberate - it is exactly the sort of pattern that using the whole
    database indiscriminately misses, and part of what comparable cases
    may be able to correct.

    NOTHING here looks at the material. That is the point.
    """
    overall = {
        "accept_per_day": statistics.mean(
            c["accept_cost"] / c["delay_days"] for c in cases
        ),
        "switch_flat": statistics.mean(c["switch_cost"] for c in cases),
        "expedite_per_day": statistics.mean(
            c["expedite_cost"] / c["delay_days"] for c in cases
        ),
    } if cases else {
        "accept_per_day": 0, "switch_flat": 0, "expedite_per_day": 0
    }

    params = {}
    for size in PROJECT_SIZES:
        group = [c for c in cases if c["project_size"] == size]
        if not group:
            # No cases of this size available - fall back to the overall
            # average rather than crashing.
            params[size] = dict(overall)
            continue
        params[size] = {
            "accept_per_day": statistics.mean(
                c["accept_cost"] / c["delay_days"] for c in group
            ),
            "switch_flat": statistics.mean(c["switch_cost"] for c in group),
            "expedite_per_day": statistics.mean(
                c["expedite_cost"] / c["delay_days"] for c in group
            ),
            "cases_fitted_on": len(group),
        }
    return params


# ---------------------------------------------------------------------
# 2. THE BASELINE ESTIMATE
# ---------------------------------------------------------------------
def baseline_costs(material, delay_days, project_size, params):
    """
    Estimate the three options from the whole-database averages.

    `material` is accepted but never used, and that is intentional: the
    baseline is blind to the material. Comparability is what makes the
    material matter.
    """
    p = params[project_size]
    return {
        "Accept": round_to_hundred(delay_days * p["accept_per_day"]),
        "Switch": round_to_hundred(p["switch_flat"]),
        "Expedite": round_to_hundred(delay_days * p["expedite_per_day"]),
    }


# ---------------------------------------------------------------------
# 3. THE HISTORY CORRECTION
# ---------------------------------------------------------------------
def correction_factors(retrieved_cases, params):
    """
    Work out how wrong the whole-database average was on the comparable
    cases we retrieved.

    In one sentence:
        "On past disruptions like this one, reality cost 1.3 times what
         the database average predicted - so scale our prediction by 1.3."

    WHY A RATIO AND NOT AN AVERAGE OF PAST COSTS?
    Because past cases never have exactly the same delay length, and a
    4-day delay costs far less than a 9-day one. Averaging their dollar
    figures would mostly measure how long those delays were, not what we
    know about this material. The ratio divides the delay length out.

    Returns something like {"Accept": 1.18, "Switch": 0.94, "Expedite": 1.31}
    """
    if not retrieved_cases:
        return {action: 1.0 for action in ACTIONS}

    totals = {action: 0.0 for action in ACTIONS}

    for case in retrieved_cases:
        predicted = baseline_costs(
            case["material"], case["delay_days"], case["project_size"], params
        )
        truth = {
            "Accept": case["accept_cost"],
            "Switch": case["switch_cost"],
            "Expedite": case["expedite_cost"],
        }
        for action in ACTIONS:
            if predicted[action] > 0:
                totals[action] += truth[action] / predicted[action]
            else:
                totals[action] += 1.0

    count = len(retrieved_cases)
    return {action: totals[action] / count for action in ACTIONS}


def historical_costs(material, delay_days, project_size, retrieved_cases,
                     params):
    """The baseline estimate, corrected by the comparable past cases."""
    baseline = baseline_costs(material, delay_days, project_size, params)
    factors = correction_factors(retrieved_cases, params)
    return {
        action: round_to_hundred(baseline[action] * factors[action])
        for action in ACTIONS
    }


# ---------------------------------------------------------------------
# 4. THE BLENDED ESTIMATE
# ---------------------------------------------------------------------
def blended_costs(baseline, historical, weight_history=None):
    """
    Mix the two estimates.

    Leave weight_history as None to use BLEND_WEIGHT_HISTORY above. We
    look the constant up here rather than in the function signature so
    that it can be changed while the program is running.
    """
    if weight_history is None:
        weight_history = BLEND_WEIGHT_HISTORY
    weight_baseline = 1.0 - weight_history
    return {
        action: round_to_hundred(
            weight_baseline * baseline[action] + weight_history * historical[action]
        )
        for action in ACTIONS
    }


# ---------------------------------------------------------------------
# 5. TURNING COSTS INTO A RECOMMENDATION
# ---------------------------------------------------------------------
def recommend(costs):
    """Return the name of the cheapest option, e.g. 'Expedite'."""
    return min(ACTIONS, key=lambda action: costs[action])


def estimate_everything(material, delay_days, project_size, retrieved_cases,
                        params, weight_history=None):
    """
    Run both estimates in one go.

    `params` comes from fit_baseline() and must have been fitted WITHOUT
    the project being advised, so that nothing leaks.
    """
    baseline = baseline_costs(material, delay_days, project_size, params)
    historical = historical_costs(
        material, delay_days, project_size, retrieved_cases, params
    )
    blended = blended_costs(baseline, historical, weight_history)

    return {
        "baseline": baseline,
        "historical": historical,
        "blended": blended,
        "factors": correction_factors(retrieved_cases, params),
        "baseline_recommendation": recommend(baseline),
        "recommendation": recommend(blended),
        "cases_used": len(retrieved_cases),
    }
