from __future__ import annotations

from pathlib import Path

from flask import Flask, jsonify, send_from_directory

from main import OUTPUT_FILE, read_app_data, write_app_data

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
        write_app_data(OUTPUT_FILE)
        return ("", 204)

    return app


def run(host: str = "127.0.0.1", port: int = 8000) -> None:
    app = create_app()
    print(f"Serving dashboard on http://{host}:{port}")
    app.run(host=host, port=port, debug=False)


if __name__ == "__main__":
    run()
