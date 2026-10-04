"""
similarity.py
=============

PURPOSE
-------
Decide how comparable a past disruption is to the new one, and find the
most comparable past cases.

There is deliberately NO machine learning here. The professor must be
able to read the number off the screen and see exactly why a case was
considered similar. Every score in this file can be worked out by hand
on paper.

THE FORMULA
-----------
    similarity = 40% x material match
               + 30% x delay match
               + 30% x project size match

    ...expressed as a percentage from 0% to 100%.

WHERE DO 40 / 30 / 30 COME FROM?
--------------------------------
They are OUR ASSUMPTION for this prototype. Nothing more.

They were not measured from real procurement data, not fitted to our
simulation, and they are not an industry standard. We chose them because
material seemed the most decisive dimension and the other two seemed
roughly equally important.

Any report using this prototype must describe them as a prototype
assumption, not as an established weighting. Establishing real weights
would require real disruption records from real contractors, which this
project does not have.
"""

# How much each dimension counts towards the total.
# These must add up to 1.0.
#
# PROTOTYPE ASSUMPTION - chosen by judgement, not measured from data.
# See the note at the top of this file.
WEIGHT_MATERIAL = 0.40
WEIGHT_DELAY = 0.30
WEIGHT_PROJECT_SIZE = 0.30

# Project sizes in order, so we can measure "how many levels apart".
SIZE_ORDER = ["Small", "Medium", "Large"]

# How many days apart two delays have to be before we call them
# completely different. 10 days apart = 0% delay similarity.
DELAY_TOLERANCE_DAYS = 10


def material_similarity(material_a, material_b):
    """
    Same material = 1.0, different material = 0.0.

    Deliberately blunt. We could say steel and concrete are "a bit
    alike", but any such judgement would be our opinion smuggled into
    the results, and this is precisely the dimension we are testing.
    """
    return 1.0 if material_a == material_b else 0.0


def project_size_similarity(size_a, size_b):
    """
    Same size          = 1.0   (Large vs Large)
    One level apart    = 0.5   (Large vs Medium)
    Two levels apart   = 0.0   (Large vs Small)
    """
    levels_apart = abs(SIZE_ORDER.index(size_a) - SIZE_ORDER.index(size_b))
    if levels_apart == 0:
        return 1.0
    if levels_apart == 1:
        return 0.5
    return 0.0


def delay_similarity(delay_a, delay_b):
    """
    Straight-line drop-off by distance in days.

    Same day        -> 1.00
    1 day apart     -> 0.90
    3 days apart    -> 0.70
    10+ days apart  -> 0.00
    """
    days_apart = abs(delay_a - delay_b)
    score = 1.0 - (days_apart / DELAY_TOLERANCE_DAYS)
    return max(0.0, score)


def describe_delay(days_apart):
    """Turn a number of days into words, for the explanation on screen."""
    if days_apart == 0:
        return "identical"
    if days_apart == 1:
        return "very similar (1 day apart)"
    if days_apart <= 3:
        return f"similar ({days_apart} days apart)"
    if days_apart <= 6:
        return f"somewhat different ({days_apart} days apart)"
    return f"very different ({days_apart} days apart)"


def describe_size(size_a, size_b):
    """Turn a size comparison into words."""
    levels_apart = abs(SIZE_ORDER.index(size_a) - SIZE_ORDER.index(size_b))
    if levels_apart == 0:
        return "same"
    if levels_apart == 1:
        return f"one level apart ({size_b} vs {size_a})"
    return f"two levels apart ({size_b} vs {size_a})"


def compare(new_disruption, past_case):
    """
    Compare one new disruption against one past case.

    `new_disruption` is a dictionary like:
        {"material": "Steel", "delay_days": 5, "project_size": "Large"}

    Returns a dictionary with the total score AND the reasoning behind
    it, so the interface can show the working out.
    """
    material_score = material_similarity(
        new_disruption["material"], past_case["material"]
    )
    delay_score = delay_similarity(
        new_disruption["delay_days"], past_case["delay_days"]
    )
    size_score = project_size_similarity(
        new_disruption["project_size"], past_case["project_size"]
    )

    total = (
        WEIGHT_MATERIAL * material_score
        + WEIGHT_DELAY * delay_score
        + WEIGHT_PROJECT_SIZE * size_score
    )

    days_apart = abs(new_disruption["delay_days"] - past_case["delay_days"])

    return {
        "similarity": round(total * 100),          # 0 to 100
        "material_score": material_score,
        "delay_score": delay_score,
        "size_score": size_score,
        "explanation": {
            "Material": "same" if material_score == 1.0 else
                        f"different ({past_case['material']} vs {new_disruption['material']})",
            "Delay": describe_delay(days_apart),
            "Project size": describe_size(
                new_disruption["project_size"], past_case["project_size"]
            ),
        },
    }


def find_similar_cases(new_disruption, all_cases, top_n=3):
    """
    Score every past case and return the `top_n` most comparable ones.

    Each returned case is the original case dictionary with two extra
    keys added: "similarity" and "explanation".
    """
    scored = []
    for case in all_cases:
        result = compare(new_disruption, case)
        enriched = dict(case)                       # copy, don't modify the original
        enriched["similarity"] = result["similarity"]
        enriched["explanation"] = result["explanation"]
        scored.append(enriched)

    # Sort from most similar to least similar.
    # The case_id is a tie-breaker so the result is always the same order.
    scored.sort(key=lambda c: (-c["similarity"], c["case_id"]))

    return scored[:top_n]


# ---------------------------------------------------------------------
# WHEN TO STAY QUIET
# ---------------------------------------------------------------------
# The evaluation showed that history only helps when it is comparable:
#
#   band 2, 77% similar  ->  error -43%   (history helps)
#   band 3, 60% similar  ->  error  +9%   (history HURTS)
#
# So below a cut-off the system reports that no comparable history
# exists instead of giving advice. 70% sits between the two measured
# bands. It is a prototype choice read off our own results, not a
# tuned or validated threshold.
MIN_SIMILARITY_FOR_ADVICE = 70


def average_similarity(retrieved_cases):
    """Mean similarity of the retrieved cases, 0-100 (the evaluation's measure)."""
    if not retrieved_cases:
        return 0
    return round(sum(c["similarity"] for c in retrieved_cases) / len(retrieved_cases))


def has_comparable_history(retrieved_cases):
    """True when the retrieved cases are similar enough to advise on."""
    return average_similarity(retrieved_cases) >= MIN_SIMILARITY_FOR_ADVICE


def contribution_breakdown(new_disruption, past_case):
    """
    How many of the similarity points came from each dimension, e.g.
    {"Material": 40, "Delay": 21, "Project size": 30} for a 91% match.
    """
    result = compare(new_disruption, past_case)
    return {
        "Material": round(WEIGHT_MATERIAL * result["material_score"] * 100),
        "Delay": round(WEIGHT_DELAY * result["delay_score"] * 100),
        "Project size": round(WEIGHT_PROJECT_SIZE * result["size_score"] * 100),
    }
