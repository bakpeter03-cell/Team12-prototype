"""
data_generator.py
=================

PURPOSE
-------
This file creates the SYNTHETIC HISTORICAL DATABASE for our prototype.

Think of this file as "the world". It is a small simulated construction
world in which we know everything: for every disruption we know exactly
what the Accept / Switch / Expedite options would have cost.

In real life a contractor could never know this. Because our world is
simulated, we DO know it, and that is what makes our experiment possible:
we can compare what our system *estimates* against what the simulated
truth *actually is*.

IMPORTANT
---------
Nothing in this file is real construction industry data.
All numbers are invented for experimentation only.

HOW TO RUN IT
-------------
    python3 data_generator.py

It writes the file:  data/historical_cases.csv

This file only uses tools that come with Python itself, so you do not
need to install anything to run it.
"""

import csv
import os
import random

# ---------------------------------------------------------------------
# We fix the "random seed" so the data is the same every time we run it.
# This means your results are reproducible, which matters for a report.
# ---------------------------------------------------------------------
RANDOM_SEED = 42

NUMBER_OF_CASES = 400

# ---------------------------------------------------------------------
# THE HIDDEN RULES OF OUR SIMULATED WORLD
# ---------------------------------------------------------------------
# These are the "physics" of our world. Our prototype's baseline
# calculator will NOT know these numbers. Only the simulator knows them.
#
# For each material we define:
#   delay_cost_multiplier  - how painful a delay in this material is.
#                            Structural steel holds up everything after it,
#                            so it hurts more. Concrete is easier to work
#                            around, so it hurts a bit less.
#   switch_base_cost       - roughly what it costs to change supplier
#                            (new order, new price, re-approval, admin).
#   switch_residual_days   - even after switching, some delay remains,
#                            because the new supplier also needs time.
#   expedite_cost_per_day  - price of buying back ONE day (air freight,
#                            overtime at the factory, priority production).
#   expedite_recovery      - what share of the delay expediting can remove
#                            at most. Some items simply cannot be rushed.
# ---------------------------------------------------------------------
# ---------------------------------------------------------------------
# PUBLISHED LEAD TIMES - THE ONE THING WE DID NOT INVENT
# ---------------------------------------------------------------------
# These are procurement lead times in WEEKS, taken from published
# industry sources. They are the empirical anchor of the whole
# simulation: every difference between materials below is derived from
# them by a stated formula, rather than chosen by us.
#
#   Concrete and masonry      1-4 wks    Terrapin Construction Group,
#   Roofing membrane          3-10 wks   "Commercial Construction Material
#   Structural steel         14-20 wks    Lead Times", July 2026
#   Medium-voltage switchgear 52-80 wks
#     https://terrapincg.com/news/commercial-construction-material-lead-times-2026
#
#   Lighting                  8-16 wks   Cresa, "Strategies to Optimize
#   Rooftop HVAC units       30-45 wks    Lead Times for a Successful
#   Fabricated steel         20-25 wks    Construction Project"
#   Switchgear               45-60 wks
#     https://www.cresa.com/Blog/2023-Optimize-Lead-Times
#
# Where the two sources overlap we use the union of their ranges.
# ---------------------------------------------------------------------
MATERIAL_LEAD_TIME_WEEKS = {
    "Concrete & masonry":    (1, 4),
    "Roofing membrane":      (3, 10),
    "Lighting":              (8, 16),
    "Structural steel":      (14, 25),
    "HVAC rooftop units":    (30, 45),
    "Electrical switchgear": (45, 80),
}


def derive_material_rules():
    """
    Turn published lead times into the simulator's material parameters.

    THE LOGIC, in one sentence each:

      A material that takes longer to procure is harder to replace, so
      MORE delay remains after switching supplier.

      A material that takes longer to procure is harder to rush, so LESS
      of the delay can be bought back by expediting.

      A material that takes longer to procure is more specialised, so
      switching supplier costs more and expediting costs more per day.

    Each material is placed on a 0-to-1 scale by its midpoint lead time,
    then the parameters are read off linear rules. The rules and their
    endpoints are ours; the ORDERING and the SPACING come from the
    published data.

    Note that lead times run from weeks to well over a year while our
    disruptions run 1-15 days. We are mapping the published ORDERING
    onto the prototype's scale, not claiming these are literal delays.
    """
    midpoints = {
        name: (low + high) / 2
        for name, (low, high) in MATERIAL_LEAD_TIME_WEEKS.items()
    }
    shortest, longest = min(midpoints.values()), max(midpoints.values())

    rules = {}
    for name, midpoint in midpoints.items():
        # 0.0 for the quickest material, 1.0 for the slowest
        position = (midpoint - shortest) / (longest - shortest)

        rules[name] = {
            # How painful a delay in this material is, per day.
            # SET TO 1.0 FOR EVERY MATERIAL. We could argue that some
            # materials sit on the critical path and hurt more, but we
            # found no published figure for it, so rather than invent
            # one we removed the assumption entirely. Material therefore
            # affects only switching and expediting, both of which are
            # derived from cited lead times.
            "delay_cost_multiplier": 1.00,

            # Days of delay still remaining after switching supplier.
            "switch_residual_days": int(round(1 + 3 * position)),

            # Share of the delay that expediting can buy back.
            "expedite_recovery": round(0.90 - 0.30 * position, 2),

            # One-off cost of switching supplier.
            "switch_base_cost": int(round(10000 + 40000 * position)),

            # Premium paid per day of delay bought back.
            "expedite_cost_per_day": int(round(2500 + 4000 * position)),

            "lead_time_weeks": MATERIAL_LEAD_TIME_WEEKS[name],
        }
    return rules


MATERIALS = derive_material_rules()

# ---------------------------------------------------------------------
# PROJECT SIZE
# ---------------------------------------------------------------------
# "Project size" in our prototype means the ECONOMIC weight of the
# project, not the size of the company.
#
#   base_daily_delay_cost - how much one lost day costs on this project.
#   commercial_scale      - bigger projects buy bigger quantities, so
#                           switching and expediting also cost more.
# ---------------------------------------------------------------------
# The daily cost of delay rises steeply with the value of the project.
# Published liquidated-damages schedules (US sources, quoted in USD as
# published) show roughly a tenfold spread
# from the smallest to the largest contract bracket:
#
#   Alabama DOT (2002)   $120/day under $100k  ->  $1,200/day over $10M
#   Florida DOT (2008)   $544/day              ->  $8,624/day
#   Georgia DOT (2008)   $75/day               ->  $2,100/day
#     Auburn University Highway Research Center, project 930-656,
#     "Development of a Procedure for Updating Liquidated Damages"
#     https://eng.auburn.edu/files/centers/hrc/930-656.pdf
#
# We adopt that tenfold spread. The ABSOLUTE level here is higher than
# those schedules because liquidated damages are what an owner charges
# a contractor - deliberately set low enough to stay enforceable - and
# not the contractor's own internal cost of a lost day, which also
# includes idle crews, extended site overhead and knock-on trades.
# The shape is sourced; the level is our assumption.
PROJECT_SIZES = {
    "Small":  {"base_daily_delay_cost": 1000,  "commercial_scale": 0.6},
    "Medium": {"base_daily_delay_cost": 3500,  "commercial_scale": 1.0},
    "Large":  {"base_daily_delay_cost": 10000, "commercial_scale": 1.4},
}

# ---------------------------------------------------------------------
# THE PROJECTS
# ---------------------------------------------------------------------
# Every disruption happens ON a project. This matters for our research
# question, which is about whether knowledge moves BETWEEN projects.
#
#   project_size   - a property of the project itself, not of the
#                    individual disruption.
#   project_effect - everything permanent about this project that we did
#                    not model: how good the site team is, how far it is
#                    from the suppliers, how strict the client is, how
#                    much float the programme has. A project with 1.08
#                    is 8% more expensive to be disrupted on than
#                    average, in every single one of its disruptions.
#
# This is the honest reason cross-project transfer is hard. If projects
# were identical apart from their size, "learning from another project"
# would be free. They are not, so it costs something - and measuring
# what it costs is the point of the experiment.
#
# These values are invented. They are a modelling assumption, not a
# measurement of real construction projects.
# ---------------------------------------------------------------------
PROJECT_COUNT = 20


def build_projects():
    """
    Create the portfolio of projects.

    Sizes cycle Small / Medium / Large so every size is well represented,
    and the project effect is spread evenly from 0.90 to 1.10. Because
    the sizes cycle every three while the effect rises steadily, no size
    ends up systematically cheaper or dearer than another.
    """
    sizes = ["Small", "Medium", "Large"]
    projects = {}
    for index in range(PROJECT_COUNT):
        share = index / (PROJECT_COUNT - 1)          # 0.0 up to 1.0
        projects[f"P{index + 1:02d}"] = {
            "project_size": sizes[index % 3],
            "project_effect": round(0.90 + 0.20 * share, 3),
        }
    return projects


PROJECTS = build_projects()

MIN_DELAY_DAYS = 1
MAX_DELAY_DAYS = 15

# How often the manager in our simulated history actually picked the
# cheapest option. Real managers are not perfect, and we want our history
# to contain some imperfect decisions too.
PROBABILITY_MANAGER_PICKS_BEST = 0.75

ACTIONS = ["Accept", "Switch", "Expedite"]


def round_to_hundred(amount):
    """Round a money amount to the nearest €100 so the numbers look tidy."""
    return int(round(amount / 100.0) * 100)


def simulate_true_costs(material, delay_days, project_size, rng,
                        project_effect=1.0):
    """
    THE HEART OF THE SIMULATOR.

    Given one disruption, work out what each of the three responses
    would truly cost in our simulated world.

    `project_effect` is the permanent character of the project this
    disruption happened on (see PROJECTS above). Leave it at 1.0 for an
    average project.

    Returns a dictionary:
        {"Accept": ..., "Switch": ..., "Expedite": ..., "daily_delay_cost": ...}
    """
    material_rules = MATERIALS[material]
    size_rules = PROJECT_SIZES[project_size]

    # --- Step 1: what does one lost day cost on THIS disruption? --------
    # Base cost from the project size, adjusted by how critical the
    # material is, by the permanent character of this project, plus a
    # small random amount of "this particular job was a bit
    # better/worse than usual".
    daily_delay_cost = (
        size_rules["base_daily_delay_cost"]
        * material_rules["delay_cost_multiplier"]
        * project_effect
        * rng.uniform(0.90, 1.10)
    )

    # --- Step 2: ACCEPT THE DELAY ---------------------------------------
    # You do nothing. You simply pay for every lost day.
    accept_cost = delay_days * daily_delay_cost

    # --- Step 3: SWITCH SUPPLIER ----------------------------------------
    # You pay a one-off switching cost, and you still lose a few days
    # because the new supplier needs time as well.
    switch_residual_days = min(material_rules["switch_residual_days"], delay_days)
    switch_cost = (
        material_rules["switch_base_cost"]
        * size_rules["commercial_scale"]
        * project_effect
        * rng.uniform(0.85, 1.15)
        + switch_residual_days * daily_delay_cost
    )

    # --- Step 4: EXPEDITE -----------------------------------------------
    # You pay a premium per day that you buy back. You cannot always buy
    # back the whole delay, so some days remain.
    days_recovered = int(delay_days * material_rules["expedite_recovery"])
    expedite_residual_days = delay_days - days_recovered
    expedite_cost = (
        material_rules["expedite_cost_per_day"]
        * size_rules["commercial_scale"]
        * project_effect
        * days_recovered
        * rng.uniform(0.85, 1.15)
        + expedite_residual_days * daily_delay_cost
    )

    return {
        "Accept": round_to_hundred(accept_cost),
        "Switch": round_to_hundred(switch_cost),
        "Expedite": round_to_hundred(expedite_cost),
        "daily_delay_cost": round_to_hundred(daily_delay_cost),
    }


def make_one_case(case_number, rng):
    """Invent one random disruption and work out everything about it."""
    # Every disruption happens on one of our twelve projects. The project
    # decides the project size and carries its own permanent character.
    project_id = rng.choice(list(PROJECTS.keys()))
    project = PROJECTS[project_id]
    project_size = project["project_size"]

    material = rng.choice(list(MATERIALS.keys()))
    delay_days = rng.randint(MIN_DELAY_DAYS, MAX_DELAY_DAYS)

    costs = simulate_true_costs(
        material, delay_days, project_size, rng, project["project_effect"]
    )

    # The cheapest of the three options is the "optimal action".
    optimal_action = min(ACTIONS, key=lambda action: costs[action])

    # The manager usually, but not always, chose the cheapest option.
    if rng.random() < PROBABILITY_MANAGER_PICKS_BEST:
        chosen_action = optimal_action
    else:
        other_actions = [a for a in ACTIONS if a != optimal_action]
        chosen_action = rng.choice(other_actions)

    # What the contractor actually paid is the cost of what they chose.
    actual_cost = costs[chosen_action]

    return {
        "case_id": f"{case_number:03d}",
        "project_id": project_id,
        "material": material,
        "delay_days": delay_days,
        "project_size": project_size,
        "accept_cost": costs["Accept"],
        "switch_cost": costs["Switch"],
        "expedite_cost": costs["Expedite"],
        "optimal_action": optimal_action,
        "chosen_action": chosen_action,
        "actual_cost": actual_cost,
    }


COLUMNS = [
    "case_id",
    "project_id",
    "material",
    "delay_days",
    "project_size",
    "accept_cost",
    "switch_cost",
    "expedite_cost",
    "optimal_action",
    "chosen_action",
    "actual_cost",
]


def generate_cases(how_many=NUMBER_OF_CASES, seed=RANDOM_SEED):
    """Build a list of disruption cases."""
    rng = random.Random(seed)
    return [make_one_case(i, rng) for i in range(1, how_many + 1)]


def save_cases(cases, file_path):
    """Write the list of cases into a CSV file."""
    folder = os.path.dirname(file_path)
    if folder:
        os.makedirs(folder, exist_ok=True)
    with open(file_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(cases)


def print_summary(cases):
    """Print a short report so we can see the data makes sense."""
    print(f"\nGenerated {len(cases)} historical disruption cases.\n")

    print("How often each action was the cheapest (the 'optimal action'):")
    for action in ACTIONS:
        count = sum(1 for c in cases if c["optimal_action"] == action)
        print(f"  {action:<9} {count:>3} cases  ({count / len(cases):.0%})")

    followed = sum(1 for c in cases if c["chosen_action"] == c["optimal_action"])
    print(f"\nManager chose the cheapest option in {followed} of {len(cases)} cases.")

    costs = [c["actual_cost"] for c in cases]
    print(f"Actual cost range: €{min(costs):,} to €{max(costs):,}")

    print(f"\nCases per project (across {len(PROJECTS)} projects):")
    per_project = []
    for project_id in PROJECTS:
        count = sum(1 for c in cases if c["project_id"] == project_id)
        per_project.append(f"{project_id}: {count}")
    print("  " + "   ".join(per_project))

    print("\nFirst 10 rows:")
    header = (f"{'id':<5}{'proj':<6}{'material':<22}{'days':>5}{'size':>8}"
              f"{'accept':>10}{'switch':>10}{'expedite':>10}{'optimal':>10}"
              f"{'chosen':>10}{'actual':>10}")
    print(header)
    print("-" * len(header))
    for c in cases[:10]:
        print(
            f"{c['case_id']:<5}{c['project_id']:<6}{c['material']:<22}"
            f"{c['delay_days']:>5}{c['project_size']:>8}"
            f"{c['accept_cost']:>10,}{c['switch_cost']:>10,}{c['expedite_cost']:>10,}"
            f"{c['optimal_action']:>10}{c['chosen_action']:>10}{c['actual_cost']:>10,}"
        )


if __name__ == "__main__":
    # Always save next to this script, so it works no matter where you
    # run the command from.
    here = os.path.dirname(os.path.abspath(__file__))
    output_path = os.path.join(here, "data", "historical_cases.csv")

    cases = generate_cases()
    save_cases(cases, output_path)
    print_summary(cases)
    print(f"\nSaved to: {output_path}")

    print("\nSynthetic prototype data - for experimentation only.")
