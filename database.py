"""
database.py
===========

PURPOSE
-------
Read the historical cases out of the CSV file, and add new ones to it.

That is all it does. It is separated into its own small file so that
every other file can simply say "give me the cases" without worrying
about how CSV files work.

Our "database" is one spreadsheet file: data/historical_cases.csv
You can open it by double-clicking it in Finder.
"""

import csv
import os

from data_generator import COLUMNS

# These columns hold numbers. Everything read from a CSV file arrives as
# text, so we have to convert these back into numbers.
NUMBER_COLUMNS = [
    "delay_days",
    "accept_cost",
    "switch_cost",
    "expedite_cost",
    "actual_cost",
]


def default_path():
    """The normal location of the database, next to this file."""
    here = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(here, "data", "historical_cases.csv")


def load_cases(file_path=None):
    """
    Read all historical cases from the CSV file.

    Returns a list of dictionaries, one per case, with numbers stored as
    real numbers rather than text.
    """
    if file_path is None:
        file_path = default_path()

    if not os.path.exists(file_path):
        raise FileNotFoundError(
            f"Could not find {file_path}.\n"
            "Run 'python3 data_generator.py' first to create it."
        )

    cases = []
    with open(file_path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            case = dict(row)
            for column in NUMBER_COLUMNS:
                case[column] = int(float(case[column]))
            cases.append(case)
    return cases


def next_case_id(cases):
    """Work out the id for the next case, e.g. '101' after '100'."""
    if not cases:
        return "001"
    highest = max(int(case["case_id"]) for case in cases)
    return f"{highest + 1:03d}"


def add_case(new_case, file_path=None):
    """
    Add one new case to the end of the CSV file.

    This is the feedback loop: once a manager records what a disruption
    actually cost, it becomes available to every future search.
    """
    if file_path is None:
        file_path = default_path()

    # Keep only the real database columns, in the right order.
    # (Retrieved cases carry extra keys like "similarity" - drop those.)
    row = {column: new_case.get(column, "") for column in COLUMNS}

    with open(file_path, "a", newline="", encoding="utf-8") as f:
        csv.DictWriter(f, fieldnames=COLUMNS).writerow(row)

    return row


def count_cases(file_path=None):
    """How many cases are currently in the database."""
    return len(load_cases(file_path))


# ---------------------------------------------------------------------
# DEMO SAFETY NET
# ---------------------------------------------------------------------
# During a demo, new cases get saved. To start the next demo from the
# same 400 simulated cases, we keep an untouched copy the first time the
# app runs and can put it back with one click.
import shutil


def original_path():
    return default_path().replace(".csv", "_original.csv")


def ensure_original_backup():
    """Keep a copy of the simulated dataset before anything is added."""
    if not os.path.exists(original_path()) and os.path.exists(default_path()):
        shutil.copyfile(default_path(), original_path())


def original_case_ids():
    """The case ids that came from the simulation (not added in the app)."""
    ensure_original_backup()
    return {c["case_id"] for c in load_cases(original_path())}


def reset_to_original():
    """Throw away every case added in the app."""
    ensure_original_backup()
    shutil.copyfile(original_path(), default_path())
