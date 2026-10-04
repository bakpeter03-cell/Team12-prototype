"""
app.py
======

The ImpactIQ interface: three pages that follow one disruption from the
moment the supplier's message arrives to the moment it becomes part of
the knowledge base.

HOW TO RUN IT
-------------
    cd ~/Documents/procurement-prototype
    streamlit run app.py

THREE PAGES
-----------
    1. Intake        upload the supplier's email / notice / invoice,
                     check the fields the system read from it
    2. Estimation    cost of Accept / Switch / Expedite, and the past
                     cases the estimate is based on (with similarity)
    3. Knowledge base  every stored case, including the ones added here

Like before, this file contains NO logic of its own. Reading documents
is in extraction.py, similarity in similarity.py, costs in
calculations.py, storage in database.py. This file is only the screen.

The previous interface (with the evaluation page) is kept as
app_legacy.py and still works:  streamlit run app_legacy.py
"""

import html
import os
import re
from email.utils import parseaddr, parsedate_to_datetime

import pandas as pd
import streamlit as st

import calculations
import database
import extraction
import similarity
from data_generator import PROJECTS

st.set_page_config(page_title="ImpactIQ · Procurement Risk Agent",
                   page_icon="⚡", layout="wide",
                   initial_sidebar_state="collapsed")

HERE = os.path.dirname(os.path.abspath(__file__))
SAMPLES_FOLDER = os.path.join(HERE, "mock_documents")
HOW_MANY_SIMILAR_CASES = 3

PAGES = ["Intake", "Estimation", "Knowledge base"]

# Highlight colours per extracted field: (label, background, text, accent)
FIELD_STYLE = {
    "project":    ("Project",  "#DBEAFE", "#1E3A8A", "#2563EB"),
    "material":   ("Material", "#EDE9FE", "#4C1D95", "#7C3AED"),
    "delay_days": ("Delay",    "#FFEDD5", "#7C2D12", "#EA580C"),
    "supplier":   ("Supplier", "#DCFCE7", "#14532D", "#16A34A"),
}

# Friendly names for the demo documents in the sample picker
SAMPLE_LABELS = {
    "01_email_steel_delay.eml": "Email · Structural steel delay (P07)",
    "02_notice_hvac_supplier.txt": "Delay notice · HVAC rooftop units (P12)",
    "03_invoice_switchgear_expedite.txt": "Invoice · Electrical switchgear (P05)",
    "04_email_concrete_short.eml": "Email · Ready-mix concrete (P16)",
    "05_email_lighting_weeks.eml": "Email · LED luminaires (P09)",
    "06_notice_curtainwall_nohistory.txt": "Delay notice · Curtain wall glazing (P03)",
    "07_email_roofing_messy.eml": "Email · EPDM roofing membrane (P14)",
    "08_email_steel_long_delay.eml": "Email · Steel, three-week delay (P11)",
}


def money(amount):
    return f"€{amount:,.0f}"


def tidy(markup):
    """Put HTML on one line, so markdown never mistakes indentation for code."""
    return " ".join(line.strip() for line in markup.splitlines() if line.strip())


# =====================================================================
# LOOK AND FEEL
# =====================================================================
# Text colours are kept dark on purpose (no light grey text):
#   #0F172A headings and numbers · #1E293B body text · #334155 secondary text
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;600&display=swap');

  html {font-size: 17px;}
  html, body, [data-testid="stAppViewContainer"], .stMarkdown, .stButton button,
  input, textarea, [data-baseweb="select"], [data-testid="stWidgetLabel"] {
      font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;}
  body, .stMarkdown, .stMarkdown p {color:#1E293B;}
  [data-testid="stSidebar"], [data-testid="collapsedControl"] {display:none;}
  .block-container {padding: 1.8rem 2.6rem 4rem; max-width: 1600px;}
  h1, h2, h3 {letter-spacing:-0.02em; color:#0F172A !important;}
  h3 {font-size:2rem !important; font-weight:800 !important; padding-bottom:.2rem !important;}
  [data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p {
      color:#1E293B !important; font-size:.98rem !important; line-height:1.55;}
  [data-testid="stWidgetLabel"] p {color:#0F172A !important; font-weight:600 !important;
      font-size:.95rem !important;}
  .stButton button, .stDownloadButton button, [data-testid="stPopover"] button {
      font-size:1rem !important; font-weight:600 !important; border-radius:10px !important;
      min-height:2.9rem;}
  .stButton button p, .stDownloadButton button p, [data-testid="stPopover"] button p {
      font-size:1rem !important; font-weight:600 !important;}
  [data-testid="stAlert"] p {font-size:1.02rem; color:#0F172A;}
  [data-testid="stExpander"] summary p {font-size:1rem; font-weight:600; color:#0F172A;}

  /* --- header ------------------------------------------------------ */
  .brand {display:flex; align-items:center; gap:.9rem; margin-top:.2rem;}
  .brand .logo {font-weight:800; font-size:1.9rem; letter-spacing:-.01em; color:#0F172A;}
  .brand .logo span {color:#1F4FD8;}
  .brand .tag {color:#1E293B; font-size:1rem; font-weight:500;}
  .synthetic {display:inline-block; font-size:.78rem; font-weight:600; color:#78350F;
              background:#FEF3C7; border:1px solid #FCD34D; border-radius:999px;
              padding:.15rem .7rem; margin-left:.5rem;}
  .page-title {font-size:2.1rem; font-weight:800; color:#0F172A; letter-spacing:-.02em;
               margin:.6rem 0 .25rem 0;}
  .page-sub {font-size:1.05rem; color:#334155; margin-bottom:1.2rem; max-width:900px;}

  .card {background:#FFFFFF; border:1px solid #D8DEE8; border-radius:16px;
         padding:1.4rem 1.6rem; box-shadow:0 1px 3px rgba(15,23,42,.05);}
  .card h4 {margin:0 0 .8rem 0; font-size:.85rem; text-transform:uppercase;
            letter-spacing:.07em; color:#0F172A; font-weight:700;}

  /* --- the document viewer ----------------------------------------- */
  .mail {background:#FFFFFF; border:1px solid #D8DEE8; border-radius:18px; overflow:hidden;
         box-shadow:0 1px 3px rgba(15,23,42,.06), 0 12px 32px rgba(15,23,42,.05);}
  .mail-bar {display:flex; justify-content:space-between; align-items:center; gap:1rem;
             padding:.75rem 1.6rem; background:#F1F5F9; border-bottom:1px solid #E2E8F0;
             font-size:.88rem; color:#1E293B; font-weight:500;}
  .kind {display:inline-flex; align-items:center; gap:.45rem; font-weight:700; color:#1F4FD8;
         text-transform:uppercase; letter-spacing:.06em; font-size:.8rem;}
  .kind i {width:8px; height:8px; border-radius:50%; background:#1F4FD8; display:inline-block;}
  .mail-head {padding:1.4rem 1.6rem 1.2rem;}
  .mail-subject {font-size:1.45rem; font-weight:700; color:#0F172A; line-height:1.3;
                 margin-bottom:1rem;}
  .mail-from {display:flex; gap:.9rem; align-items:center;}
  .avatar {width:46px; height:46px; border-radius:50%; background:#E2E8F0; color:#0F172A;
           display:flex; align-items:center; justify-content:center; font-weight:700;
           font-size:1.05rem; flex-shrink:0;}
  .from-name {font-weight:700; color:#0F172A; font-size:1.02rem;}
  .from-addr {color:#334155; font-size:.92rem;}
  .mail-date {margin-left:auto; color:#1E293B; font-size:.92rem; text-align:right;
              white-space:nowrap;}
  .extracted {display:flex; flex-wrap:wrap; gap:.5rem 1.4rem; align-items:center;
              padding:.9rem 1.6rem; background:#F8FAFC; border-top:1px solid #E2E8F0;}
  .extracted .lbl {font-size:.88rem; font-weight:700; text-transform:none;
                   letter-spacing:0; color:#334155; margin-right:.2rem;}
  .xchip {display:inline-flex; align-items:center; gap:.45rem; font-size:.93rem;
          font-weight:600; color:#0F172A;}
  .xchip i {width:8px; height:8px; border-radius:50%; display:inline-block;}
  .xchip small {font-size:.78rem; font-weight:500; color:#334155;}
  .xchip.miss {color:#991B1B;}
  .mail-body {padding:1.5rem 1.6rem 1.8rem; font-size:1.06rem; line-height:1.8;
              color:#1E293B; max-height:640px; overflow:auto;}
  .mail-body p {margin:0 0 1.05rem 0;}
  .mail-body p.title {font-weight:700; letter-spacing:-.01em; color:#0F172A;}
  .mail-body .kv {margin:0 0 1.05rem 0;}
  .mail-body .grid {font-family:'JetBrains Mono', ui-monospace, Menlo, monospace;
                    font-size:.84rem; line-height:1.7; background:#F8FAFC;
                    border:1px solid #E2E8F0; border-radius:10px; padding:.9rem 1.1rem;
                    margin:0 0 1.05rem 0; overflow-x:auto; white-space:nowrap; color:#0F172A;}
  mark.hl {border-radius:3px; padding:.05rem .15rem; font-weight:inherit; color:inherit;
           border-bottom:2px solid;
           -webkit-box-decoration-break:clone; box-decoration-break:clone;}
  mark.hl .tag {font-family:'Inter', sans-serif; font-size:.62rem; font-weight:800;
                letter-spacing:.07em; text-transform:uppercase; color:#FFFFFF;
                border-radius:4px; padding:.08rem .38rem; margin-left:.4rem;
                vertical-align:.12rem;}

  /* --- the fields panel ---------------------------------------------- */
  .panel-title {font-size:1.25rem; font-weight:800; color:#0F172A;}
  .panel-sub {font-size:.98rem; color:#1E293B; margin:.2rem 0 1rem 0;}
  .panel-sub b {color:#15803D;}
  .flabel {display:flex; align-items:center; gap:.55rem; font-weight:700; color:#0F172A;
           font-size:1rem; margin:.5rem 0 .35rem 0;}
  .fbar {width:5px; height:1.15rem; border-radius:3px; display:inline-block;}
  .fstate {margin-left:auto; font-size:.74rem; font-weight:800; letter-spacing:.05em;
           text-transform:uppercase; border-radius:999px; padding:.12rem .6rem;}
  .fstate.ok {background:#DCFCE7; color:#14532D;}
  .fstate.no {background:#FEE2E2; color:#991B1B;}
  .found {font-size:.9rem; color:#1E293B; margin:.1rem 0 1rem 0;}
  .found q {font-weight:600; color:#0F172A; quotes:"“" "”";}
  .missing {font-size:.9rem; color:#991B1B; margin:.1rem 0 1rem 0; font-weight:600;}
  .note-nohistory {font-size:.92rem; color:#78350F; background:#FEF3C7; border:1px solid #FCD34D;
                   border-radius:10px; padding:.6rem .85rem; margin:-.3rem 0 1rem 0; font-weight:500;}

  .empty {text-align:center; padding:4rem 1rem; color:#1E293B; font-size:1.1rem;}
  .empty .big {font-size:3rem;}
  div[data-testid="stFileUploader"] section {border-radius:14px; padding:1.2rem;}
  div[data-testid="stFileUploader"] section small, div[data-testid="stFileUploader"] span {color:#1E293B;}

  /* --- estimation page ------------------------------------------------- */
  .section {font-size:.95rem; text-transform:uppercase; letter-spacing:.07em; color:#0F172A;
            font-weight:800; margin:2rem 0 .8rem 0;}
  .summary {display:flex; flex-wrap:wrap; gap:.5rem; margin:.1rem 0 1.2rem 0;}
  .summary span {background:#FFFFFF; border:1px solid #CBD5E1; border-radius:999px;
                 padding:.35rem .95rem; font-size:1rem; color:#1E293B;}
  .summary .src {background:transparent; border:none; color:#334155;}

  .conf .conf-top {display:flex; justify-content:space-between; gap:1.5rem; align-items:flex-start;}
  .conf-title {font-weight:800; font-size:1.3rem;}
  .conf-text {font-size:1.02rem; color:#1E293B; margin-top:.3rem; max-width:900px; line-height:1.55;}
  .conf-num {font-size:2.6rem; font-weight:800; line-height:1; text-align:right; white-space:nowrap;}
  .conf-num span {display:block; font-size:.82rem; font-weight:600; color:#1E293B; margin-top:.4rem;}
  .track {position:relative; height:12px; background:#E2E8F0; border-radius:999px; margin:1.3rem 0 1.6rem 0;}
  .track .fill {height:100%; border-radius:999px;}
  .track .tick {position:absolute; top:-6px; width:3px; height:24px; background:#0F172A; border-radius:2px;}
  .track .tick span {position:absolute; top:27px; left:50%; transform:translateX(-50%);
                     font-size:.82rem; font-weight:600; color:#0F172A; white-space:nowrap;}

  .opts {display:grid; grid-template-columns:repeat(3, 1fr); gap:1.2rem;}
  .opt {background:#FFFFFF; border:1px solid #D8DEE8; border-radius:16px; padding:1.4rem 1.6rem;
        position:relative; min-height:200px;}
  .opt.rec {border:2.5px solid #16A34A; box-shadow:0 8px 24px rgba(22,163,74,.14);}
  .opt.muted {background:#F8FAFC;}
  .opt.muted .opt-cost {color:#334155;}
  .badge {display:inline-block; font-size:.76rem; font-weight:800; text-transform:uppercase;
          letter-spacing:.06em; border-radius:6px; padding:.18rem .6rem; min-height:1.3rem;}
  .badge.rec {background:#DCFCE7; color:#14532D;}
  .badge.gen {background:#FEF3C7; color:#78350F;}
  .opt-name {font-size:1.4rem; font-weight:800; margin-top:.45rem; color:#0F172A;}
  .opt-desc {font-size:.98rem; color:#334155;}
  .opt-cost {font-size:2.6rem; font-weight:800; margin-top:.6rem; color:#0F172A;
             font-variant-numeric:tabular-nums; letter-spacing:-.02em;}
  .opt-detail {font-size:.92rem; color:#1E293B;}
  .opt-detail .up {color:#B91C1C; font-weight:700;}
  .opt-detail .down {color:#15803D; font-weight:700;}

  .pc .pc-top {display:flex; justify-content:space-between; align-items:flex-start;}
  .pc-id {font-weight:800; font-size:1.15rem; color:#0F172A;}
  .pc-sub {font-size:.95rem; color:#334155;}
  .pc-sim {font-size:2rem; font-weight:800; text-align:right; line-height:1; color:#0F172A;}
  .pc-sim span {display:block; font-size:.78rem; font-weight:600; color:#334155; margin-top:.2rem;}
  .card.pc {min-height:270px;}
  .pc-story {font-size:1.02rem; color:#1E293B; line-height:1.6; margin-top:1rem;}
  .pc-compare {font-size:.94rem; color:#334155; line-height:1.5; margin-top:.9rem;
               padding-top:.8rem; border-top:1px solid #E2E8F0;}

  /* --- knowledge base page -------------------------------------------- */
  .kpis {display:grid; grid-template-columns:repeat(4, 1fr); gap:1.2rem; margin-top:.4rem;}
  .kpi {background:#FFFFFF; border:1px solid #D8DEE8; border-radius:16px; padding:1.3rem 1.5rem;}
  .kpi-label {font-size:.84rem; color:#0F172A; text-transform:uppercase; letter-spacing:.06em; font-weight:700;}
  .kpi-value {font-size:2.4rem; font-weight:800; color:#0F172A; margin-top:.3rem;
              font-variant-numeric:tabular-nums; letter-spacing:-.02em;}
  .kpi-note {font-size:.92rem; color:#334155;}
  table.cov, table.cov tr, table.cov td, table.cov th {border:none !important;}
  table.cov thead tr th {background:transparent !important;}
  table.cov {width:100%; border-collapse:separate; border-spacing:5px; font-size:1rem;}
  table.cov th {font-size:.85rem; color:#0F172A; font-weight:700; text-align:center; padding:.3rem;}
  table.cov td {text-align:center; border-radius:7px; padding:.6rem .4rem;
                font-variant-numeric:tabular-nums; font-weight:700;}
  table.cov td.mat {text-align:left; font-weight:600; color:#0F172A; padding-left:0;}
  table.cov td.tot {color:#1E293B; font-weight:600;}
  table.cov td.zero {color:#78350F; background:#FEF3C7;}
  table.cov td.thin {outline:2px dashed #D97706; outline-offset:-2px;}
  .legend-intro {font-size:1rem; color:#1E293B; line-height:1.6; margin:0 0 1.1rem 0;}
  .lg-row {display:flex; align-items:center; gap:1rem; padding:.65rem 0;
           border-top:1px solid #E2E8F0; font-size:.98rem; color:#1E293B; line-height:1.45;}
  .lg-row b {color:#0F172A;}
  .lg-cell {width:64px; height:42px; border-radius:7px; flex-shrink:0; display:flex;
            align-items:center; justify-content:center; font-weight:700; font-size:1rem;}
  .lg-cell.thin {outline:2px dashed #D97706; outline-offset:-2px;}
  .lg-cell.zero {background:#FEF3C7; color:#78350F;}
  .why-card p {font-size:1.02rem; color:#1E293B; line-height:1.65; margin:0 0 .9rem 0;}
</style>
""", unsafe_allow_html=True)


# =====================================================================
# NAVIGATION
# =====================================================================
if "page" not in st.session_state:
    st.session_state.page = "Intake"


def go_to(page):
    st.session_state.page = page


def header():
    left, right = st.columns([1.2, 1], vertical_alignment="center")
    with left:
        st.markdown(
            '<div class="brand"><div class="logo">Impact<span>IQ</span></div>'
            '<div class="tag">Procurement risk agent'
            '<span class="synthetic">Synthetic prototype data</span></div></div>',
            unsafe_allow_html=True)
    with right:
        cols = st.columns(3)
        for i, (col, name) in enumerate(zip(cols, PAGES)):
            col.button(f"{i + 1}  ·  {name}", key=f"nav_{name}",
                       type="primary" if st.session_state.page == name else "secondary",
                       width="stretch", on_click=go_to, args=(name,))


def page_heading(title, subtitle):
    st.markdown(f'<div class="page-title">{title}</div>'
                f'<div class="page-sub">{subtitle}</div>', unsafe_allow_html=True)


# =====================================================================
# PAGE 1 - INTAKE
# =====================================================================
def list_samples():
    if not os.path.isdir(SAMPLES_FOLDER):
        return []
    return sorted(f for f in os.listdir(SAMPLES_FOLDER)
                  if f.lower().endswith((".eml", ".txt")))


def collect_spans(body, fields):
    """The exact stretch of the body each extracted field came from (one per field)."""
    spans = []
    for key, found in fields.items():
        if not found:
            continue
        explicit = [found[k] for k in ("span", "extra_span") if found.get(k)]
        if explicit:
            spans.extend((start, end, key) for start, end in explicit)
            continue
        # found in the subject line or e-mail header: mark its first mention in the body
        needle = found["evidence"] if key == "material" else str(found["value"])
        m = re.search(re.escape(needle), body, re.I)
        if m:
            spans.append((m.start(), m.end(), key))
    spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
    kept, cursor = [], 0
    for start, end, key in spans:
        if start >= cursor:                 # drop overlaps
            kept.append((start, end, key))
            cursor = end
    return kept


def block_kind(text):
    """How to lay out one paragraph of the document."""
    lines = [l for l in text.split("\n") if l.strip()]
    if any(re.search(r"\S {3,}\S", l) or re.fullmatch(r"\s*[-=_]{5,}\s*", l) for l in lines):
        return "grid"                         # columns, e.g. invoice line items
    if len(lines) >= 2 and sum(bool(re.match(r"^\s*[\w .()/#-]{1,32}:\s", l))
                               for l in lines) >= len(lines) / 2:
        return "kv"                           # "Supplier: ...", "Date: ..." lines
    if len(lines) == 1 and lines[0].isupper() and len(lines[0]) < 60:
        return "title"
    if len(lines) >= 2 and all(len(l.strip()) < 45 for l in lines):
        return "kv-plain"                     # short lines, e.g. a signature
    return "prose"


def render_body(body, fields):
    """The document body as clean HTML paragraphs with the evidence highlighted."""
    spans = collect_spans(body, fields)
    blocks = []
    for block in re.finditer(r"(?:[^\n]|\n(?!\s*\n))+", body):
        b_start, b_end = block.span()
        raw_block = block.group(0)
        b_start += len(raw_block) - len(raw_block.lstrip("\n"))   # skip leading blank lines
        b_end -= len(raw_block) - len(raw_block.rstrip("\n"))
        text = body[b_start:b_end]
        if not text.strip():
            continue
        kind = block_kind(text)

        def piece(s):
            s = html.escape(s)
            if kind == "grid":
                return s.replace(" ", "&nbsp;").replace("\n", "<br>")
            if kind in ("kv", "kv-plain"):
                return s.replace("\n", "<br>")
            return s.replace("\n", " ")       # prose: re-flow hard-wrapped lines

        out, cursor = [], b_start
        for start, end, key in spans:
            if start < b_start or end > b_end:
                continue
            label, bg, fg, accent = FIELD_STYLE[key]
            out.append(piece(body[cursor:start]))
            out.append(f'<mark class="hl" title="Extracted: {label}" '
                       f'style="background:{accent}1A;border-color:{accent}">'
                       f'{html.escape(body[start:end])}</mark>')
            cursor = end
        out.append(piece(body[cursor:b_end]))
        inner = "".join(out).strip()
        if kind == "grid":
            blocks.append(f'<div class="grid">{inner}</div>')
        elif kind == "kv":
            blocks.append(f'<div class="kv">{inner}</div>')
        elif kind == "kv-plain":
            blocks.append(f'<p>{inner}</p>')
        else:
            blocks.append(f'<p class="{kind}">{inner}</p>')
    return "".join(blocks)


def sender_parts(doc, fields):
    name, addr = parseaddr(doc["sender"]) if doc["sender"] else ("", "")
    if not name:
        name = fields["supplier"]["value"] if fields["supplier"] else (addr or "Unknown sender")
    initials = "".join(w[0] for w in re.findall(r"[A-Za-z]+", name)[:2]).upper() or "?"
    return name, addr, initials


def nice_date(raw):
    try:
        return parsedate_to_datetime(raw).strftime("%a %d %b %Y, %H:%M")
    except (TypeError, ValueError, IndexError):
        return raw


def document_viewer(intake):
    doc, fields = intake["result"]["document"], intake["result"]["fields"]
    name, addr, initials = sender_parts(doc, fields)
    subject = doc["subject"]
    if not subject:
        first = next((l.strip() for l in doc["body"].splitlines() if l.strip()), "")
        subject = first.capitalize() if first.isupper() else first

    chips = []
    for key, (label, bg, fg, accent) in FIELD_STYLE.items():
        found = fields[key]
        if found:
            value = found["value"]
            if key == "delay_days":
                value = f"{value} days"
            chips.append(f'<span class="xchip"><i style="background:{accent}"></i>'
                         f'<small>{label}</small>{html.escape(str(value))}</span>')
        else:
            chips.append(f'<span class="xchip miss"><small>{label}</small>not found</span>')

    return tidy(f"""
    <div class="mail">
      <div class="mail-bar"><span class="kind"><i></i>{doc['kind']}</span>
        <span>{html.escape(intake['source'])}</span></div>
      <div class="mail-head">
        <div class="mail-subject">{html.escape(subject)}</div>
        <div class="mail-from">
          <div class="avatar">{initials}</div>
          <div><div class="from-name">{html.escape(name)}</div>
               <div class="from-addr">{html.escape(addr) if addr else doc['kind']}</div></div>
          <div class="mail-date">{html.escape(nice_date(doc['sent']))}</div>
        </div>
      </div>
      <div class="mail-body">{render_body(doc['body'], fields)}</div>
      <div class="extracted"><span class="lbl">Extracted by ImpactIQ</span>{''.join(chips)}</div>
    </div>""")


def load_into_form(source_name, raw):
    """Run extraction on a new document and pre-fill the editable fields."""
    result = extraction.extract(source_name, raw)
    f = result["fields"]
    st.session_state.intake = {"source": source_name, "result": result}
    st.session_state.f_project = f["project"]["value"] if f["project"] else None
    st.session_state.f_material = f["material"]["value"] if f["material"] else None
    st.session_state.f_delay = f["delay_days"]["value"] if f["delay_days"] else None
    st.session_state.f_supplier = f["supplier"]["value"] if f["supplier"] else ""


def field_label(key, fields):
    label, _, _, accent = FIELD_STYLE[key]
    state = ('<span class="fstate ok">Found</span>' if fields[key]
             else '<span class="fstate no">Missing</span>')
    st.markdown(f'<div class="flabel"><span class="fbar" style="background:{accent}"></span>'
                f'{label}{state}</div>', unsafe_allow_html=True)


def field_evidence(key, fields):
    found = fields[key]
    if found and key == "supplier" and not found.get("span"):
        st.markdown('<div class="found">Taken from the e-mail sender</div>',
                    unsafe_allow_html=True)
    elif found:
        how = f" · {found['method']}" if found.get("method") else ""
        st.markdown(f'<div class="found">From the text: <q>{html.escape(str(found["evidence"]))}</q>{how}</div>',
                    unsafe_allow_html=True)
    else:
        st.markdown('<div class="missing">Not found in the document. Please fill in.</div>',
                    unsafe_allow_html=True)


def page_intake():
    page_heading("Incoming disruption",
                 "Upload the supplier's message: an e-mail, a delay notice or an invoice. "
                 "The system reads the key facts and you confirm them before anything "
                 "is estimated.")

    up_col, sample_col = st.columns([1.6, 1], gap="large")
    with up_col:
        uploaded = st.file_uploader("Upload a document (.eml or .txt)", type=["eml", "txt"])
    with sample_col:
        samples = list_samples()
        sample = st.selectbox("Or open a sample document", ["—"] + samples,
                              format_func=lambda f: "Choose a sample…" if f == "—"
                              else SAMPLE_LABELS.get(f, f))

    # Work out which document is "current" and extract it once.
    if uploaded is not None:
        raw, name = uploaded.getvalue(), uploaded.name
    elif sample != "—":
        with open(os.path.join(SAMPLES_FOLDER, sample), "rb") as fh:
            raw, name = fh.read(), sample
    else:
        raw = name = None

    if name is not None:
        signature = (name, len(raw), hash(raw))
        if st.session_state.get("doc_signature") != signature:
            st.session_state.doc_signature = signature
            load_into_form(name, raw)

    intake = st.session_state.get("intake")
    if not intake or name is None:
        st.markdown(
            '<div class="card empty"><div class="big">📨</div>'
            '<p><b>No document yet.</b><br>Drop a supplier e-mail (.eml) or a notice or '
            'invoice (.txt) above, or open one of the sample documents.</p></div>',
            unsafe_allow_html=True)
        return

    result = intake["result"]
    doc, fields = result["document"], result["fields"]

    st.write("")
    left, right = st.columns([1.7, 1], gap="large")

    with left:
        st.markdown(document_viewer(intake), unsafe_allow_html=True)

    with right:
        with st.container(border=True):
            found_count = sum(1 for k in ("project", "material", "delay_days") if fields[k])
            st.markdown(
                f'<div class="panel-title">What the system read</div>'
                f'<div class="panel-sub"><b>{found_count} of 3</b> required fields found '
                f'automatically. Correct anything that is wrong.</div>',
                unsafe_allow_html=True)

            field_label("project", fields)
            st.selectbox("Project", list(PROJECTS.keys()), key="f_project", index=None,
                         placeholder="Select project", label_visibility="collapsed",
                         format_func=lambda p: f"{p}  ·  {PROJECTS[p]['project_size']} project")
            field_evidence("project", fields)

            field_label("material", fields)
            st.selectbox("Material", list(extraction.MATERIAL_KEYWORDS.keys()),
                         key="f_material", index=None, placeholder="Select material",
                         label_visibility="collapsed",
                         format_func=lambda m: m if m in extraction.KNOWN_MATERIALS
                         else f"{m}  (no history yet)")
            field_evidence("material", fields)
            if st.session_state.f_material and \
                    st.session_state.f_material not in extraction.KNOWN_MATERIALS:
                st.markdown('<div class="note-nohistory">This material is not in the '
                            'knowledge base yet, so expect the system to withhold advice.</div>',
                            unsafe_allow_html=True)

            field_label("delay_days", fields)
            st.number_input("Delay (days)", min_value=1, max_value=30, step=1,
                            key="f_delay", placeholder="Number of days",
                            label_visibility="collapsed")
            field_evidence("delay_days", fields)

            field_label("supplier", fields)
            st.text_input("Supplier", key="f_supplier", label_visibility="collapsed")
            field_evidence("supplier", fields)

            ready = all([st.session_state.f_project, st.session_state.f_material,
                         st.session_state.f_delay])
            if st.button("Estimate costs  →", type="primary", width="stretch",
                         disabled=not ready):
                st.session_state.case = {
                    "project_id": st.session_state.f_project,
                    "project_size": PROJECTS[st.session_state.f_project]["project_size"],
                    "material": st.session_state.f_material,
                    "delay_days": int(st.session_state.f_delay),
                    "supplier": st.session_state.f_supplier,
                    "source": intake["source"],
                    "kind": doc["kind"],
                }
                st.session_state.pop("analysis", None)
                go_to("Estimation")
                st.rerun()


# =====================================================================
# PAGE 2 - ESTIMATION
# =====================================================================
ACTION_INFO = {
    "Accept":   "Absorb the delay and keep the current supplier",
    "Switch":   "Re-source the order from an alternative supplier",
    "Expedite": "Pay the supplier to speed up production or transport",
}
SEGMENT_COLOURS = {"Material": "#7C3AED", "Delay": "#EA580C", "Project size": "#1F4FD8"}
MAX_POINTS = {"Material": round(similarity.WEIGHT_MATERIAL * 100),
              "Delay": round(similarity.WEIGHT_DELAY * 100),
              "Project size": round(similarity.WEIGHT_PROJECT_SIZE * 100)}


def run_analysis(case):
    """Retrieval + estimates. Same steps as the evaluation, nothing new."""
    all_cases = database.load_cases()
    disruption = {k: case[k] for k in ("material", "delay_days", "project_size")}

    # THE CROSS-PROJECT RULE: a project never learns from its own history.
    other_projects = [c for c in all_cases if c["project_id"] != case["project_id"]]
    params = calculations.fit_baseline(other_projects)
    retrieved = similarity.find_similar_cases(disruption, other_projects,
                                              top_n=HOW_MANY_SIMILAR_CASES)
    for past in retrieved:
        past["points"] = similarity.contribution_breakdown(disruption, past)

    result = calculations.estimate_everything(
        case["material"], case["delay_days"], case["project_size"], retrieved, params)
    comparable = similarity.has_comparable_history(retrieved)

    return {
        "case": case,
        "retrieved": retrieved,
        "result": result,
        "avg_similarity": similarity.average_similarity(retrieved),
        "comparable": comparable,
        # What we show and save: the full estimate when history is
        # comparable, otherwise only the generic (baseline) estimate.
        "shown": result["blended"] if comparable else result["baseline"],
        "searched": len(other_projects),
        "excluded": len(all_cases) - len(other_projects),
        "projects_searched": len({c["project_id"] for c in other_projects}),
    }


def confidence_bar(avg, comparable):
    threshold = similarity.MIN_SIMILARITY_FOR_ADVICE
    colour = "#16A34A" if comparable else "#D97706"
    title = ("Comparable history found" if comparable
             else "No comparable history — advice withheld")
    text = ("The past cases below are similar enough to correct the estimate."
            if comparable else
            "Our tests showed that history this different makes estimates <b>worse</b> "
            "than ignoring it (+10% error at 60% similarity). The system shows only the "
            "generic estimate and makes no recommendation.")
    return f"""
    <div class="card conf" style="border-left:5px solid {colour}">
      <div class="conf-top">
        <div><div class="conf-title" style="color:{colour}">{title}</div>
             <div class="conf-text">{text}</div></div>
        <div class="conf-num" style="color:{colour}">{avg}%<span>avg. similarity of top {HOW_MANY_SIMILAR_CASES}</span></div>
      </div>
      <div class="track"><div class="fill" style="width:{avg}%;background:{colour}"></div>
        <div class="tick" style="left:{threshold}%"><span>advice threshold {threshold}%</span></div></div>
    </div>"""


def option_card(action, analysis):
    result, comparable = analysis["result"], analysis["comparable"]
    shown = analysis["shown"][action]
    recommended = comparable and action == result["recommendation"]
    classes = "opt" + (" rec" if recommended else "") + ("" if comparable else " muted")
    badge = ('<span class="badge rec">Recommended</span>' if recommended else
             '<span class="badge gen">Generic estimate</span>' if not comparable else
             '<span class="badge" style="visibility:hidden">·</span>')
    if comparable:
        base, final = result["baseline"][action], result["blended"][action]
        diff = final - base
        arrow = "▲" if diff > 0 else "▼" if diff < 0 else "="
        detail = (f'generic {money(base)} <span class="{"up" if diff > 0 else "down"}">'
                  f'{arrow} {money(abs(diff))}</span> from comparable cases')
    else:
        detail = "whole-database average only · not a recommendation"
    return f"""
    <div class="{classes}">
      {badge}
      <div class="opt-name">{action}</div>
      <div class="opt-desc">{ACTION_INFO[action]}</div>
      <div class="opt-cost">{money(shown)}</div>
      <div class="opt-detail">{detail}</div>
    </div>"""


ACTION_PHRASE = {
    "Accept": "accepted the delay",
    "Switch": "switched to another supplier",
    "Expedite": "paid to expedite the delivery",
}


ACTION_GERUND = {"Accept": "accepting the delay", "Switch": "switching supplier",
                 "Expedite": "expediting"}


def material_words(name):
    """'Structural steel' -> 'structural steel', but 'HVAC rooftop units' stays."""
    return name if name[:2].isupper() else name[0].lower() + name[1:]


def describe_case(past, case):
    """A plain-language description of a past case, and how it compares."""
    days = past["delay_days"]
    article = "An" if str(days).startswith("8") or days in (11, 18) else "A"
    story = (f"{article} {days}-day delay on {material_words(past['material'])} for a "
             f"{past['project_size'].lower()} project. The team "
             f"{ACTION_PHRASE[past['chosen_action']]}, which cost "
             f"<b>{money(past['actual_cost'])}</b>.")
    if past["chosen_action"] != past["optimal_action"]:
        story += (f" In hindsight, {ACTION_GERUND[past['optimal_action']]} would have "
                  "been cheaper.")

    same = []
    same.append("same material" if past["material"] == case["material"]
                else f"a different material ({material_words(past['material'])})")
    same.append("same project size" if past["project_size"] == case["project_size"]
                else f"a {past['project_size'].lower()} instead of a "
                     f"{case['project_size'].lower()} project")
    gap = past["delay_days"] - case["delay_days"]
    same.append("same delay length" if gap == 0 else
                f"{abs(gap)} day{'s' if abs(gap) != 1 else ''} "
                f"{'longer' if gap > 0 else 'shorter'} delay")
    compared = "Compared with this disruption: " + ", ".join(same) + "."
    return story, compared


def case_card(past, case):
    story, compared = describe_case(past, case)
    return f"""
    <div class="card pc">
      <div class="pc-top"><div><div class="pc-id">Case {past['case_id']}</div>
        <div class="pc-sub">Project {past['project_id']} · {past['project_size']}</div></div>
        <div class="pc-sim">{past['similarity']}%<span>similar</span></div></div>
      <div class="pc-story">{story}</div>
      <div class="pc-compare">{html.escape(compared)}</div>
    </div>"""


def page_estimation():
    case = st.session_state.get("case")
    if not case:
        st.markdown("### Estimation")
        st.info("Start on **1 · Intake**: upload a document and press *Estimate costs*.")
        return

    if st.session_state.get("analysis", {}).get("case") != case:
        st.session_state.analysis = run_analysis(case)
    analysis = st.session_state.analysis
    result = analysis["result"]

    # --- what we are estimating --------------------------------------
    top_l, top_r = st.columns([5, 1])
    with top_l:
        st.markdown('<div class="page-title">Cost estimate</div>', unsafe_allow_html=True)
        known = "" if case["material"] in extraction.KNOWN_MATERIALS else " (no history)"
        st.markdown(
            f'<div class="summary">'
            f'<span><b>{html.escape(case["supplier"] or "Unknown supplier")}</b></span>'
            f'<span>Project <b>{case["project_id"]}</b> · {case["project_size"]}</span>'
            f'<span><b>{html.escape(case["material"])}</b>{known}</span>'
            f'<span><b>{case["delay_days"]} days</b> late</span>'
            f'<span class="src">from {html.escape(case["source"])}</span></div>',
            unsafe_allow_html=True)
    with top_r:
        st.write("")
        st.button("← Edit fields", on_click=go_to, args=("Intake",), width="stretch")

    # --- confidence ---------------------------------------------------
    st.markdown(tidy(confidence_bar(analysis["avg_similarity"], analysis["comparable"])),
                unsafe_allow_html=True)

    # --- the three options --------------------------------------------
    st.markdown('<div class="section">Three ways to respond</div>', unsafe_allow_html=True)
    st.markdown(tidy('<div class="opts">' + "".join(option_card(a, analysis)
                for a in calculations.ACTIONS) + "</div>"), unsafe_allow_html=True)

    if analysis["comparable"] and result["baseline_recommendation"] != result["recommendation"]:
        st.write("")
        st.info(f"**The comparable cases changed the decision.** Without them, the "
                f"system would have chosen **{result['baseline_recommendation']}**.")

    # --- the evidence ---------------------------------------------------
    heading = ("The past cases this is based on" if analysis["comparable"] else
               "Closest past cases — too different to use")
    st.markdown(f'<div class="section">{heading}</div>', unsafe_allow_html=True)
    st.caption(
        f"Searched **{analysis['searched']} cases** from {analysis['projects_searched']} "
        f"other projects. {analysis['excluded']} cases from {case['project_id']} itself "
        "were excluded: a project never learns from its own history.")
    cols = st.columns(len(analysis["retrieved"]))
    for col, past in zip(cols, analysis["retrieved"]):
        col.markdown(tidy(case_card(past, case)), unsafe_allow_html=True)

    st.write("")
    with st.expander("How the estimate was calculated"):
        table = pd.DataFrame({
            "Generic (whole database)": result["baseline"],
            "Correction from past cases": {a: f"× {result['factors'][a]:.2f}"
                                           for a in calculations.ACTIONS},
            "History-corrected": result["historical"],
            "Final estimate": result["blended"],
        }).loc[calculations.ACTIONS]
        for c in ("Generic (whole database)", "History-corrected", "Final estimate"):
            table[c] = table[c].map(money)
        st.dataframe(table, width="stretch")
        st.markdown(
            f"1. **Generic estimate:** average cost per delay day (Accept, Expedite) or "
            f"flat switching cost, averaged over the other projects' cases of the same "
            f"size ({case['project_size']}). The material is ignored.\n"
            f"2. **Correction:** on the {HOW_MANY_SIMILAR_CASES} most similar cases, how much "
            f"did reality differ from that generic rule? That ratio is applied here.\n"
            f"3. **Final estimate** = {1 - calculations.BLEND_WEIGHT_HISTORY:.0%} generic + "
            f"{calculations.BLEND_WEIGHT_HISTORY:.0%} history-corrected.\n"
            f"4. **Advice threshold:** below {similarity.MIN_SIMILARITY_FOR_ADVICE}% average "
            "similarity, only the generic estimate is shown and nothing is recommended.")

    # --- the manager decides -------------------------------------------------
    st.markdown('<div class="section">Manager decision</div>', unsafe_allow_html=True)
    show_manager_decision(analysis)


def show_manager_decision(analysis):
    if analysis.get("saved_case_id"):
        st.success(f"**Case {analysis['saved_case_id']} saved to the knowledge base.** "
                   "It is now part of every future search — on other projects.")
        st.button("View in knowledge base  →", type="primary",
                  on_click=go_to, args=("Knowledge base",))
        return

    with st.container(border=True):
        st.caption("The system advises, the manager decides. Once the disruption is "
                   "resolved, record what was done and what it really cost.")
        c1, c2, c3 = st.columns([1.4, 1, 0.8])
        default = (calculations.ACTIONS.index(analysis["result"]["recommendation"])
                   if analysis["comparable"] else 0)
        with c1:
            chosen = st.radio("Action taken", calculations.ACTIONS, index=default,
                              horizontal=True, key="decision_action")
        with c2:
            actual = st.number_input("Actual cost (€)", min_value=0, step=500,
                                     value=int(analysis["shown"][chosen]),
                                     key=f"decision_cost_{chosen}")
        with c3:
            st.write("")
            save = st.button("Save outcome", type="primary", width="stretch")
        st.caption("Prototype note: the two options not taken are stored with the "
                   "system's estimates. In reality you only learn what the chosen option cost.")

    if save:
        case = analysis["case"]
        costs = dict(analysis["shown"])
        costs[chosen] = int(actual)
        new_case = {
            "case_id": database.next_case_id(database.load_cases()),
            "project_id": case["project_id"],
            "material": case["material"],
            "delay_days": case["delay_days"],
            "project_size": case["project_size"],
            "accept_cost": costs["Accept"],
            "switch_cost": costs["Switch"],
            "expedite_cost": costs["Expedite"],
            "optimal_action": min(calculations.ACTIONS, key=lambda a: costs[a]),
            "chosen_action": chosen,
            "actual_cost": int(actual),
        }
        database.add_case(new_case)
        analysis["saved_case_id"] = new_case["case_id"]
        st.session_state.setdefault("added_this_session", []).append(new_case["case_id"])
        st.rerun()


# =====================================================================
# PAGE 3 - KNOWLEDGE BASE
# =====================================================================
SIZE_ORDER = ["Small", "Medium", "Large"]
THIN_SEGMENT = 10          # fewer cases than this in a segment = thin coverage


def kpi(label, value, note=""):
    return (f'<div class="kpi"><div class="kpi-label">{label}</div>'
            f'<div class="kpi-value">{value}</div><div class="kpi-note">{note}</div></div>')


def coverage_grid(frame):
    """Material x project size table, shaded by how many cases each segment holds."""
    counts = frame.groupby(["material", "project_size"]).size()
    materials = sorted(frame["material"].unique(),
                       key=lambda m: (m not in extraction.KNOWN_MATERIALS, m))
    top = max(counts.max(), 1)
    head = "".join(f"<th>{s}</th>" for s in SIZE_ORDER)
    rows = []
    for m in materials:
        cells = []
        for s in SIZE_ORDER:
            n = int(counts.get((m, s), 0))
            if n == 0:
                cells.append('<td class="zero">—</td>')
            else:
                alpha = 0.12 + 0.78 * n / top
                colour = "#fff" if alpha > 0.55 else "#111827"
                thin = " thin" if n < THIN_SEGMENT else ""
                cells.append(f'<td class="n{thin}" style="background:rgba(31,79,216,{alpha:.2f});'
                             f'color:{colour}">{n}</td>')
        total = int(counts.loc[m].sum()) if m in counts.index.get_level_values(0) else 0
        rows.append(f"<tr><td class='mat'>{html.escape(m)}</td>{''.join(cells)}"
                    f"<td class='tot'>{total}</td></tr>")
    return (f'<table class="cov"><thead><tr><th></th>{head}<th>Total</th></tr></thead>'
            f'<tbody>{"".join(rows)}</tbody></table>')


def page_storage():
    cases = database.load_cases()
    original = database.original_case_ids()
    just_now = set(st.session_state.get("added_this_session", []))

    frame = pd.DataFrame(cases)
    frame["origin"] = ["Added" if cid not in original else "Simulated"
                       for cid in frame["case_id"]]
    added = int((frame["origin"] == "Added").sum())

    page_heading("Knowledge base",
                 "Every resolved disruption becomes a case. The database is the asset: "
                 "each new case makes the next estimate on a similar disruption better.")

    st.markdown(tidy('<div class="kpis">'
        + kpi("Cases stored", f"{len(frame):,}", f"{len(original)} simulated · {added} added here")
        + kpi("Projects", frame["project_id"].nunique(), "sizes: small · medium · large")
        + kpi("Material categories", frame["material"].nunique(),
              "each one is its own segment")
        + kpi("Total disruption cost", money(frame["actual_cost"].sum()),
              f"average {money(frame['actual_cost'].mean())} per case")
        + "</div>"), unsafe_allow_html=True)

    # --- coverage --------------------------------------------------------
    left, right = st.columns([1.25, 1], gap="large")
    with left:
        st.markdown('<div class="section">Coverage by segment</div>', unsafe_allow_html=True)
        st.markdown(tidy(f'<div class="card">{coverage_grid(frame)}</div>'),
                    unsafe_allow_html=True)
    with right:
        st.markdown('<div class="section">How to read the grid</div>', unsafe_allow_html=True)
        st.markdown(tidy(f"""
        <div class="card legend-card">
          <p class="legend-intro">Each cell is one <b>segment</b>: a material on a project
          of a given size. The number is how many past cases the system can compare
          against there.</p>
          <div class="lg-row"><span class="lg-cell" style="background:rgba(31,79,216,.90);color:#fff">35</span>
            <div><b>Deep coverage</b><br>Many comparable cases, strongest estimates</div></div>
          <div class="lg-row"><span class="lg-cell" style="background:rgba(31,79,216,.40);color:#0F172A">16</span>
            <div><b>Good coverage</b><br>Enough cases to correct the estimate</div></div>
          <div class="lg-row"><span class="lg-cell thin" style="background:rgba(31,79,216,.14);color:#0F172A">3</span>
            <div><b>Thin coverage</b><br>Fewer than {THIN_SEGMENT} cases, treat advice with care</div></div>
          <div class="lg-row"><span class="lg-cell zero">—</span>
            <div><b>No history</b><br>Nothing comparable, the system withholds advice</div></div>
        </div>"""), unsafe_allow_html=True)

    # --- the table ----------------------------------------------------------
    st.markdown('<div class="section">All cases</div>', unsafe_allow_html=True)
    f1, f2, f3, f4 = st.columns([1.4, 1.4, 1, 1])
    with f1:
        pick_material = st.multiselect("Material", sorted(frame["material"].unique()),
                                       placeholder="All materials")
    with f2:
        pick_project = st.multiselect("Project", sorted(frame["project_id"].unique()),
                                      placeholder="All projects")
    with f3:
        pick_action = st.multiselect("Action taken", calculations.ACTIONS,
                                     placeholder="All actions")
    with f4:
        st.write("")
        only_added = st.toggle("Only cases added here", value=False)

    view = frame.copy()
    if pick_material:
        view = view[view["material"].isin(pick_material)]
    if pick_project:
        view = view[view["project_id"].isin(pick_project)]
    if pick_action:
        view = view[view["chosen_action"].isin(pick_action)]
    if only_added:
        view = view[view["origin"] == "Added"]
    view = view.sort_values("case_id", key=lambda c: c.astype(int), ascending=False)

    display = pd.DataFrame({
        "Case": view["case_id"],
        "Source": view["origin"],
        "Project": view["project_id"],
        "Size": view["project_size"],
        "Material": view["material"],
        "Delay (days)": view["delay_days"],
        "Action taken": view["chosen_action"],
        "Actual cost": view["actual_cost"],
        "Cheapest option": view["optimal_action"],
    })

    def shade(row):
        if row["Case"] in just_now:
            return ["background-color:#DCFCE7; font-weight:600"] * len(row)
        if row["Source"] == "Added":
            return ["background-color:#F0FDF4"] * len(row)
        return [""] * len(row)

    st.dataframe(display.style.apply(shade, axis=1).format({"Actual cost": "€{:,.0f}"}),
                 width="stretch", height=440, hide_index=True)

    note = f"Showing {len(display)} of {len(frame)} cases, newest first."
    if just_now:
        note += " Green rows were added in this session."
    st.caption(note)

    # --- actions ---------------------------------------------------------------
    a1, a2, _ = st.columns([1, 1, 2])
    with a1:
        st.download_button("Download CSV", data=view.drop(columns="origin").to_csv(index=False),
                           file_name="knowledge_base.csv", mime="text/csv",
                           width="stretch")
    with a2:
        with st.popover("Reset demo data", width="stretch", disabled=added == 0):
            st.markdown(f"Remove the **{added} case{'s' if added != 1 else ''}** added "
                        f"in the app and go back to the {len(original)} simulated cases?")
            if st.button("Yes, reset", type="primary"):
                database.reset_to_original()
                st.session_state.pop("added_this_session", None)
                if "analysis" in st.session_state:
                    st.session_state.analysis.pop("saved_case_id", None)
                st.rerun()


# ---------------------------------------------------------------------
database.ensure_original_backup()
header()
{"Intake": page_intake,
 "Estimation": page_estimation,
 "Knowledge base": page_storage}[st.session_state.page]()
