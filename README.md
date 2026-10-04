# AI Procurement-Risk Agent — Prototype and Comparability Experiment

**Synthetic prototype data — for experimentation only.**
No real construction industry data is used anywhere in this project.

---

## 1. What this project is

A university course prototype of a decision-support tool for small and
mid-size general contractors.

When a supplier delivery is delayed, the contractor has three options:
**accept** the delay, **switch** supplier, or **expedite** delivery. The
prototype estimates what each would cost and recommends one. Every
resolved disruption is then stored, so the database grows.

## 2. The assumption we test

> Can historical procurement disruptions from one project provide useful
> information for a new disruption on another project, when the
> characteristics of the projects differ?

The software is not the valuable thing. The accumulating pile of past
disruptions is. But that pile is only worth having if knowledge actually
travels between projects, and nobody has shown that it does.

The experiment compares two ways of using the same database:

| | Uses |
|---|---|
| **Baseline** | the whole database, ignoring comparability entirely |
| **System** | only the most comparable cases |

So the question becomes: **does it matter which past cases you use, or is
any history as good as any other?**

## 3. Installing and running

```
cd ~/Documents/procurement-prototype
pip3 install -r requirements.txt
```

```
python3 data_generator.py     # build the simulated history
python3 evaluation.py         # run the experiments
streamlit run app.py          # the three-page interface
```

`data_generator.py` and `evaluation.py` need nothing installed — they use
only what comes with Python. The app needs the packages above.

A browser tab opens by itself. Leave the Terminal running while you use
the app; `Ctrl + C` stops it.

## 4. What each file does

| File | What it is for |
|---|---|
| `data_generator.py` | The simulated world. Knows the hidden rules. Writes 400 cases across 20 projects. |
| `calculations.py` | The estimates: baseline fitted from the database, correction from comparable cases, and the blend. |
| `similarity.py` | How comparable two disruptions are, and retrieval of the closest cases. |
| `database.py` | Reads the CSV and appends new cases. |
| `evaluation.py` | The experiments. This is the research contribution. |
| `app.py` | The three-page interface. Contains no new logic. |

Data files: `historical_cases.csv` (the knowledge base), `test_cases.csv`,
`evaluation_results.csv`, `access_results.csv`, `control_results.csv`.

## 5. How the synthetic data is generated

Real disruption records sit inside contractors' businesses and are not
available to us, so we fabricated a set that reflects how delays behave.
This is the data our venture would accumulate from contractors over time;
we created it up front so the idea could be tested now.

Because we built the world, we know what all three options truly cost for
every case — which is what makes measuring the error possible. In reality
you only ever learn the cost of the option you took.

### The material parameters are derived from published lead times

This is the one part of the simulation we did not invent. Procurement
lead times are published; we use them as the empirical anchor and derive
every difference between materials from them by a stated formula.

| Material | Published lead time | Switch fee | Days still lost after switching | Expedite €/day | Delay recoverable |
|---|---|---|---|---|---|
| Concrete & masonry | 1–4 wks | €10,000 | 1 | €2,500 | 90% |
| Roofing membrane | 3–10 wks | €12,667 | 1 | €2,767 | 88% |
| Lighting | 8–16 wks | €16,333 | 1 | €3,133 | 85% |
| Structural steel | 14–25 wks | €21,333 | 2 | €3,633 | 82% |
| HVAC rooftop units | 30–45 wks | €33,333 | 3 | €4,833 | 72% |
| Electrical switchgear | 45–80 wks | €50,000 | 4 | €6,500 | 60% |

The reasoning, one line each: a material that takes longer to procure is
**harder to replace** (more delay remains after switching), **harder to
rush** (less of the delay is recoverable), and **more specialised**
(switching and expediting both cost more). Each material is placed on a
0–1 scale by its midpoint lead time and the parameters read off linear
rules. The *ordering and spacing* come from the published data; the rule
endpoints are ours. Lead times run to well over a year while our
disruptions run 1–15 days, so we map the published ordering onto the
prototype's scale rather than claiming these are literal delays.

**We removed the material criticality multiplier.** An earlier version
assumed some materials hurt more per day of delay because they sit on the
critical path. We found no published figure for it, so rather than invent
one we set it to 1.00 for every material. Material now affects only
switching and expediting, both derived from citations. The headline result
barely moved when we did this (−44% became −42%), so it does not depend on
the parameter we could not source.

### Daily delay cost by project size

Published liquidated-damages schedules (US sources, quoted in USD as published) show roughly a **tenfold spread**
from the smallest to the largest contract bracket:

| Source | Smallest bracket | Largest bracket |
|---|---|---|
| Alabama DOT (2002) | $120/day under $100k | $1,200/day over $10M |
| Florida DOT (2008) | $544/day | $8,624/day |
| Georgia DOT (2008) | $75/day | $2,100/day |

We adopt that tenfold spread: **€1,000 / €3,500 / €10,000** per lost day
for Small / Medium / Large. The *shape* is sourced. The *level* is our
assumption, and deliberately higher than those schedules, because
liquidated damages are what an owner charges a contractor — set low enough
to stay enforceable — not the contractor's own internal cost of a lost
day, which also includes idle crews, extended site overhead and knock-on
trades.

### The remaining invented parameters

- Each of the 20 projects carries a permanent multiplier between 0.90 and
  1.10, standing in for site team quality, distance to suppliers,
  programme float and client strictness. Unsourced modelling assumption.
- ±10% per-case noise, representing everything not modelled.
- The 40/30/30 similarity weights.

**Accept** = days × daily cost. **Switch** = a one-off fee (larger on
bigger jobs) plus the days still lost while the new supplier ramps up.
**Expedite** = a premium per day bought back, plus the days that could not
be recovered — concrete can recover ~90% of a delay, switchgear only ~60%.

In the current 400-case dataset the cheapest option is Accept 44% of the
time, Switch 42% and Expedite 14%, so all three occur. Expediting is rarely
worth it on small projects — paying a rush premium on a job losing €1,000 a
day seldom pays — which is a consequence of the sourced parameters rather
than something we tuned for. The
simulated manager picks the cheapest option about 75% of the time. A fixed
random seed makes every run reproducible.

## 6. The three estimates

### The baseline — the whole database, no comparability

**Every baseline constant is a plain average taken from the historical
database itself.** Nothing is invented and nothing comes from inside the
simulator. You could reproduce any of these in a spreadsheet:

| Project size | Accept | Switch | Expedite |
|---|---|---|---|
| Small | €1,005 / day | €15,726 flat | €1,836 / day |
| Medium | €3,565 / day | €30,906 flat | €3,684 / day |
| Large | €10,094 / day | €47,668 flat | €6,413 / day |

- `accept_per_day` = average of `accept_cost ÷ delay_days`
- `switch_flat` = average `switch_cost` — switching is dominated by a
  one-off fee, so it barely moves with delay length
- `expedite_per_day` = average of `expedite_cost ÷ delay_days`

Two things to note. **The baseline ignores the material completely** —
that is the point, since comparability is what makes material matter. And
switching cost does drift upward about 25% across the delay range, which
the flat average does not capture; that is exactly the sort of pattern
that using the database indiscriminately misses.

The fitted daily costs reproduce the €1,000 / €3,500 / €10,000 tiers the
simulation was built from, to within 2%.

### The correction — what comparable cases say

For each retrieved case, compare what it *actually* cost with what the
baseline *would have predicted* for it. The ratio is the correction.

> "On past disruptions like this one, reality cost 1.3× what the database
> average predicted — so scale our prediction by 1.3."

**Why a ratio rather than an average of past costs.** Retrieved cases never
have exactly the same delay length, and a 4-day delay costs far less than a
9-day one. Averaging euro figures would mostly measure how long *those*
delays were. The ratio divides delay length out.

### The blend

```
final = 0.5 × baseline + 0.5 × corrected
```

A single constant, so it can be varied and studied. Recommendation = the
cheapest of the three final estimates.

## 7. How the similarity score works

```
similarity = 40 × material match + 30 × delay match + 30 × job size match
```

| Component | Rule |
|---|---|
| Material | same = 1, different = 0 |
| Job size | same = 1, one level apart = 0.5, two apart = 0 |
| Delay | `max(0, 1 − days apart ÷ 10)` |

The three highest scorers are retrieved. Every score can be worked out by
hand on paper — there is no machine learning anywhere in this project,
deliberately, because an opaque model would make the experiment impossible
to interpret.

> **The 40/30/30 weights are a prototype assumption, not an empirically
> established industry weighting.** They were not measured from real
> procurement records and not fitted to our simulation. Every result below
> is conditional on that choice.

## 8. The evaluation

### The cross-project rule

When advising a disruption on Project X, **nothing from Project X may be
used** — not for retrieval, and not for fitting the baseline. It is applied
in one function (`build_pool`) so no experiment can bypass it, and every
run prints a leakage check.

This is what turns the study from "can the system interpolate?" into "does
knowledge transfer *between projects*?"

### The four comparability bands

Each band is defined by **what the available cases have in common** with
the new disruption. The similarity percentage is then *measured* on
whatever gets retrieved, so it is a result rather than a label we assigned.

| Band | Available cases share | Measured similarity | Baseline | With history | Change |
|---|---|---|---|---|---|
| 1 Near-identical | same material, same job size, similar duration | 98% | €7,934 | €4,667 | **−41%** |
| 2 Different duration | same material, same job size, very different duration | 77% | €7,934 | €4,825 | **−39%** |
| 3 Different material | different material, same job size | 60% | €7,934 | €8,728 | **+10%** |
| 4 Nothing in common | different material, different job size, very different duration | 24% | €7,934 | €8,643 | **+9%** |

**The baseline is identical at €7,934 in every row.** That is the control:
the same 200 test disruptions run through every band, and the baseline
never looks at comparability, so any difference between rows is caused by
which cases were retrieved and nothing else. The run verifies this
explicitly.

All 200 test disruptions are used at every band. Test disruptions are
generated until there are 200 that every band can offer at least three
cases; a candidate that one band could not serve is replaced rather than
used, because measuring different bands on different disruptions would
break the pairing.

**What it says.** Comparable cases from other projects cut the estimation
error by 41%. Non-comparable cases make it *worse* than ignoring
comparability altogether. And bands 1 and 2 are almost identical, so once
the material and job size match, the length of the delay barely matters.

### Decision quality

| Band | Recommends the cheapest option | Advice changed |
|---|---|---|
| 1 Near-identical | 89% | 22% |
| 2 Different duration | 87% | 22% |
| 3 Different material | 66% | 8% |
| 4 Nothing in common | 66% | 14% |
| Baseline (no comparability) | 72% | — |

The effect is much clearer in euros than in decisions, because when the
system picks wrong the two best options are often nearly tied. Report the
error as the headline; this table is the honest supporting detail.

### Own history versus a shared pool

Each condition builds **both** its baseline and its retrieved cases from
the same data, because a contractor working alone would have to do the
same.

| Condition | Cases available | Measured similarity | Baseline | With history | Change |
|---|---|---|---|---|---|
| Own site only | 20 | 82% | €7,944 | €5,531 | −30% |
| Other sites only (pooled) | 380 | 98% | €7,934 | €4,667 | **−41%** |
| Own + other sites | 400 | 98% | €7,902 | €4,638 | −41% |

Pooling other projects' records is worth about eleven percentage points
over a contractor's own history alone; adding their own history back on top
of the pool adds almost nothing. The reason is in the similarity column:
twenty own cases only get you to 82%, while the pool reaches 98%.

### The control: shuffled material labels

Our dataset assumes costs are driven by duration, scale and material. A
fair critic will say we planted that pattern and then found it.

So we shuffled the material labels in the database. Every case keeps its
real cost and real delay; only the label saying *which* material it was
becomes meaningless. If the result comes from genuine comparability, the
gap between the same-material and different-material bands should collapse.

| Band | Real data | Labels shuffled |
|---|---|---|
| 1 Near-identical | −41% | +9% |
| 2 Different duration | −39% | +7% |
| 3 Different material | +10% | 0% |
| 4 Nothing in common | +9% | −1% |

**Gap between same-material and different-material bands: 51% on real data,
8% with the labels shuffled.**

**What this shows and what it does not.** It rules out one specific failure
mode: that the retrieval machinery produces apparent improvement regardless
of what it retrieves. That is not a hypothetical worry — our first control
attempt caught exactly such an artifact. **It does not show that material
really drives disruption cost.** We assumed that and built the data from it,
so no test inside the simulation can validate it. The only thing that speaks
to the premise is the published lead-time data the material parameters are
derived from.

*We first tried a control where the costs themselves were randomised. It
failed, and instructively: with random costs the baseline's assumption that
cost scales with delay length becomes wrong, the baseline goes badly
astray, and almost any correction appears to improve it. That measures the
baseline's shape rather than our claim. Shuffling a single label leaves
everything else intact and tests the thing we actually assert.*

## 9. Sources

The material parameters and the project-size cost tiers are derived from
these. Everything else in the simulation is a stated assumption.

- Terrapin Construction Group, *Commercial Construction Material Lead
  Times*, July 2026 — concrete and masonry 1–4 wks, roofing membrane 3–10
  wks, structural steel 14–20 wks, medium-voltage switchgear 52–80 wks.
  https://terrapincg.com/news/commercial-construction-material-lead-times-2026
- Cresa, *Strategies to Optimize Lead Times for a Successful Construction
  Project* — lighting 8–16 wks, fabricated structural steel 20–25 wks,
  rooftop HVAC units 30–45 wks, switchgear 45–60 wks, generators 50–60 wks.
  https://www.cresa.com/Blog/2023-Optimize-Lead-Times
- Auburn University Highway Research Center, project 930-656, *Development
  of a Procedure for Updating Liquidated Damages* — state DOT liquidated
  damages schedules by contract value (Alabama 2002; Florida, Georgia,
  Louisiana, Mississippi, Tennessee 2008).
  https://eng.auburn.edu/files/centers/hrc/930-656.pdf

## 10. Limitations

- All data is **simulated**. No real procurement records were used.
- **The core assumption cannot be tested from inside the simulation.** We
  assume disruption costs are driven by measurable characteristics, build
  data from that assumption, and show retrieval exploits it. The
  shuffled-label control rules out a method artifact; it cannot validate
  the premise. Deriving the material parameters from published lead times
  moves that assumption out of our hands and onto cited sources, but the
  mapping from lead times to cost parameters is still ours.
- **The 40/30/30 weights are a prototype assumption.** We did not test
  alternatives.
- Our history stores the true cost of all three options for every case. In
  reality only the chosen option's cost is observed, so a real knowledge
  base would need roughly three times the cases to reach the same estimate
  quality.
- Projects differ only by size and a single permanent multiplier between
  0.90 and 1.10. Real projects differ in far more ways, and probably by
  more, which would make cross-project transfer harder than it appears.
- Costs are simplified to three options; supplier behaviour to one
  disruption type with no negotiation or partial delivery; schedules to a
  flat cost per lost day with no critical path or float.
- Only three comparability dimensions are tested. Location, season,
  contract type and supplier relationship are ignored.
- Every figure is a plain average across test cases. We did not compute
  confidence intervals or significance tests, and the recommendation
  accuracy differences in particular may not survive one.
- We measured whether history helps at a fixed database size. We did not
  measure whether estimates improve as the database grows, so the claim
  that accumulation pays off over time is not tested here.

## Demo interface (ImpactIQ)

`streamlit run app.py` opens the three-page demo:

1. **Intake**: upload a supplier e-mail (.eml) or notice/invoice (.txt), or open one from `mock_documents/`. `extraction.py` reads project, material, delay and supplier with plain keyword rules and highlights the words it used. All fields can be corrected.
2. **Estimation**: cost of Accept / Switch / Expedite, the three most similar past cases from other projects, and an advice threshold. Below 70% average similarity, only the generic estimate is shown and nothing is recommended (the band-3 finding). The manager records the outcome, which is saved as a new case.
3. **Knowledge base**: every case, coverage per material × project size, filters, CSV download, and **Reset demo data**, which restores the 400 simulated cases from `data/historical_cases_original.csv`.

The earlier interface with the evaluation page is kept as `app_legacy.py`.
