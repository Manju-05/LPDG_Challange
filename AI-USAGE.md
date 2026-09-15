# AI Usage Statement (AI-USAGE.md)

This document details the usage of AI coding tools during the development of the LPDG Innovation Hub Selection Challenge 2026 (Part 1 & Part 2: Track B — Software Development).

---

## 1. What AI Tools Were Used For

AI assistants were utilized as pair-programming aids for:
- Initial project structure scaffolding and boilerplate generation.
- Parsing and summarizing the challenge requirements and constraints.
- Drafting synthetic test fixtures and unit test templates.
- Drafting documentation templates for `README.md` and `DECISIONS.md`.

---

## 2. Independent Verification & Manual Review

All code, queries, and logic were independently verified through:
- Direct execution of the full test suite via `pytest`.
- Verification of the official validator script (`validate_submission.py`) against generated outputs.
- Verification of data types, schema integrity, and column nullability across all dataset files.
- Manual audit of temporal boundaries to ensure zero future data leakage.

---

## 3. Real AI Mistakes Spotted and Corrected

During development, several concrete issues were identified in AI-assisted code generation and immediately resolved:

### Mistake 1: Unicode Greek Sigma in Reason Strings Breaking Windows CP1252 Consoles
- **What happened**: The AI generated reason-formatting code using the Greek unicode character $\sigma$ (`"{flagged_hours}h >3σ breach"`).
- **How it was caught**: Running the prediction inspector on Windows terminal failed with `UnicodeEncodeError: 'charmap' codec can't encode character '\u03c3' in position 249: character maps to <undefined>`.
- **How it was fixed**: Replaced unicode $\sigma$ with universal ASCII text (`>3-sigma`), ensuring 100% portability across all operating systems, terminals, and locale configurations.

### Mistake 2: Pandas 3.0 Datetime vs Date Comparison TypeError
- **What happened**: The AI wrote `decom_dates >= monday`, attempting to directly compare a pandas `datetime64[s]` Series (containing `NaT` values) with a Python standard library `datetime.date` object.
- **How it was caught**: Running the automated test suite with `pytest` raised `TypeError: Invalid comparison between dtype=datetime64[s] and date`.
- **How it was fixed**: Converted comparison operands to `pd.Timestamp(monday)` and explicitly handled `isna()` masks before comparison.

### Mistake 3: Assumed Default UTF-8 Encoding for German Dataset CSVs
- **What happened**: Standard `pd.read_csv()` calls assumed default UTF-8 encoding across all CSV files.
- **How it was caught**: Reading `gateway_master.csv` threw `UnicodeDecodeError: 'utf-8' codec can't decode byte 0xdf in position 161: invalid continuation byte` due to German character encodings (e.g., `ß` = 0xDF in ISO-8859-1 / Latin-1).
- **How it was fixed**: Explicitly set `encoding='latin1'` on `gateway_master.csv`, `field_visits.csv`, and `meter_read_success.csv`, ensuring flawless ingestion of all German text and umlauts.
