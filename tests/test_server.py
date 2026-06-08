from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server


class ServerTests(unittest.TestCase):
    def test_dashboard_returns_404_when_data_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            missing_output = Path(temp_dir) / "app_data.json"
            with patch.object(server, "OUTPUT_FILE", missing_output):
                app = server.create_app()
                with app.test_client() as client:
                    response = client.get("/api/dashboard")

        self.assertEqual(response.status_code, 404)

    def test_sync_writes_data_and_dashboard_reads_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "app_data.json"
            frontend_dir = Path(temp_dir) / "frontend"
            frontend_dir.mkdir()
            (frontend_dir / "index.html").write_text("<html></html>", encoding="utf-8")

            def fake_write_app_data(target_file: Path, shoebox_dir: Path | None = None) -> Path:
                target_file.write_text('{"source_folder": "demo", "records": [], "warnings": []}', encoding="utf-8")
                return target_file

            with patch.object(server, "OUTPUT_FILE", output_file), patch.object(server, "FRONTEND_DIR", frontend_dir), patch.object(server, "write_app_data", side_effect=fake_write_app_data):
                app = server.create_app()
                with app.test_client() as client:
                    sync_response = client.post("/api/sync")
                    dashboard_response = client.get("/api/dashboard")

        self.assertEqual(sync_response.status_code, 204)
        self.assertEqual(dashboard_response.status_code, 200)
        self.assertEqual(dashboard_response.get_json(), {"source_folder": "demo", "records": [], "warnings": []})


if __name__ == "__main__":
    unittest.main()