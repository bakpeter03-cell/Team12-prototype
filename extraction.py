"""
extraction.py
=============

PURPOSE
-------
Read an incoming disruption document (a supplier email, a delay notice,
an invoice) and pull out the four facts the rest of the system needs:

    project      which project the delivery is for       e.g. "P07"
    material     what is being delivered late             e.g. "Structural steel"
    delay_days   how many days late                       e.g. 6
    supplier     who sent it                              e.g. "Nordstaal Profiles B.V."

There is deliberately NO AI here. Every field is found by plain keyword
and pattern matching, so the result is the same every time the demo
runs, and every extracted value can be traced back to the exact words
in the document that produced it (the interface highlights them).

The manager always confirms the fields before anything is estimated.
Extraction is a convenience, not a decision.

ACCEPTED INPUT
--------------
    .eml   a saved email (headers + body)
    .txt   plain text: a pasted email, a notice, an invoice
"""

import re
from datetime import datetime, date
from email import policy
from email.parser import BytesParser

from data_generator import MATERIALS, PROJECTS

# ---------------------------------------------------------------------
# MATERIAL VOCABULARY
# ---------------------------------------------------------------------
# The words a supplier might actually use, mapped to our six material
# categories. Longer phrases are listed first so "structural steel" wins
# over a bare "steel".
#
# The last three categories are NOT in the historical database. They are
# recognised so that the system can say honestly "I know what this is,
# but I have no comparable history for it" instead of guessing.
MATERIAL_KEYWORDS = {
    "Structural steel": [
        "structural steel", "steel beams", "steel sections", "steel columns",
        "i-beams", "hea ", "heb ", "ipe ", "steel frame", "steelwork",
    ],
    "Concrete & masonry": [
        "ready-mix", "readymix", "ready mix", "concrete", "masonry",
        "precast", "blockwork", "bricks", "brickwork",
    ],
    "HVAC rooftop units": [
        "rooftop unit", "rooftop units", "hvac", "rtu", "air handling unit",
        "air handling units", "ahu",
    ],
    "Electrical switchgear": [
        "switchgear", "switchboard", "lv panel", "mv panel",
        "distribution board", "main distribution",
    ],
    "Lighting": [
        "luminaires", "luminaire", "light fittings", "led fixtures",
        "lighting", "downlights",
    ],
    "Roofing membrane": [
        "roofing membrane", "roof membrane", "epdm", "tpo membrane",
        "bitumen", "bituminous",
    ],
    # --- recognised, but no history exists for these -----------------
    "Curtain wall & glazing": [
        "curtain wall", "curtain-wall", "glazing", "glass panels",
        "facade panels", "façade panels",
    ],
    "Lifts & elevators": ["elevator", "elevators", "lift car", "passenger lift"],
    "Timber / CLT": ["cross-laminated", "clt panels", "glulam", "timber frame"],
}

KNOWN_MATERIALS = set(MATERIALS.keys())

NUMBER_WORDS = {
    "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11,
    "twelve": 12, "thirteen": 13, "fourteen": 14, "fifteen": 15,
    "a": 1, "an": 1,
}
NUM = r"(\d{1,3}|" + "|".join(sorted(NUMBER_WORDS, key=len, reverse=True)) + r")"


def _to_int(token):
    token = token.lower()
    return int(token) if token.isdigit() else NUMBER_WORDS[token]


# ---------------------------------------------------------------------
# READING THE FILE
# ---------------------------------------------------------------------
def read_document(filename, raw_bytes):
    """
    Turn an uploaded file into plain text plus a few header fields.

    Returns {"kind", "subject", "sender", "sent", "body"}.
    """
    name = filename.lower()
    if name.endswith(".eml"):
        message = BytesParser(policy=policy.default).parsebytes(raw_bytes)
        part = message.get_body(preferencelist=("plain", "html"))
        body = part.get_content() if part is not None else ""
        if part is not None and part.get_content_type() == "text/html":
            body = re.sub(r"<[^>]+>", " ", body)
        return {
            "kind": "Email",
            "subject": str(message.get("subject", "") or ""),
            "sender": str(message.get("from", "") or ""),
            "sent": str(message.get("date", "") or ""),
            "body": body.strip(),
        }

    text = raw_bytes.decode("utf-8", errors="replace").strip()
    return {
        "kind": _guess_kind(text),
        "subject": _header(text, "subject"),
        "sender": _header(text, "from"),
        "sent": _header(text, "date"),
        "body": text,
    }


def _header(text, name):
    match = re.search(rf"^{name}\s*:\s*(.+)$", text, re.I | re.M)
    return match.group(1).strip() if match else ""


def _guess_kind(text):
    head = text[:400].lower()
    if "invoice" in head:
        return "Invoice"
    if "notice" in head or "notification" in head:
        return "Delay notice"
    if re.search(r"^from\s*:", text, re.I | re.M):
        return "Email"
    return "Document"


# ---------------------------------------------------------------------
# THE FIELD FINDERS
# ---------------------------------------------------------------------
# Each finder returns a dictionary:
#     {"value": ..., "evidence": "the matched words", "span": (start, end)}
# or None when nothing was found. The span points into the text that was
# searched, so the interface can highlight it.

def find_project(text):
    pattern = re.compile(r"\b(?:project\s*(?:no\.?|number|#|code)?\s*[:\-]?\s*)?P[\s\-]?0?(\d{1,2})\b", re.I)
    for match in pattern.finditer(text):
        project_id = f"P{int(match.group(1)):02d}"
        if project_id in PROJECTS:
            return {"value": project_id, "evidence": match.group(0),
                    "span": match.span()}
    return None


def find_material(text):
    lowered = text.lower()
    best = None
    for material, keywords in MATERIAL_KEYWORDS.items():
        hits = []
        for keyword in keywords:
            for m in re.finditer(r"(?<![a-z])" + re.escape(keyword.strip()) + r"(?![a-z])", lowered):
                hits.append(m.span())
        if hits:
            first = min(hits)
            candidate = (len(hits), -first[0], material, first)
            if best is None or candidate > best:
                best = candidate
    if best is None:
        return None
    _, _, material, span = best
    return {"value": material, "evidence": text[span[0]:span[1]], "span": span,
            "in_database": material in KNOWN_MATERIALS}


DELAY_PATTERNS = [
    # "delayed by 6 days", "delayed by six working days"
    rf"delay(?:ed)?\s+(?:by|of)\s+(?:approximately\s+|about\s+|around\s+)?{NUM}\s+(?:working\s+|calendar\s+|business\s+)?(day|days|week|weeks)\b",
    # "a 6-day delay", "six day delay"
    rf"\b{NUM}[\s\-](day|week)s?\s+delay",
    # "6 days late", "two weeks behind"
    rf"\b{NUM}\s+(?:working\s+|calendar\s+|business\s+)?(day|days|week|weeks)\s+(?:late|behind|later)",
    # "pushed back 4 days", "postponed by 4 days", "moved 4 days"
    rf"(?:pushed\s+back|postponed|moved|slipped|shifted)\s+(?:by\s+)?{NUM}\s+(?:working\s+|calendar\s+)?(day|days|week|weeks)\b",
    # "an additional 5 days", "extra 5 days"
    rf"(?:additional|extra)\s+{NUM}\s+(?:working\s+|calendar\s+)?(day|days|week|weeks)\b",
]

DATE_FORMATS = ["%d %B %Y", "%d %b %Y", "%B %d, %Y", "%b %d, %Y",
                "%d-%m-%Y", "%d/%m/%Y", "%Y-%m-%d", "%d.%m.%Y"]
DATE_RE = re.compile(
    r"\b(\d{1,2}\s+[A-Z][a-z]+\s+\d{4}|[A-Z][a-z]+\s+\d{1,2},\s+\d{4}|"
    r"\d{4}-\d{2}-\d{2}|\d{1,2}[./-]\d{1,2}[./-]\d{4})\b"
)


def _parse_date(token):
    for fmt in DATE_FORMATS:
        try:
            return datetime.strptime(token, fmt).date()
        except ValueError:
            continue
    return None


def find_delay(text):
    # 1) An explicit number of days in the text.
    for pattern in DELAY_PATTERNS:
        match = re.search(pattern, text, re.I)
        if match:
            amount = _to_int(match.group(1))
            unit = match.group(2).lower()
            days = amount * 7 if unit.startswith("week") else amount
            return {"value": days, "evidence": match.group(0),
                    "span": match.span(), "method": "stated in text"}

    # 2) No number stated: compare an original and a revised date.
    original = revised = None
    for line_match in re.finditer(r"^.*$", text, re.M):
        line = line_match.group(0)
        low = line.lower()
        for d in DATE_RE.finditer(line):
            parsed = _parse_date(d.group(0))
            if parsed is None:
                continue
            span = (line_match.start() + d.start(), line_match.start() + d.end())
            if re.search(r"original|scheduled|confirmed|agreed|planned", low) and original is None:
                original = (parsed, span, line.strip())
            elif re.search(r"revised|new|expected|now|updated|rescheduled", low) and revised is None:
                revised = (parsed, span, line.strip())
    if original and revised and revised[0] > original[0]:
        days = (revised[0] - original[0]).days
        return {"value": days,
                "evidence": f"{original[0]:%d %b} → {revised[0]:%d %b}",
                "span": revised[1], "extra_span": original[1],
                "method": "difference between original and revised delivery date"}
    return None


def find_supplier(doc):
    text = doc["body"]
    match = re.search(r"^(?:supplier|vendor|from company|issued by)\s*:\s*(.+)$", text, re.I | re.M)
    if match:
        return {"value": match.group(1).strip(), "evidence": match.group(0),
                "span": match.span(1)}
    sender = doc.get("sender", "")
    if sender:
        name = re.sub(r"<.*?>", "", sender).strip().strip('"')
        domain = re.search(r"@([\w\-]+)\.", sender)
        value = name or (domain.group(1).title() if domain else sender)
        return {"value": value, "evidence": sender, "span": None}
    return None


# ---------------------------------------------------------------------
# PUTTING IT TOGETHER
# ---------------------------------------------------------------------
def extract(filename, raw_bytes):
    """
    Read a document and extract every field.

    Returns:
        {
          "document": {kind, subject, sender, sent, body},
          "fields":   {"project": {...} | None, "material": ..., "delay_days": ..., "supplier": ...},
          "project_size": "Small" | "Medium" | "Large" | None,
          "complete": True when project, material and delay were all found,
        }
    """
    doc = read_document(filename, raw_bytes)
    searchable = doc["subject"] + "\n" + doc["body"]
    offset = len(doc["subject"]) + 1           # spans are reported relative to the body

    def rebase(found):
        if found and found.get("span"):
            start, end = found["span"]
            found["span"] = (start - offset, end - offset) if start >= offset else None
        if found and found.get("extra_span"):
            start, end = found["extra_span"]
            found["extra_span"] = (start - offset, end - offset) if start >= offset else None
        return found

    fields = {
        "project": rebase(find_project(searchable)),
        "material": rebase(find_material(searchable)),
        "delay_days": rebase(find_delay(searchable)),
        "supplier": find_supplier(doc),
    }
    project_size = (PROJECTS[fields["project"]["value"]]["project_size"]
                    if fields["project"] else None)

    return {
        "document": doc,
        "fields": fields,
        "project_size": project_size,
        "complete": all(fields[k] for k in ("project", "material", "delay_days")),
    }


if __name__ == "__main__":
    import sys
    for path in sys.argv[1:]:
        with open(path, "rb") as f:
            result = extract(path, f.read())
        print(f"\n{path}  [{result['document']['kind']}]")
        for key, found in result["fields"].items():
            print(f"  {key:11s} {found['value'] if found else '— not found —'}"
                  + (f"   ← \"{found['evidence']}\"" if found else ""))
        print(f"  size        {result['project_size']}")
