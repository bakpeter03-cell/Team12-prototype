"""
app.py
======

The Streamlit interface for the prototype.

HOW TO RUN IT
-------------
    cd ~/Documents/procurement-prototype
    streamlit run app.py

A browser tab opens by itself. Leave the Terminal window running while
you use the app - closing it stops the app.

THREE PAGES
-----------
    1. Analyze disruption   the decision tool
    2. Historical database  the growing knowledge base
    3. Evaluation           the experiment results

This file contains NO new logic. Every calculation comes from
calculations.py, similarity.py and database.py, which already work and
are already tested. This is only the screen.
"""

import os

import pandas as pd
import streamlit as st

import calculations
import database
import similarity
from data_generator import MATERIALS, PROJECTS

# ---------------------------------------------------------------------
# PAGE SETUP
# ---------------------------------------------------------------------
st.set_page_config(
    page_title="Procurement Risk Agent",
    layout="wide",
)

HOW_MANY_SIMILAR_CASES = 3
DATA_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")


def money(amount):
    """Format a number as money, e.g. 41700 -> '€41,700'."""
    return f"€{amount:,.0f}"


# ---------------------------------------------------------------------
# SIDEBAR - which page are we on
# ---------------------------------------------------------------------
st.sidebar.title("Procurement Risk Agent")
page = st.sidebar.radio(
    "Page",
    ["1 - Analyze disruption", "2 - Historical database", "3 - Evaluation"],
    label_visibility="collapsed",
)

st.sidebar.caption(
    "**Synthetic prototype data — for experimentation only.** "
    "No real construction industry data is used anywhere in this tool."
)
st.sidebar.divider()
st.sidebar.caption(
    f"Similarity weights: **{similarity.WEIGHT_MATERIAL:.0%} material · "
    f"{similarity.WEIGHT_DELAY:.0%} delay · "
    f"{similarity.WEIGHT_PROJECT_SIZE:.0%} project size**  \n"
    "These are a prototype assumption, not an empirically established "
    "industry weighting."
)


# =====================================================================
# PAGE 1 - ANALYZE DISRUPTION
# =====================================================================
def page_analyze():
    st.title("Analyze a new disruption")
    st.caption(
        "The system estimates the cost of the three possible responses, "
        "using comparable disruptions from **other projects** only."
    )

    all_cases = database.load_cases()

    # --- The input form ----------------------------------------------
    with st.form("new_disruption"):
        col1, col2, col3 = st.columns(3)

        with col1:
            project_id = st.selectbox(
                "Project",
                list(PROJECTS.keys()),
                help="The project this disruption is happening on. "
                     "Its own past cases will be excluded from the search.",
            )
            project_size = PROJECTS[project_id]["project_size"]
            st.caption(f"Project size: **{project_size}**")

        with col2:
            material = st.selectbox("Material", list(MATERIALS.keys()))

        with col3:
            delay_days = st.slider("Delay (days)", 1, 15, 5)

        st.caption("Disruption type: supplier delivery delay")
        analyze = st.form_submit_button("Analyze", type="primary")

    if analyze:
        st.session_state["analysis"] = run_analysis(
            all_cases, project_id, material, delay_days, project_size
        )

    if "analysis" not in st.session_state:
        st.info("Fill in the disruption above and press **Analyze**.")
        return

    show_analysis(st.session_state["analysis"], all_cases)


def run_analysis(all_cases, project_id, material, delay_days, project_size):
    """Do the retrieval and the three estimates. No display here."""
    disruption = {
        "material": material,
        "delay_days": delay_days,
        "project_size": project_size,
    }

    # THE CROSS-PROJECT RULE: never learn from your own project.
    # This applies to the retrieved cases AND to the baseline, which is
    # fitted from the same pool of other projects' cases.
    other_projects = [c for c in all_cases if c["project_id"] != project_id]
    own_project_count = len(all_cases) - len(other_projects)

    params = calculations.fit_baseline(other_projects)

    retrieved = similarity.find_similar_cases(
        disruption, other_projects, top_n=HOW_MANY_SIMILAR_CASES
    )
    result = calculations.estimate_everything(
        material, delay_days, project_size, retrieved, params
    )

    return {
        "project_id": project_id,
        "material": material,
        "delay_days": delay_days,
        "project_size": project_size,
        "retrieved": retrieved,
        "result": result,
        "searched": len(other_projects),
        "excluded": own_project_count,
    }


def show_analysis(analysis, all_cases):
    result = analysis["result"]
    retrieved = analysis["retrieved"]

    st.divider()

    # --- The retrieved cases -----------------------------------------
    st.subheader("Similar historical cases")
    st.caption(
        f"Searched **{analysis['searched']} cases from "
        f"{len(PROJECTS) - 1} other projects**. "
        f"{analysis['excluded']} cases from {analysis['project_id']} itself "
        "were excluded, because a project may not learn from its own history."
    )

    columns = st.columns(len(retrieved))
    for column, case in zip(columns, retrieved):
        with column:
            st.metric(
                f"Case {case['case_id']} · project {case['project_id']}",
                f"{case['similarity']}% similar",
            )
            st.write(
                f"{case['material']} | {case['delay_days']} days "
                f"| {case['project_size']}"
            )
            st.write(f"Chosen action: **{case['chosen_action']}**")
            st.write(f"Actual cost: **{money(case['actual_cost'])}**")
            for dimension, reason in case["explanation"].items():
                st.caption(f"{dimension}: {reason}")

    st.divider()

    # --- What the past cases tell us ---------------------------------
    st.subheader("What the past cases tell us")
    factor_columns = st.columns(3)
    for column, action in zip(factor_columns, calculations.ACTIONS):
        factor = result["factors"][action]
        with column:
            st.metric(
                action,
                f"{factor:.2f}x",
                f"{(factor - 1) * 100:+.0f}% vs the generic rule",
                delta_color="off",
            )
    st.caption(
        "How much those comparable cases cost compared with what the "
        "whole-database average predicted for them. This is the correction "
        "applied to the new disruption."
    )

    st.divider()

    # --- The three estimates -----------------------------------------
    st.subheader("Cost comparison")

    table = pd.DataFrame(
        {
            "Baseline (whole database)": [
                result["baseline"][a] for a in calculations.ACTIONS
            ],
            "History-corrected": [
                result["historical"][a] for a in calculations.ACTIONS
            ],
            "Final estimate": [
                result["blended"][a] for a in calculations.ACTIONS
            ],
        },
        index=calculations.ACTIONS,
    )
    st.dataframe(
        table.style.format("€{:,.0f}"),
        width="stretch",
    )
    st.caption(
        f"Final estimate = "
        f"{1 - calculations.BLEND_WEIGHT_HISTORY:.0%} baseline + "
        f"{calculations.BLEND_WEIGHT_HISTORY:.0%} history-corrected."
    )

    # --- The recommendation ------------------------------------------
    recommendation = result["recommendation"]
    st.success(
        f"### Recommendation: {recommendation}  \n"
        f"Estimated cost **{money(result['blended'][recommendation])}** — "
        f"based on the current disruption and {result['cases_used']} "
        f"comparable cases from other projects."
    )
    if result["baseline_recommendation"] != recommendation:
        st.info(
            f"Without historical cases the system would have recommended "
            f"**{result['baseline_recommendation']}**. The history changed "
            "the decision."
        )

    st.divider()
    show_manager_decision(analysis, all_cases)


# =====================================================================
# THE FEEDBACK LOOP
# =====================================================================
def show_manager_decision(analysis, all_cases):
    """The manager decides, records what it cost, and the case is saved."""
    st.subheader("Manager decision")
    st.caption(
        "The system advises. The manager decides. Once the disruption is "
        "resolved, the outcome is recorded and becomes available to every "
        "future search."
    )

    result = analysis["result"]

    # Already saved? Show the confirmation instead of the form, so the
    # same case cannot be added twice by clicking Save again.
    if analysis.get("saved_case_id"):
        st.success(
            f"Case {analysis['saved_case_id']} saved to the historical "
            "knowledge base. It is now available for future similarity "
            "searches."
        )
        st.caption(
            f"The knowledge base now holds "
            f"**{len(database.load_cases())} cases**. "
            "Press **Analyze** above to start a new disruption."
        )
        return

    with st.form("manager_decision"):
        col1, col2 = st.columns(2)
        with col1:
            chosen = st.radio(
                "Action taken",
                calculations.ACTIONS,
                index=calculations.ACTIONS.index(result["recommendation"]),
                horizontal=True,
            )
        with col2:
            actual_cost = st.number_input(
                "Actual cost (€)",
                min_value=0,
                step=500,
                value=int(result["blended"][result["recommendation"]]),
            )
        save = st.form_submit_button("Save outcome", type="primary")

    st.caption(
        "Note: because this is a prototype, the two options **not** chosen "
        "are stored as the system's final estimates. In reality their cost "
        "would never be observed — you only ever find out what the option "
        "you took actually cost."
    )

    if save:
        new_case = build_new_case(analysis, chosen, actual_cost, all_cases)
        database.add_case(new_case)
        analysis["saved_case_id"] = new_case["case_id"]
        st.rerun()


def build_new_case(analysis, chosen_action, actual_cost, all_cases):
    """Turn a manager decision into a row for the historical database."""
    # The chosen action's cost is real. The other two are our estimates.
    costs = dict(analysis["result"]["blended"])
    costs[chosen_action] = int(actual_cost)

    return {
        "case_id": database.next_case_id(all_cases),
        "project_id": analysis["project_id"],
        "material": analysis["material"],
        "delay_days": analysis["delay_days"],
        "project_size": analysis["project_size"],
        "accept_cost": costs["Accept"],
        "switch_cost": costs["Switch"],
        "expedite_cost": costs["Expedite"],
        "optimal_action": min(calculations.ACTIONS, key=lambda a: costs[a]),
        "chosen_action": chosen_action,
        "actual_cost": int(actual_cost),
    }


# =====================================================================
# PAGE 2 - HISTORICAL DATABASE
# =====================================================================
def page_database():
    st.title("Historical knowledge base")
    st.caption(
        "Every resolved disruption becomes a case. The database is the "
        "asset — the longer it runs, the more disruptions it can speak to."
    )

    cases = database.load_cases()

    col1, col2, col3 = st.columns(3)
    col1.metric("Historical cases", len(cases))
    col2.metric("Projects", len({c["project_id"] for c in cases}))
    col3.metric("Materials", len({c["material"] for c in cases}))

    st.divider()

    frame = pd.DataFrame(cases)
    display = frame[[
        "case_id", "project_id", "material", "delay_days", "project_size",
        "chosen_action", "actual_cost",
    ]].rename(columns={
        "case_id": "Case",
        "project_id": "Project",
        "material": "Material",
        "delay_days": "Delay (days)",
        "project_size": "Project size",
        "chosen_action": "Chosen action",
        "actual_cost": "Actual cost",
    })

    st.subheader("All cases")
    st.dataframe(
        display.style.format({"Actual cost": "€{:,.0f}"}),
        width="stretch",
        height=420,
        hide_index=True,
    )

    st.subheader("Cases per project")
    per_project = (
        frame.groupby("project_id").size().reset_index(name="cases")
        .rename(columns={"project_id": "Project", "cases": "Cases"})
    )
    st.dataframe(per_project, width="stretch", hide_index=True)
    st.caption(
        "When advising a disruption on a project, that project's own row "
        "is excluded from the search."
    )


# =====================================================================
# PAGE 3 - EVALUATION
# =====================================================================
def page_evaluation():
    st.title("Evaluation")
    st.caption(
        "Does historical knowledge transfer between projects, and when "
        "does it stop working?"
    )

    results_path = os.path.join(DATA_FOLDER, "evaluation_results.csv")
    if not os.path.exists(results_path):
        st.warning(
            "No results yet. Run `python3 evaluation.py` in the Terminal "
            "first, then reload this page."
        )
        return

    results = pd.read_csv(results_path)

    cross = results
    by_level = cross.groupby("level").agg(
        similarity=("measured_similarity", "mean"),
        baseline_error=("baseline_error", "mean"),
        history_error=("blended_error", "mean"),
        baseline_accuracy=("baseline_correct", "mean"),
        history_accuracy=("blended_correct", "mean"),
    ).reset_index()

    col1, col2, col3 = st.columns(3)
    col1.metric("Test disruptions", results["test_id"].nunique())
    col2.metric("Comparability levels", by_level.shape[0])
    leaked = int(cross["cases_from_own_project"].sum())
    col3.metric("Same-project cases used", leaked,
                "cross-project rule holds" if leaked == 0 else "LEAKAGE",
                delta_color="off")

    st.divider()
    st.subheader("Results by comparability level")

    table = by_level.copy()
    table["change"] = (
        (table["history_error"] - table["baseline_error"])
        / table["baseline_error"]
    )
    table = table.rename(columns={
        "level": "Level",
        "similarity": "Measured similarity",
        "baseline_error": "Baseline error",
        "history_error": "With history",
        "change": "Change",
        "baseline_accuracy": "Accuracy (baseline)",
        "history_accuracy": "Accuracy (history)",
    })[[
        "Level", "Measured similarity", "Baseline error", "With history",
        "Change", "Accuracy (baseline)", "Accuracy (history)",
    ]]

    st.dataframe(
        table.style.format({
            "Measured similarity": "{:.0f}%",
            "Baseline error": "€{:,.0f}",
            "With history": "€{:,.0f}",
            "Change": "{:+.0%}",
            "Accuracy (baseline)": "{:.0%}",
            "Accuracy (history)": "{:.0%}",
        }),
        width="stretch",
        hide_index=True,
    )

    st.caption(
        "The baseline never looks at history, so its error is identical at "
        "every level. That is the control: any difference between rows is "
        "caused by the historical cases and nothing else."
    )

    st.info("Charts coming next — this page currently shows the numbers only.")


# ---------------------------------------------------------------------
# ROUTER
# ---------------------------------------------------------------------
if page.startswith("1"):
    page_analyze()
elif page.startswith("2"):
    page_database()
else:
    page_evaluation()
