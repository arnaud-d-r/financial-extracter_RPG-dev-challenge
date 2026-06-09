from __future__ import annotations

from datetime import datetime
from datetime import date
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory

from main import OUTPUT_FILE, build_app_data, read_app_data, write_app_data, patch_app_data

ROOT = Path(__file__).resolve().parent
FRONTEND_DIR = ROOT / "frontend"


def create_app() -> Flask:
    app = Flask(__name__, static_folder=str(FRONTEND_DIR), static_url_path="")

    @app.get("/")
    def index() -> object:
        return send_from_directory(FRONTEND_DIR, "index.html")

    @app.get("/api/dashboard")
    def dashboard() -> object:
        if not OUTPUT_FILE.exists():
            return jsonify({"error": "app_data.json not found"}), 404
        return jsonify(read_app_data(OUTPUT_FILE).to_dict())

    @app.post("/api/sync")
    def sync() -> object:
        data = build_app_data()
        write_app_data(data, OUTPUT_FILE)
        return ("", 204)
    
    @app.patch("/api/transaction/warning")
    def patch_warning() -> object:
        try:
            request_data = request.get_json()
        except Exception:
            return jsonify({"error": "Invalid JSON payload"}), 400
        if not request_data:
            return jsonify({"error": "Invalid JSON payload"}), 400
        match = request_data.get("match", {})
        raw_date = match.get("date")
        parsed_date = None

        if raw_date:
            try:
                parsed_date = date.fromisoformat(str(raw_date))
            except (ValueError, TypeError):
                parsed_date = None
        request_tuple = (match.get("source_file"), parsed_date, match.get("amount"))
        success = patch_app_data(request_tuple, request_data.get("remove_warning"))
        if not success:
            return jsonify({"error": "Failed to patch transaction warning"}), 400
        return ("", 204)

    return app


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    app = create_app()
    print(f"Serving dashboard on http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run()
