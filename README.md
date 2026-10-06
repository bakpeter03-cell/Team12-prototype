# ImpactIQ — Procurement AI Agent (prototype)

**Team 12 · AI Strategy Lab** · Sofia Papakosta, Franciszek Oleś, Péter Bak, Felix Brugger

> All data in this project is **simulated**. No real construction or procurement records are used.

---

## What is ImpactIQ?

When a supplier delivery is late, a general contractor has three choices:

| Option | What it means |
|---|---|
| **Accept** | Wait for the delayed delivery |
| **Switch** | Order from a different supplier |
| **Expedite** | Pay extra to speed the delivery up |

ImpactIQ reads the supplier's message, estimates what each option will cost, and recommends the cheapest one. It does this by looking at **similar disruptions from other projects**. Every resolved disruption is saved, so the database (and the advice) keeps growing.

The app has three pages:

1. **Intake** – upload a supplier e-mail, delay notice or invoice. ImpactIQ finds the project, material, delay and supplier, and highlights where it found them.
2. **Estimation** – the estimated cost of Accept / Switch / Expedite, the three most similar past cases, and a recommendation. If no comparable history exists, ImpactIQ **withholds advice** instead of guessing.
3. **Knowledge base** – every stored case, and how many cases exist per material and project size.

---

## How to download and run it

You need about 10 minutes the first time. After that, starting the app takes 10 seconds.

### Step 1 – Install Python (skip if you already have it)

1. Go to **https://www.python.org/downloads/** and download the latest Python 3 (version 3.9 or newer).
2. Run the installer.
   - **Windows:** on the first screen, tick **"Add python.exe to PATH"** before clicking *Install Now*.
   - **Mac:** click through the installer with the default options.

### Step 2 – Download the project

1. On this GitHub page, click the green **`<> Code`** button (top right, above the file list).
2. Click **Download ZIP**.
3. Find the file in your **Downloads** folder and unzip it (double-click on Mac; right-click → *Extract All* on Windows).
4. You now have a folder called something like **`impactiq-prototype-main`**. You can move it anywhere, e.g. to your Desktop.

### Step 3 – Open a terminal in that folder

- **Mac:** open the **Terminal** app (press `Cmd + Space`, type *Terminal*, press Enter). Type `cd ` (with a space after it), then **drag the project folder into the Terminal window** and press Enter.
- **Windows:** open the project folder in File Explorer, click the address bar at the top, type `cmd` and press Enter. A black Command Prompt window opens, already in the right folder.

### Step 4 – Install the required packages (only the first time)

Copy this line, paste it into the terminal and press Enter:

**Mac**
```
python3 -m pip install -r requirements.txt
```

**Windows**
```
py -m pip install -r requirements.txt
```

Wait until it finishes (it may take a minute or two).

### Step 5 – Start the app

**Mac**
```
python3 -m streamlit run app.py
```

**Windows**
```
py -m streamlit run app.py
```

Your web browser opens ImpactIQ automatically. If it does not, open **http://localhost:8501** in your browser.

Keep the terminal window open while you use the app. To stop it, click the terminal and press `Ctrl + C`.

**Next time:** you only need Step 3 and Step 5.

---

## Try the demo (2 minutes)

1. On **Intake**, open the dropdown **"Or open a sample document"** and choose a document. (You can also upload your own `.eml` or `.txt` file.)
2. Check the fields on the right and press **Estimate costs →**.
3. On **Estimation**, see the three costs, the recommendation and the similar past cases.
4. Optionally record a decision with **Save outcome**, then open **Knowledge base** to see the new case.

Good samples to show:

| Sample | What it shows |
|---|---|
| Delay notice · HVAC rooftop units (P12) | 98% match – the past cases **change** the recommendation |
| Email · Structural steel delay (P07) | 100% match – a clean, confident estimate |
| Email · Steel, three-week delay (P11) | 79% match – advice with lower confidence |
| Delay notice · Curtain wall glazing (P03) | 60% match – **advice withheld**, no comparable history |

To remove the cases you added during a demo, press **Reset demo data** on the Knowledge base page.

---

## Main result

We tested 200 new disruptions against a database of 400 simulated past disruptions (20 projects, 6 materials, 3 project sizes). A project was never allowed to learn from its own history.

| What the available past cases have in common | Similarity | Change in estimation error |
|---|---|---|
| Same material, same size, similar delay | 98% | **−41%** |
| Same material, same size, different delay | 77% | **−39%** |
| Different material, same size | 60% | +10% (worse) |
| Nothing in common | 24% | +9% (worse) |

**In short:** comparable history makes cost estimates about 40% more accurate. Non-comparable history makes them *worse* than using no history at all — which is why ImpactIQ withholds advice below 70% similarity.

To re-run the experiment yourself: `python3 evaluation.py` (Mac) or `py evaluation.py` (Windows).

---

## What is in this folder

| File / folder | What it does |
|---|---|
| `app.py` | The ImpactIQ interface (screens only, no calculations) |
| `extraction.py` | Reads the supplier message and finds project, material, delay and supplier |
| `similarity.py` | Scores how similar two disruptions are (40% material, 30% delay, 30% size) |
| `calculations.py` | Estimates the cost of Accept / Switch / Expedite |
| `database.py` | Reads and saves cases in the CSV database |
| `data_generator.py` | Creates the simulated dataset |
| `evaluation.py` | Runs the experiment behind the results above |
| `data/` | The 400 past cases and the experiment results (CSV, opens in Excel) |
| `mock_documents/` | 8 sample supplier e-mails, notices and invoices |
| `docs/METHODOLOGY.md` | Full method, data sources, all results and limitations |
| `app_legacy.py` | The earlier version of the interface, with an evaluation page |

---

## Limitations (short version)

- All data is simulated, so the 41% should be read as an upper bound.
- The 40/30/30 similarity weights are our assumption; alternatives were not tested.
- Only material, delay and project size are compared; location, season, contract type and supplier are not.
- The database stores the true cost of all three options; in reality only the chosen option's cost is known.

The full list, the sources and the detailed method are in **[docs/METHODOLOGY.md](docs/METHODOLOGY.md)**.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `python3: command not found` (Mac) or `'py' is not recognized` (Windows) | Python is not installed, or (Windows) "Add to PATH" was not ticked. Re-run the Python installer (Step 1). |
| `No module named streamlit` | Step 4 was skipped or failed. Run it again. |
| `No such file or directory: requirements.txt` | The terminal is not in the project folder. Redo Step 3. |
| The browser does not open | Open http://localhost:8501 manually. |
| `Port 8501 is already in use` | The app is already running in another terminal window. Close it, or use the address shown in the terminal. |
