from __future__ import annotations

import datetime
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import server
from extractors.models import (
    AppDataBundle,
    Transaction,
    TransactionCategory,
    Warnings,
)


# ─── Factories ────────────────────────────────────────────────────────────────


def make_transaction(**kwargs) -> Transaction:
    defaults = dict(
        source_file="statement.pdf",
        category=TransactionCategory.BANK_STATEMENT,
        vendor="Acme Corp",
        date=datetime.date(2025, 1, 15),
        amount=100.0,
    )
    return Transaction(**{**defaults, **kwargs})


def make_bundle(*records: Transaction) -> AppDataBundle:
    return AppDataBundle(records=list(records))


def bundle_json(*records: Transaction) -> str:
    return json.dumps(make_bundle(*records).to_dict())


# ─── Helpers ─────────────────────────────────────────────────────────────────


class ServerTestCase(unittest.TestCase):
    """Base class that wires up a temp output file and a minimal frontend dir."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        tmp = Path(self._tmp.name)

        self.output_file = tmp / "app_data.json"

        self.frontend_dir = tmp / "frontend"
        self.frontend_dir.mkdir()
        (self.frontend_dir / "index.html").write_text("<html></html>", encoding="utf-8")

        self._patches = [
            patch.object(server, "OUTPUT_FILE", self.output_file),
            patch.object(server, "FRONTEND_DIR", self.frontend_dir),
        ]
        for p in self._patches:
            p.start()

        self.app = server.create_app()
        self.client = self.app.test_client()

    def tearDown(self):
        for p in self._patches:
            p.stop()
        self._tmp.cleanup()

    def write_bundle(self, *records: Transaction) -> None:
        self.output_file.write_text(bundle_json(*records), encoding="utf-8")


# ─── GET / ────────────────────────────────────────────────────────────────────


class IndexTests(ServerTestCase):

    def test_serves_index_html(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<html>", response.data)


# ─── GET /api/dashboard ───────────────────────────────────────────────────────


class DashboardTests(ServerTestCase):

    def test_returns_404_when_data_missing(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 404)
        self.assertIn("error", response.get_json())

    def test_returns_200_with_bundle_when_data_exists(self):
        self.write_bundle()
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"records": []})

    def test_returns_records(self):
        self.write_bundle(make_transaction())
        response = self.client.get("/api/dashboard")
        data = response.get_json()
        self.assertEqual(len(data["records"]), 1)
        self.assertEqual(data["records"][0]["vendor"], "Acme Corp")

    def test_returns_json_content_type(self):
        self.write_bundle()
        response = self.client.get("/api/dashboard")
        self.assertIn("application/json", response.content_type)


# ─── POST /api/sync ───────────────────────────────────────────────────────────


class SyncTests(ServerTestCase):

    def _fake_write(self, data, output_file, **_):
        output_file.write_text(bundle_json(), encoding="utf-8")

    def test_returns_204(self):
        with patch.object(server, "build_app_data", return_value=make_bundle()), \
             patch.object(server, "write_app_data", side_effect=self._fake_write):
            response = self.client.post("/api/sync")
        self.assertEqual(response.status_code, 204)

    def test_sync_then_dashboard_returns_data(self):
        with patch.object(server, "build_app_data", return_value=make_bundle()), \
             patch.object(server, "write_app_data", side_effect=self._fake_write):
            self.client.post("/api/sync")
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), {"records": []})

    def test_sync_calls_build_app_data(self):
        with patch.object(server, "build_app_data", return_value=make_bundle()) as mock_build, \
             patch.object(server, "write_app_data", side_effect=self._fake_write):
            self.client.post("/api/sync")
        mock_build.assert_called_once()

    def test_sync_calls_write_app_data(self):
        bundle = make_bundle()
        with patch.object(server, "build_app_data", return_value=bundle), \
             patch.object(server, "write_app_data", side_effect=self._fake_write) as mock_write:
            self.client.post("/api/sync")
        mock_write.assert_called_once()


# ─── PATCH /api/transaction/warning ──────────────────────────────────────────


class PatchWarningTests(ServerTestCase):

    VALID_PAYLOAD = {
        "match": {
            "source_file": "statement.pdf",
            "date": "2025-01-15",
            "amount": 100.0,
        },
        "remove_warning": "negative_amount",
    }

    def _patch(self, payload, patch_return=True):
        with patch.object(server, "patch_app_data", return_value=patch_return) as mock:
            response = self.client.patch(
                "/api/transaction/warning",
                json=payload,
            )
        return response, mock

    # Happy path

    def test_returns_204_on_success(self):
        response, _ = self._patch(self.VALID_PAYLOAD)
        self.assertEqual(response.status_code, 204)

    def test_calls_patch_app_data_with_correct_tuple(self):
        _, mock = self._patch(self.VALID_PAYLOAD)
        args = mock.call_args.args
        self.assertEqual(args[0][0], "statement.pdf")
        self.assertEqual(args[0][1], datetime.date(2025, 1, 15))
        self.assertEqual(args[0][2], 100.0)

    def test_calls_patch_app_data_with_correct_warning(self):
        _, mock = self._patch(self.VALID_PAYLOAD)
        self.assertEqual(mock.call_args.args[1], "negative_amount")

    def test_date_is_parsed_to_date_object(self):
        """Ensures fromisoformat converts the string before it reaches patch_app_data."""
        _, mock = self._patch(self.VALID_PAYLOAD)
        passed_date = mock.call_args.args[0][1]
        self.assertIsInstance(passed_date, datetime.date)

    # Failure responses

    def test_returns_400_when_patch_app_data_returns_false(self):
        response, _ = self._patch(self.VALID_PAYLOAD, patch_return=False)
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.get_json())

    def test_returns_400_when_body_is_missing(self):
        response = self.client.patch(
            "/api/transaction/warning",
            data="not json",
            content_type="text/plain",
        )
        self.assertEqual(response.status_code, 400)

    def test_returns_400_when_body_is_empty(self):
        response = self.client.patch(
            "/api/transaction/warning",
            json=None,
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 400)

    # Field variations

    def test_missing_date_field_causes_error(self):
        payload = {
            "match": {"source_file": "statement.pdf", "amount": 100.0},
            "remove_warning": "negative_amount",
        }
        # date=None passed to fromisoformat raises TypeError or AttributeError
        response = self.client.patch("/api/transaction/warning", json=payload)
        self.assertIn(response.status_code, (400, 500))

    def test_malformed_date_causes_error(self):
        payload = {
            "match": {
                "source_file": "statement.pdf",
                "date": "not-a-date",
                "amount": 100.0,
            },
            "remove_warning": "negative_amount",
        }
        response = self.client.patch("/api/transaction/warning", json=payload)
        self.assertIn(response.status_code, (400, 500))


if __name__ == "__main__":
    unittest.main()