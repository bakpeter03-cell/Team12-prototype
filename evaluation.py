"""
evaluation.py
=============

PURPOSE
-------
This is the research part of the project. The interface shows the idea;
this file produces the evidence.

THE ASSUMPTION WE TEST
----------------------
    Can historical procurement disruptions from one project provide
    useful information for a new disruption on another project, when
    the characteristics of the projects differ?

THE TWO ESTIMATES BEING COMPARED
--------------------------------
    BASELINE   use the whole database, ignore comparability entirely
    SYSTEM     use only the most comparable cases

So the experiment is really asking: does it matter WHICH past cases you
use, or is any history as good as any other?

THE CROSS-PROJECT RULE
----------------------
When advising a disruption on Project X, nothing from Project X may be
used - not for retrieval, and not for fitting the baseline. Applied in
one place (`build_pool`) so no experiment can bypass it, and checked on
every run.

WHAT IT RUNS
------------
    1.  The four comparability bands          the main experiment
    1b. Own history versus a shared pool      the pooling question
    C.  The same method with material labels shuffled  the credibility check

HOW TO RUN IT
-------------
    python3 evaluation.py              the three experiments above
    python3 evaluation.py --appendix   also the two supporting experiments
"""

import csv
import os
import random
import statistics
import sys

import calculations
import database
import similarity
from data_generator import MATERIALS, PROJECTS, simulate_true_costs

ACTIONS = calculations.ACTIONS
SIZE_ORDER = similarity.SIZE_ORDER

NUMBER_OF_TEST_DISRUPTIONS = 200
TEST_SEED = 2024
HOW_MANY_SIMILAR_CASES = 3

# =====================================================================
# THE TEST DISRUPTIONS
# =====================================================================
def make_test_disruptions(how_many=NUMBER_OF_TEST_DISRUPTIONS, seed=TEST_SEED,
                          history=None):
    """
    Invent brand new disruptions that are NOT in the database.

    When `history` is given, candidates keep being generated until there
    are `how_many` that every comparability band can serve with at least
    HOW_MANY_SIMILAR_CASES cases (see run_experiment_1). That way all
    200 test disruptions are measured at all four bands - the design
    stays strictly paired and nothing has to be dropped afterwards.

    Each happens on one of the existing projects - which is what makes
    the cross-project rule meaningful, since that project already has a
    history the system will be forbidden from using.

    We also record what the three options truly cost. That is our ground
    truth. The system never sees it; we only use it to mark the result.
    """
    rng = random.Random(seed)
    disruptions = []

    number = 0
    while len(disruptions) < how_many:
        number += 1
        if number > how_many * 20:
            raise RuntimeError("Could not find enough usable test disruptions.")
        project_id = rng.choice(list(PROJECTS.keys()))
        project = PROJECTS[project_id]
        project_size = project["project_size"]
        material = rng.choice(list(MATERIALS.keys()))
        delay_days = rng.randint(1, 15)

        truth = simulate_true_costs(
            material, delay_days, project_size, rng, project["project_effect"]
        )

        candidate = {
            "project_id": project_id, "material": material,
            "delay_days": delay_days, "project_size": project_size,
        }
        if history is not None and not usable_at_every_band(history, candidate):
            continue

        disruptions.append({
            "test_id": f"T{len(disruptions) + 1:03d}",
            "project_id": project_id,
            "material": material,
            "delay_days": delay_days,
            "project_size": project_size,
            "true_accept_cost": truth["Accept"],
            "true_switch_cost": truth["Switch"],
            "true_expedite_cost": truth["Expedite"],
            "true_best_action": min(ACTIONS, key=lambda a: truth[a]),
        })

    return disruptions


def shuffle_materials(cases, seed=TEST_SEED + 500):
    """
    THE CONTROL: randomly reassign the material labels in the database.

    Every case keeps its real cost, its real delay and its real project.
    Only the MATERIAL LABEL is shuffled, so it no longer says anything
    true about why that case cost what it did.

    WHY THIS IS THE RIGHT CONTROL
    Our claim is that comparability carries information - and material
    is the dimension the results hang on. If the claim is real, then
    destroying the meaning of the material label should collapse the
    difference between "same material" bands and "different material"
    bands. If that difference survives, our method is responding to
    something other than genuine comparability, and the result is not
    trustworthy.

    We deliberately do NOT randomise the costs themselves. We tried
    that first and it failed as a control: with random costs, the
    baseline's assumption that cost scales with delay length becomes
    wrong, the baseline goes badly astray, and almost any correction
    appears to improve it. That measures the baseline's shape, not our
    claim. Shuffling one label leaves everything else intact.
    """
    rng = random.Random(seed)
    labels = [case["material"] for case in cases]
    rng.shuffle(labels)
    return [dict(case, material=label) for case, label in zip(cases, labels)]


def truth_of(test):
    """Pull the three true costs out of a test disruption."""
    return {
        "Accept": test["true_accept_cost"],
        "Switch": test["true_switch_cost"],
        "Expedite": test["true_expedite_cost"],
    }


# =====================================================================
# THE FOUR COMPARABILITY BANDS
# =====================================================================
CLOSE_DELAY_DAYS = 2        # "similar duration"
FAR_DELAY_DAYS = 7          # "very different duration"


def pool_everything(case, test):
    """No restriction beyond the cross-project rule."""
    return True


def band_1_near_identical(case, test):
    return (
        case["material"] == test["material"]
        and case["project_size"] == test["project_size"]
        and abs(case["delay_days"] - test["delay_days"]) <= CLOSE_DELAY_DAYS
    )


def band_2_different_duration(case, test):
    return (
        case["material"] == test["material"]
        and case["project_size"] == test["project_size"]
        and abs(case["delay_days"] - test["delay_days"]) >= FAR_DELAY_DAYS
    )


def band_3_different_material(case, test):
    return (
        case["material"] != test["material"]
        and case["project_size"] == test["project_size"]
    )


def band_4_nothing_in_common(case, test):
    return (
        case["material"] != test["material"]
        and case["project_size"] != test["project_size"]
        and abs(case["delay_days"] - test["delay_days"]) >= FAR_DELAY_DAYS
    )


# Each band is defined by WHAT THE AVAILABLE CASES HAVE IN COMMON with
# the new disruption - never by a similarity percentage. The percentage
# is then measured on whatever actually gets retrieved, so it is a
# result rather than a label we assigned in advance.
LEVELS = [
    ("1 Near-identical", band_1_near_identical,
     "same material, same job size, similar duration"),
    ("2 Different duration", band_2_different_duration,
     "same material, same job size, very different duration"),
    ("3 Different material", band_3_different_material,
     "different material, same job size"),
    ("4 Nothing in common", band_4_nothing_in_common,
     "different material, different job size, very different duration"),
]


# =====================================================================
# THE CROSS-PROJECT RULE
# =====================================================================
def build_pool(history, test, level_rule=None, projects="other"):
    """
    Decide which past cases the system is allowed to see for this test.

        "other" - only OTHER projects (the cross-project rule, default)
        "own"   - only THIS project's own history
        "any"   - everything

    `level_rule` optionally narrows it further by comparability.
    """
    pool = []
    for case in history:
        same_project = case["project_id"] == test["project_id"]
        if projects == "other" and same_project:
            continue
        if projects == "own" and not same_project:
            continue
        if level_rule is not None and not level_rule(case, test):
            continue
        pool.append(case)
    return pool


def usable_at_every_band(history, test):
    """True when every band can offer this test enough comparable cases."""
    return all(
        len(build_pool(history, test, rule, projects="other"))
        >= HOW_MANY_SIMILAR_CASES
        for _, rule, _ in LEVELS
    )


class BaselineFitter:
    """
    Fits the baseline from the database, obeying the cross-project rule.

    The baseline uses the WHOLE available database and ignores
    comparability, so it is fitted once per (project excluded, access
    condition) and reused. Caching it also keeps the run fast.
    """

    def __init__(self, history):
        self.history = history
        self._cache = {}

    def params_for(self, test, projects="other"):
        key = (test["project_id"], projects)
        if key not in self._cache:
            pool = build_pool(self.history, test, projects=projects)
            self._cache[key] = calculations.fit_baseline(pool)
        return self._cache[key]


# =====================================================================
# MEASURING ONE ESTIMATE AGAINST THE TRUTH
# =====================================================================
def measure(estimate, truth):
    """Average absolute error in euros across the three options."""
    return statistics.mean(abs(estimate[a] - truth[a]) for a in ACTIONS)


def evaluate_one(test, pool, params):
    """Run the system on one test disruption and mark the result."""
    truth = truth_of(test)
    disruption = {
        "material": test["material"],
        "delay_days": test["delay_days"],
        "project_size": test["project_size"],
    }

    retrieved = similarity.find_similar_cases(
        disruption, pool, top_n=HOW_MANY_SIMILAR_CASES
    )
    result = calculations.estimate_everything(
        test["material"], test["delay_days"], test["project_size"],
        retrieved, params
    )

    best = test["true_best_action"]

    return {
        "test_id": test["test_id"],
        "project_id": test["project_id"],
        "material": test["material"],
        "delay_days": test["delay_days"],
        "project_size": test["project_size"],
        "cases_used": len(retrieved),
        "cases_from_own_project": sum(
            1 for c in retrieved if c["project_id"] == test["project_id"]
        ),
        "projects_drawn_from": len({c["project_id"] for c in retrieved}),
        "measured_similarity": (
            round(statistics.mean(c["similarity"] for c in retrieved))
            if retrieved else 0
        ),
        "baseline_error": round(measure(result["baseline"], truth)),
        "history_error": round(measure(result["historical"], truth)),
        "blended_error": round(measure(result["blended"], truth)),
        "true_best_action": best,
        "baseline_recommendation": result["baseline_recommendation"],
        "blended_recommendation": result["recommendation"],
        "recommendation_changed": int(
            result["baseline_recommendation"] != result["recommendation"]
        ),
        "baseline_correct": int(result["baseline_recommendation"] == best),
        "blended_correct": int(result["recommendation"] == best),
    }


# =====================================================================
# EXPERIMENT 1 - THE FOUR COMPARABILITY BANDS
# =====================================================================
def run_experiment_1(tests, history):
    """
    Every test disruption, at every comparability band.

    The baseline is fitted from the whole cross-project database and is
    therefore the SAME at every band. That makes it a built-in control:
    any difference between bands must come from which cases were
    retrieved, and nothing else.
    """
    fitter = BaselineFitter(history)

    # --- Keep the design strictly paired -------------------------------
    # A test is only usable if EVERY band can offer it enough cases.
    # If we let each band use whatever tests it could serve, the bands
    # would be measured on different sets of disruptions and the
    # baseline would no longer be identical across rows - which is the
    # whole basis of the control. So we use the intersection.
    usable = []
    dropped = 0
    for test in tests:
        enough_everywhere = all(
            len(build_pool(history, test, rule, projects="other"))
            >= HOW_MANY_SIMILAR_CASES
            for _, rule, _ in LEVELS
        )
        if enough_everywhere:
            usable.append(test)
        else:
            dropped += 1

    rows = []
    for level_name, pool_rule, level_description in LEVELS:
        for test in usable:
            pool = build_pool(history, test, pool_rule, projects="other")
            row = evaluate_one(test, pool, fitter.params_for(test))
            row["level"] = level_name
            row["level_description"] = level_description
            row["pool_size"] = len(pool)
            rows.append(row)

    return rows, {"tested": len(usable), "dropped": dropped}


# =====================================================================
# EXPERIMENT 1b - OWN HISTORY vs A SHARED POOL
# =====================================================================
# The bands ask HOW ALIKE cases must be. This asks WHOSE they are.
#
# Each condition gets its own fitted baseline, from the same data it is
# allowed to retrieve from - because a contractor working alone would
# also have to build their generic rules from their own records.
#
# A site with too little history of its own is NOT skipped. It falls
# back to whatever it has, and that counts against it, because in real
# life it counts against it too.
# ---------------------------------------------------------------------
ACCESS_CONDITIONS = [
    ("Own site only", "own", "only this project's own past cases"),
    ("Other sites only", "other", "the shared pool, excluding this project"),
    ("Own + other sites", "any", "everything available"),
]


def run_experiment_access(tests, history):
    fitter = BaselineFitter(history)
    rows = []
    for condition_name, projects, description in ACCESS_CONDITIONS:
        for test in tests:
            pool = build_pool(history, test, projects=projects)
            if not pool:
                continue
            row = evaluate_one(test, pool, fitter.params_for(test, projects))
            row["condition"] = condition_name
            row["condition_description"] = description
            row["pool_size"] = len(pool)
            rows.append(row)
    return rows


# =====================================================================
# REPORTING
# =====================================================================
def money(amount):
    return f"€{amount:,.0f}"


def summarise(rows):
    return {
        "n": len(rows),
        "similarity": statistics.mean(r["measured_similarity"] for r in rows),
        "pool": statistics.mean(r.get("pool_size", 0) for r in rows),
        "baseline_error": statistics.mean(r["baseline_error"] for r in rows),
        "blended_error": statistics.mean(r["blended_error"] for r in rows),
        "history_error": statistics.mean(r["history_error"] for r in rows),
        "baseline_accuracy": statistics.mean(r["baseline_correct"] for r in rows),
        "blended_accuracy": statistics.mean(r["blended_correct"] for r in rows),
        "changed": statistics.mean(r["recommendation_changed"] for r in rows),
    }


def bar(value, biggest, width=26):
    if biggest <= 0:
        return ""
    return "#" * max(1, int(round(width * value / biggest)))


def print_bands(rows, skipped, title, explain=True):
    print("\n" + "=" * 78)
    print(title)
    print("=" * 78)

    if explain:
        print(
            "\nSame test disruptions at every band. Only the comparability of\n"
            "the cases the system may retrieve changes.\n"
            "\nThe baseline uses the whole cross-project database and ignores\n"
            "comparability, so its error is identical at every band. That is\n"
            "the control: any difference between rows is caused by WHICH\n"
            "cases were retrieved and nothing else.\n"
        )

    groups = {}
    for row in rows:
        groups.setdefault(row["level"], []).append(row)

    print(f"{'Band':<22}{'pool':>6}{'similarity':>12}{'baseline':>11}"
          f"{'with history':>14}{'change':>9}")
    print("-" * 78)

    summaries = {}
    for level_name, _, description in LEVELS:
        group = groups.get(level_name)
        if not group:
            continue
        s = summarise(group)
        summaries[level_name] = s
        change = (s["blended_error"] - s["baseline_error"]) / s["baseline_error"]
        print(f"{level_name:<22}{s['pool']:>6.0f}{s['similarity']:>11.0f}%"
              f"{money(s['baseline_error']):>11}{money(s['blended_error']):>14}"
              f"{change:>+9.0%}")

    for level_name, _, description in LEVELS:
        if level_name in groups:
            print(f"\n   {level_name}: {description}")

    if skipped:
        print(f"\n{skipped['tested']} test disruptions were used at every band. "
              f"{skipped['dropped']} were dropped\nbecause at least one band "
              "could not offer them three cases; using them\nwould have "
              "measured different bands on different disruptions.")

    cross = [r for r in rows if r["cases_from_own_project"] > 0]
    print(f"\nLeakage check: {len(cross)} retrieved cases came from the test's "
          "own project (must be 0).")

    baselines = {round(s["baseline_error"]) for s in summaries.values()}
    print(f"Control check: baseline error identical at every band? "
          f"{'YES' if len(baselines) == 1 else 'NO - ' + str(baselines)}")

    if summaries:
        print("\nAVERAGE ESTIMATION ERROR BY BAND")
        biggest = max(max(s["blended_error"] for s in summaries.values()),
                      max(s["baseline_error"] for s in summaries.values()))
        for level_name, _, _ in LEVELS:
            if level_name not in summaries:
                continue
            s = summaries[level_name]
            print(f"   {level_name:<21} {bar(s['blended_error'], biggest):<28}"
                  f" {money(s['blended_error'])}")
        any_summary = next(iter(summaries.values()))
        print(f"   {'baseline (no comparability)':<21} "
              f"{bar(any_summary['baseline_error'], biggest):<28}"
              f" {money(any_summary['baseline_error'])}")

    return summaries


def print_decision_metrics(rows):
    print("\nDECISION QUALITY BY BAND")
    print(f"{'Band':<22}{'recommends cheapest':>21}{'advice changed':>17}")
    print("-" * 78)

    groups = {}
    for row in rows:
        groups.setdefault(row["level"], []).append(row)

    first = None
    for level_name, _, _ in LEVELS:
        group = groups.get(level_name)
        if not group:
            continue
        s = summarise(group)
        first = first or s
        print(f"{level_name:<22}{s['blended_accuracy']:>20.0%}"
              f"{s['changed']:>17.0%}")
    if first:
        print(f"{'baseline (no history)':<22}{first['baseline_accuracy']:>20.0%}"
              f"{'-':>17}")
    print(
        "\nNote: euro error is where the effect shows. How often the\n"
        "cheapest option is recommended moves far less, because when the\n"
        "system is wrong the two best options are often nearly tied."
    )


def print_access(rows):
    print("\n" + "=" * 78)
    print("EXPERIMENT 1b - OWN HISTORY vs A SHARED POOL")
    print("=" * 78)
    print(
        "\nDoes a contractor need anyone else's data, or is their own enough?\n"
        "Each condition builds BOTH its baseline and its retrieved cases from\n"
        "the same data, because a contractor working alone would have to do\n"
        "the same.\n"
    )

    groups = {}
    for row in rows:
        groups.setdefault(row["condition"], []).append(row)

    print(f"{'Condition':<22}{'pool':>7}{'similarity':>12}{'baseline':>11}"
          f"{'with history':>14}{'change':>9}")
    print("-" * 78)

    for condition_name, _, description in ACCESS_CONDITIONS:
        group = groups.get(condition_name)
        if not group:
            continue
        s = summarise(group)
        change = (s["blended_error"] - s["baseline_error"]) / s["baseline_error"]
        print(f"{condition_name:<22}{s['pool']:>7.0f}{s['similarity']:>11.0f}%"
              f"{money(s['baseline_error']):>11}{money(s['blended_error']):>14}"
              f"{change:>+9.0%}")

    leaked = sum(
        r["cases_from_own_project"] for r in groups.get("Other sites only", [])
    )
    print(f"\nLeakage check on the pooled condition: {leaked} own-project "
          "cases used (must be 0).")
    return groups


def print_control(summaries_real, summaries_control):
    print("\n" + "=" * 78)
    print("CONTROL - THE SAME METHOD WITH THE MATERIAL LABELS SHUFFLED")
    print("=" * 78)
    print(
        "\nOur dataset assumes disruption costs are driven by duration, project\n"
        "scale and material. A fair critic will say we planted that pattern\n"
        "and then found it.\n"
        "\nSo we shuffled the material labels in the database. Every case keeps\n"
        "its real cost and its real delay - only the label saying WHICH\n"
        "material it was becomes meaningless.\n"
        "\nIf our result comes from genuine comparability, the gap between the\n"
        "same-material and different-material bands should collapse.\n"
    )

    print(f"{'Band':<22}{'real data':>14}{'labels shuffled':>18}")
    print("-" * 78)
    for level_name, _, _ in LEVELS:
        real = summaries_real.get(level_name)
        control = summaries_control.get(level_name)
        if not real or not control:
            continue
        real_change = (real["blended_error"] - real["baseline_error"]) / real["baseline_error"]
        ctrl_change = (control["blended_error"] - control["baseline_error"]) / control["baseline_error"]
        print(f"{level_name:<22}{real_change:>+13.0%}{ctrl_change:>+17.0%}")

    first, third = LEVELS[0][0], LEVELS[2][0]
    if all(k in summaries_real for k in (first, third)) and \
       all(k in summaries_control for k in (first, third)):
        def gap(s):
            a = (s[first]["blended_error"] - s[first]["baseline_error"]) / s[first]["baseline_error"]
            b = (s[third]["blended_error"] - s[third]["baseline_error"]) / s[third]["baseline_error"]
            return abs(b - a)
        real_gap, ctrl_gap = gap(summaries_real), gap(summaries_control)
        print(f"\nGap between 'same material' and 'different material':")
        print(f"   real data:        {real_gap:.0%}")
        print(f"   labels shuffled:  {ctrl_gap:.0%}")
        if ctrl_gap < real_gap * 0.35:
            print("\n-> The gap collapses when the labels are meaningless, so the\n"
                  "   method is responding to the material label rather than\n"
                  "   producing improvement regardless of what it retrieves.\n"
                  "\n   WHAT THIS DOES NOT SHOW: that material really does drive\n"
                  "   disruption cost. We assumed that and built the data from it.\n"
                  "   This rules out an artifact in the method; it cannot validate\n"
                  "   the premise. Only the published lead-time data the material\n"
                  "   parameters are derived from speaks to that.")
        else:
            print("\n-> The gap SURVIVES label shuffling. The method is responding\n"
                  "   to something other than material comparability, and the\n"
                  "   headline result should not be trusted as stated.")


def print_summary(summaries, access_groups, control_summaries):
    """Every sentence here is chosen by the numbers, not written ahead."""
    print("\n" + "=" * 78)
    print("SUMMARY - generated from the results above")
    print("=" * 78)

    best = summaries.get(LEVELS[0][0])
    worst = summaries.get(LEVELS[-1][0])

    if best:
        change = best["baseline_error"] - best["blended_error"]
        share = change / best["baseline_error"]
        verb = "reduced" if change > 0 else "increased"
        print(
            f"\nWhen the available cases were near-identical (measured at "
            f"{best['similarity']:.0f}%\nsimilarity), using only the comparable "
            f"ones {verb} the average\ncost-estimation error by "
            f"{money(abs(change))}, or {abs(share):.0%}, against using the\n"
            f"whole database without regard to comparability."
        )

    if best and worst:
        worst_share = (worst["baseline_error"] - worst["blended_error"]) / worst["baseline_error"]
        print(
            f"\nWhen the available cases had nothing in common (measured at "
            f"{worst['similarity']:.0f}%),\nthat benefit was "
            f"{worst_share:+.0%}."
        )

    own = access_groups.get("Own site only")
    pooled = access_groups.get("Other sites only")
    if own and pooled:
        own_s, pooled_s = summarise(own), summarise(pooled)
        own_gain = (own_s["baseline_error"] - own_s["blended_error"]) / own_s["baseline_error"]
        pooled_gain = (pooled_s["baseline_error"] - pooled_s["blended_error"]) / pooled_s["baseline_error"]
        print(
            f"\nA contractor using only their own site's history retrieved cases "
            f"at\n{own_s['similarity']:.0f}% similarity and gained {own_gain:+.0%}. "
            f"Using the shared pool of other\nsites, they retrieved at "
            f"{pooled_s['similarity']:.0f}% and gained {pooled_gain:+.0%}."
        )

    top, third = LEVELS[0][0], LEVELS[2][0]
    if all(k in summaries for k in (top, third)) and \
       all(k in control_summaries for k in (top, third)):
        def gap(s):
            a = (s[top]["blended_error"] - s[top]["baseline_error"]) / s[top]["baseline_error"]
            b = (s[third]["blended_error"] - s[third]["baseline_error"]) / s[third]["baseline_error"]
            return abs(b - a)
        print(
            f"\nControl: with the material labels shuffled so they mean nothing,\n"
            f"the gap between the same-material and different-material bands\n"
            f"falls from {gap(summaries):.0%} to {gap(control_summaries):.0%}."
        )

    print("\nSynthetic prototype data - for experimentation only.")


# =====================================================================
# APPENDIX EXPERIMENTS (run with --appendix)
# =====================================================================
def run_appendix(tests, history):
    """
    Two supporting experiments, kept out of the main report to keep it
    focused: which single characteristic matters most, and how much the
    blend should trust history.
    """
    fitter = BaselineFitter(history)

    print("\n" + "=" * 78)
    print("APPENDIX A - HOW MUCH SHOULD THE BLEND TRUST COMPARABLE CASES?")
    print("=" * 78)
    print(f"\n{'weight':>8}{'Band 1 error':>16}{'Band 4 error':>16}")
    print("-" * 78)

    original = calculations.BLEND_WEIGHT_HISTORY
    try:
        for weight in [0.0, 0.25, 0.5, 0.75, 1.0]:
            calculations.BLEND_WEIGHT_HISTORY = weight
            measured = {}
            for label, rule in [("B1", band_1_near_identical),
                                ("B4", band_4_nothing_in_common)]:
                per_test = []
                for test in tests:
                    pool = build_pool(history, test, rule, projects="other")
                    if len(pool) < HOW_MANY_SIMILAR_CASES:
                        continue
                    per_test.append(
                        evaluate_one(test, pool, fitter.params_for(test))
                    )
                measured[label] = statistics.mean(
                    r["blended_error"] for r in per_test
                )
            print(f"{weight:>7.0%}{money(measured['B1']):>16}"
                  f"{money(measured['B4']):>16}")
    finally:
        calculations.BLEND_WEIGHT_HISTORY = original

    print(
        "\nTrusting comparable cases more helps in one column and hurts in\n"
        "the other. The 50/50 blend is a hedge against not knowing which\n"
        "situation you are in."
    )


# =====================================================================
# SAVING
# =====================================================================
def save_csv(rows, file_path):
    if not rows:
        return
    folder = os.path.dirname(file_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


def main():
    here = os.path.dirname(os.path.abspath(__file__))
    data_folder = os.path.join(here, "data")

    history = database.load_cases()
    tests = make_test_disruptions(history=history)

    print("=" * 78)
    print("  EVALUATION EXPERIMENT")
    print("  Synthetic prototype data - for experimentation only")
    print("=" * 78)
    print(f"\nHistorical cases:      {len(history)}")
    print(f"Projects:              {len(PROJECTS)}")
    print(f"New test disruptions:  {len(tests)}")
    print("Cross-project rule:    ENFORCED for retrieval AND for fitting "
          "the baseline")
    print(f"Similarity weights:    "
          f"{similarity.WEIGHT_MATERIAL:.0%} material / "
          f"{similarity.WEIGHT_DELAY:.0%} delay / "
          f"{similarity.WEIGHT_PROJECT_SIZE:.0%} job size  "
          f"(prototype assumption)")

    example = calculations.fit_baseline(history)
    print("\nBaseline rules fitted from the database (no invented constants):")
    for size in calculations.PROJECT_SIZES:
        p = example[size]
        print(f"   {size:<7} accept {money(p['accept_per_day'])}/day   "
              f"switch {money(p['switch_flat'])} flat   "
              f"expedite {money(p['expedite_per_day'])}/day")

    results_1, skipped = run_experiment_1(tests, history)
    summaries = print_bands(
        results_1, skipped, "EXPERIMENT 1 - DOES COMPARABILITY MATTER?"
    )
    print_decision_metrics(results_1)

    results_access = run_experiment_access(tests, history)
    access_groups = print_access(results_access)

    # --- The control run ----------------------------------------------
    # Same tests, same everything - only the material labels in the
    # database are shuffled so they no longer mean anything.
    control_rows, _ = run_experiment_1(tests, shuffle_materials(history))
    control_summaries = {}
    groups = {}
    for row in control_rows:
        groups.setdefault(row["level"], []).append(row)
    for level_name, _, _ in LEVELS:
        if level_name in groups:
            control_summaries[level_name] = summarise(groups[level_name])

    print_control(summaries, control_summaries)
    print_summary(summaries, access_groups, control_summaries)

    if "--appendix" in sys.argv:
        run_appendix(tests, history)

    save_csv(tests, os.path.join(data_folder, "test_cases.csv"))
    save_csv(results_1, os.path.join(data_folder, "evaluation_results.csv"))
    save_csv(results_access, os.path.join(data_folder, "access_results.csv"))
    save_csv(control_rows, os.path.join(data_folder, "control_results.csv"))

    print("\nSaved:")
    print("   data/test_cases.csv          the test disruptions and true costs")
    print("   data/evaluation_results.csv  the four bands, one row per test")
    print("   data/access_results.csv      own vs pooled history")
    print("   data/control_results.csv     the material-shuffled control run")
    print()


if __name__ == "__main__":
    main()
