import io
import json
import tempfile
import unittest
from unittest.mock import patch

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

# --- Service tests (unit) ---

class SubprocessModelRunnerTests(unittest.TestCase):
    """
    Unit test untuk service layer tanpa menyentuh Django ORM.
    """
    @patch('predictions.services.subprocess.run')
    def test_runs_cli_and_reads_output(self, mock_run):
        # Arrange: subprocess sukses
        mock_run.return_value.returncode = 0

        # Patch reader supaya ga perlu file output beneran
        from predictions.services import SubprocessModelRunner
        with patch.object(SubprocessModelRunner, '_read_output_csv',
                          return_value=[{"a": "b"}]) as mock_read:
            runner = SubprocessModelRunner(ml_runner_py='/abs/fake/run_model.py')

            # bikin file input temp kosong (cukup ada path-nya)
            with tempfile.NamedTemporaryFile(suffix='.csv', delete=True) as f:
                # Act
                result = runner.run(input_csv_path=f.name)

        # Assert
        assert result == [{"a": "b"}]
        assert mock_run.called
        assert mock_read.called


# --- API tests (integration-lite) ---

class PredictCsvApiTests(TestCase):
    """
    Tes endpoint /api/predict-csv/ end-to-end tipis:
    - upload CSV (multipart)
    - mock subprocess + pembacaan output
    - validasi response JSON
    """
    def setUp(self):
        self.url = reverse('predictions:predict_csv')

    def _dummy_csv_bytes(self):
        # CSV minimal yang valid sesuai pipeline (header penting)
        content = "SIN,Subject Initials\n14515,YSSA\n9723,RDHO\n"
        return content.encode('utf-8')

    @override_settings(ML_RUNNER_PY='/abs/fake/path/run_model.py')
    @patch('predictions.services.subprocess.run')
    def test_upload_and_get_json(self, mock_run):
        # Arrange
        mock_run.return_value.returncode = 0

        from predictions.services import SubprocessModelRunner
        # Hindari baca file output beneran
        with patch.object(SubprocessModelRunner, '_read_output_csv', return_value=[
            {"SIN": "14515", "Subject Initials": "YSSA", "prediction": "low"},
            {"SIN": "9723", "Subject Initials": "RDHO", "prediction": "high"},
        ]):
            file = io.BytesIO(self._dummy_csv_bytes())
            file.name = "anything.csv"

            # Act
            resp = self.client.post(self.url, data={'file': file}, format='multipart')

        # Assert
        self.assertEqual(resp.status_code, 200)
        data = json.loads(resp.content)
        self.assertIn('rows', data)
        self.assertEqual(len(data['rows']), 2)
        self.assertEqual(data['rows'][0]['prediction'], 'low')

    def test_reject_non_csv(self):
        bad_file = io.BytesIO(b'not a csv')
        bad_file.name = "not_csv.txt"
        resp = self.client.post(self.url, data={'file': bad_file}, format='multipart')
        self.assertEqual(resp.status_code, 400)

    def test_missing_file(self):
        resp = self.client.post(self.url, data={}, format='multipart')
        self.assertEqual(resp.status_code, 400)
