# Financial Files Extracter
This tool was developped for the Ready Plan Go - Spring 2026 Dev Challenge.

## Goal

The goal of this tool is first to parse, clean and transform financial data. And afterwards, to present the data in a clean overview.

## File Layout

The repo now includes a starter architecture for the extraction pipeline:

- `extractors/parse_excel.py` for spreadsheet list of invoices.
- `extractors/parse_pdf.py` for text-based PDF bank statements.
- `extractors/parse_images.py` for receipt images and OCR fallback wiring.
- `main.py` as the orchestrator that scans `shoebox/`, filters personal expenses from `notes.txt`, and writes `app_data.json`.
- `server.py` as a Flask API backend with `GET /api/dashboard` and `POST /api/sync`.
- `frontend/` as a minimal dashboard shell that consumes the API.
- `tests/` as a small unittest suite for the data pipeline and API routes.



### Run order

1. Install Python dependencies from `requirements.txt`.
2. Run `python main.py` to generate `app_data.json`.
3. Run `python server.py` to serve the API and frontend shell.

### Test command

Run the full unit test suite with:

```bash
python -m unittest discover -s tests
```

The suite includes both mocked unit tests and real-file parser tests against the sample files in `shoebox/`.
