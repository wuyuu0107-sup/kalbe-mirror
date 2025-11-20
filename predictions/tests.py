import csv
import io
import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pandas as pd
from django.core.cache import cache
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from .serializers import PredictRequestSerializer
from .services import SubprocessModelRunner
from . import run_model as rm


# =====================================================================
#  Dummy pipeline untuk test run_model.py
# =====================================================================

class DummyPipe:
    """
    Fake sklearn Pipeline-like object:
    - punya .predict()
    - punya .feature_names_in_
    - punya .named_steps["model"].classes_
    """
    def __init__(self):
        self.feature_names_in_ = list(rm.COLMAP.values())
        self._classes = [0, 1, 2]
        self.named_steps = {"model": self}

    def predict(self, X):
        # Selalu balikin kelas 0 agar mapping -> "low"
        return [0] * len(X)

    @property
    def classes_(self):
        return self._classes


# =====================================================================
#  Serializer tests
# =====================================================================

class PredictRequestSerializerTests(SimpleTestCase):
    def test_accepts_valid_csv_under_size_limit(self):
        content = b"SIN,Subject Initials\n14515,YSSA\n"
        uploaded = SimpleUploadedFile("patients.csv", content)

        serializer = PredictRequestSerializer(data={"file": uploaded})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertIn("file", serializer.validated_data)

    def test_rejects_non_csv_extension(self):
        content = b"not,really,csv\n"
        uploaded = SimpleUploadedFile("not_csv.txt", content)

        serializer = PredictRequestSerializer(data={"file": uploaded})
        self.assertFalse(serializer.is_valid())
        self.assertIn("file", serializer.errors)
        self.assertIn(".csv", str(serializer.errors["file"]))

    def test_rejects_too_large_csv(self):
        # 21MB > 20MB
        big_content = b"0" * (21 * 1024 * 1024)
        uploaded = SimpleUploadedFile("big.csv", big_content)

        serializer = PredictRequestSerializer(data={"file": uploaded})
        self.assertFalse(serializer.is_valid())
        self.assertIn("file", serializer.errors)
        self.assertIn("20MB", str(serializer.errors["file"]))


# =====================================================================
#  Service layer tests (SubprocessModelRunner)
# =====================================================================

class SubprocessModelRunnerTests(SimpleTestCase):
    def _make_dummy_runner_dir(self) -> Path:
        """
        Bikin folder sementara berisi:
        - run_model.py dummy
        - model_logreg.joblib dummy
        """
        tmpdir = Path(tempfile.mkdtemp(prefix="runner_src_"))
        runner_path = tmpdir / "run_model.py"
        runner_path.write_text("print('dummy runner')")

        model_path = tmpdir / "model_logreg.joblib"
        model_path.write_bytes(b"dummy-model")

        return runner_path

    @patch("predictions.services.subprocess.run")
    @patch.object(SubprocessModelRunner, "_read_output_csv")
    def test_run_happy_path_calls_subprocess_and_reads_output(
        self, mock_read_output, mock_subprocess_run
    ):
        mock_subprocess_run.return_value.returncode = 0
        mock_subprocess_run.return_value.stdout = "ok"
        mock_subprocess_run.return_value.stderr = ""
        mock_read_output.return_value = [{"a": "b"}]

        runner_path = self._make_dummy_runner_dir()
        runner = SubprocessModelRunner(ml_runner_py=str(runner_path))

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"SIN,Subject Initials\n14515,YSSA\n")
            input_path = f.name

        try:
            result = runner.run(input_csv_path=input_path)
        finally:
            if os.path.exists(input_path):
                os.remove(input_path)

        self.assertEqual(result, [{"a": "b"}])
        self.assertTrue(mock_subprocess_run.called)
        mock_read_output.assert_called_once()

    def test_run_raises_if_runner_not_found(self):
        runner = SubprocessModelRunner(ml_runner_py="/does/not/exist/run_model.py")

        with self.assertRaises(FileNotFoundError):
            runner.run(input_csv_path="/tmp/fake_input.csv")

    @patch("predictions.services.subprocess.run")
    def test_run_raises_runtimeerror_on_nonzero_exit_code(self, mock_subprocess_run):
        mock_subprocess_run.return_value.returncode = 1
        mock_subprocess_run.return_value.stdout = ""
        mock_subprocess_run.return_value.stderr = "boom"

        runner_path = self._make_dummy_runner_dir()
        runner = SubprocessModelRunner(ml_runner_py=str(runner_path))

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as f:
            f.write(b"SIN,Subject Initials\n14515,YSSA\n")
            input_path = f.name

        try:
            with self.assertRaises(RuntimeError) as cm:
                runner.run(input_csv_path=input_path)
        finally:
            if os.path.exists(input_path):
                os.remove(input_path)

        self.assertIn("ML runner failed", str(cm.exception))
        self.assertIn("boom", str(cm.exception))

    def test_read_output_csv_parses_rows(self):
        runner = SubprocessModelRunner(ml_runner_py="/tmp/dummy.py")

        with tempfile.NamedTemporaryFile("w+", suffix=".csv", delete=False) as f:
            writer = csv.writer(f)
            writer.writerow(["SIN", "Subject Initials", "prediction"])
            writer.writerow(["14515", "YSSA", "low"])
            writer.writerow(["9723", "RDHO", "high"])
            csv_path = Path(f.name)

        try:
            rows = runner._read_output_csv(csv_path)
        finally:
            if os.path.exists(csv_path):
                os.remove(csv_path)

        self.assertEqual(len(rows), 2)
        self.assertEqual(
            rows[0],
            {"SIN": "14515", "Subject Initials": "YSSA", "prediction": "low"},
        )
        self.assertEqual(
            rows[1],
            {"SIN": "9723", "Subject Initials": "RDHO", "prediction": "high"},
        )


# =====================================================================
#  API / view tests
# =====================================================================

class PredictCsvApiTests(TestCase):
    """
    Tes endpoint /api/predict-csv/ (name: predictions:predict_csv)
    """

    def setUp(self):
        self.url = reverse("predictions:predict_csv")
        cache.clear()

    def _dummy_csv_bytes(self):
        return b"SIN,Subject Initials\n14515,YSSA\n9723,RDHO\n"

    @patch("predictions.views.PredictionResult.objects.bulk_create")
    @patch("predictions.views.SubprocessModelRunner")
    def test_upload_csv_saves_predictions_to_db(self, MockRunner, mock_bulk_create):
        # Arrange: mock model runner to return two rows
        rows = [
            {"SIN": "14515", "Subject Initials": "YSSA", "prediction": "low"},
            {"SIN": "9723", "Subject Initials": "RDHO", "prediction": "high"},
        ]
        mock_runner = MockRunner.return_value
        mock_runner.run.return_value = rows

        file_obj = io.BytesIO(self._dummy_csv_bytes())
        file_obj.name = "patients.csv"

        # Act
        resp = self.client.post(
            self.url,
            data={"file": file_obj},
            format="multipart",
        )

        # Assert: HTTP response still OK and rows returned
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content)
        self.assertIn("rows", body)
        self.assertEqual(len(body["rows"]), 2)

        # Assert: bulk_create called once with correct number of objects
        mock_bulk_create.assert_called_once()
        created_objs = mock_bulk_create.call_args[0][0]
        self.assertEqual(len(created_objs), 2)

        # Check that first object has the correct mapped fields
        first = created_objs[0]
        self.assertEqual(first.sin, "14515")
        self.assertEqual(first.subject_initials, "YSSA")
        self.assertEqual(first.prediction, "low")
        self.assertEqual(first.input_data, "patients.csv")
        self.assertEqual(first.meta, rows[0])

    def test_reject_non_csv_in_view(self):
        bad_file = io.BytesIO(b"not a csv at all")
        bad_file.name = "not_csv.txt"

        resp = self.client.post(
            self.url,
            data={"file": bad_file},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.content)
        self.assertIn("file", body)

    def test_missing_file_returns_400(self):
        resp = self.client.post(
            self.url,
            data={},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 400)
        body = json.loads(resp.content)
        self.assertIn("file", body)

    @patch("predictions.views.SubprocessModelRunner")
    def test_runner_failure_returns_500(self, MockRunner):
        mock_runner = MockRunner.return_value
        mock_runner.run.side_effect = Exception("crash in model")

        file_obj = io.BytesIO(self._dummy_csv_bytes())
        file_obj.name = "patients.csv"

        resp = self.client.post(
            self.url,
            data={"file": file_obj},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 500)
        body = json.loads(resp.content)
        self.assertIn("detail", body)
        self.assertIn("crash in model", body["detail"])

    @patch("predictions.views.PredictionResult.objects.bulk_create")
    @patch("predictions.views.SubprocessModelRunner")
    def test_no_rows_means_no_bulk_create(self, MockRunner, mock_bulk_create):
        mock_runner = MockRunner.return_value
        mock_runner.run.return_value = []  # no predictions

        file_obj = io.BytesIO(self._dummy_csv_bytes())
        file_obj.name = "patients.csv"

        resp = self.client.post(
            self.url,
            data={"file": file_obj},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content)
        self.assertEqual(body["rows"], [])

        mock_bulk_create.assert_not_called()

    @patch("predictions.views.PredictionResult.objects.bulk_create")
    @patch("predictions.views.SubprocessModelRunner")
    def test_runner_failure_does_not_save_anything(self, MockRunner, mock_bulk_create):
        mock_runner = MockRunner.return_value
        mock_runner.run.side_effect = Exception("crash in model")

        file_obj = io.BytesIO(self._dummy_csv_bytes())
        file_obj.name = "patients.csv"

        resp = self.client.post(
            self.url,
            data={"file": file_obj},
            format="multipart",
        )

        self.assertEqual(resp.status_code, 500)
        body = json.loads(resp.content)
        self.assertIn("detail", body)
        self.assertIn("crash in model", body["detail"])

        # should never attempt to write to DB on failure
        mock_bulk_create.assert_not_called()

    @patch("predictions.views.PredictionResult.objects.bulk_create")
    @patch("predictions.views.SubprocessModelRunner")
    def test_missing_tmp_file_is_ignored(self, MockRunner, mock_bulk_create):
        # Arrange: model runner returns a single row
        rows = [
            {"SIN": "14515", "Subject Initials": "YSSA", "prediction": "low"},
        ]
        mock_runner = MockRunner.return_value
        mock_runner.run.return_value = rows

        file_obj = io.BytesIO(b"SIN,Subject Initials\n14515,YSSA\n")
        file_obj.name = "patients.csv"

        # Patch os.remove so it raises FileNotFoundError and hits the except branch
        with patch("os.remove", side_effect=FileNotFoundError) as mock_os_remove:
            # Act
            resp = self.client.post(
                self.url,
                data={"file": file_obj},
                format="multipart",
            )

        # Assert: request still succeeds (FileNotFoundError is swallowed)
        self.assertEqual(resp.status_code, 200)
        body = json.loads(resp.content)
        self.assertIn("rows", body)
        self.assertEqual(len(body["rows"]), 1)

        # os.remove was called once, but its FileNotFoundError didn't bubble up
        mock_os_remove.assert_called_once()

        # bulk_create still called for the row
        mock_bulk_create.assert_called_once()
        created_objs = mock_bulk_create.call_args[0][0]
        self.assertEqual(len(created_objs), 1)
        self.assertEqual(created_objs[0].sin, "14515")
    @patch("predictions.views.SubprocessModelRunner")
    def test_download_endpoint_serves_cached_csv(self, MockRunner):
        mock_runner = MockRunner.return_value
        mock_runner.run.return_value = [
            {"SIN": "14515", "Subject Initials": "YSSA", "prediction": "low"}
        ]

        file_obj = io.BytesIO(self._dummy_csv_bytes())
        file_obj.name = "patients.csv"

        resp = self.client.post(
            self.url,
            data={"file": file_obj},
            format="multipart",
        )
        self.assertEqual(resp.status_code, 200)
        payload = json.loads(resp.content)
        download_id = payload.get("download_id")
        self.assertTrue(download_id)

        download_url = reverse("predictions:predict_csv_download", args=[download_id])
        download_resp = self.client.get(download_url)
        self.assertEqual(download_resp.status_code, 200)
        self.assertEqual(download_resp["Content-Type"], "text/csv")
        self.assertIn("attachment", download_resp["Content-Disposition"])
        body = download_resp.content.decode()
        self.assertIn("Subject Initials", body)
        self.assertIn("YSSA", body)

    def test_download_endpoint_404_when_missing(self):
        download_url = reverse("predictions:predict_csv_download", args=["missing"])
        resp = self.client.get(download_url)
        self.assertEqual(resp.status_code, 404)


# =====================================================================
#  run_model.py helper tests
# =====================================================================

class RunModelHelperTests(SimpleTestCase):
    def test_coalesce_duplicate_targets_prefers_first_non_null(self):
        df = pd.DataFrame(
            [[1, None], [None, 2]],
            columns=["age_recruitment", "age_recruitment"],
        )
        out = rm.coalesce_duplicate_targets(df)

        self.assertEqual(list(out.columns), ["age_recruitment"])
        self.assertEqual(out["age_recruitment"].tolist(), [1, 2])

    def test_build_filtered_frame_renames_and_orders(self):
        df_raw = pd.DataFrame(
            {
                "Gender": ["M", "F"],
                "Age": [30, 40],
                "Height": [170, 160],
            }
        )

        out = rm.build_filtered_frame(df_raw)
        target_cols = list(dict.fromkeys(rm.COLMAP.values()))

        self.assertEqual(list(out.columns), target_cols)
        self.assertEqual(out.loc[0, "gender"], "M")
        self.assertEqual(out.loc[1, "age_recruitment"], 40)

    @patch("predictions.run_model.joblib.load")
    def test_load_pipeline_from_dict_bundle(self, mock_load):
        mock_load.return_value = {"pipeline": "PIPE"}
        result = rm.load_pipeline(Path("dummy.joblib"))
        self.assertEqual(result, "PIPE")

    @patch("predictions.run_model.joblib.load")
    def test_load_pipeline_plain_object(self, mock_load):
        mock_load.return_value = "PLAIN"
        result = rm.load_pipeline(Path("dummy.joblib"))
        self.assertEqual(result, "PLAIN")


# =====================================================================
#  run_model.py main() tests (CLI behaviour)
# =====================================================================

class RunModelMainTests(SimpleTestCase):
    @patch("predictions.run_model.joblib.load")
    def test_main_success_writes_predictions_with_aux_cols(self, mock_load):
        mock_load.return_value = DummyPipe()

        with tempfile.TemporaryDirectory() as tmpdir_str:
            tmpdir = Path(tmpdir_str)

            input_path = tmpdir / "input.csv"
            output_path = tmpdir / "output.csv"
            model_path = tmpdir / "model_logreg.joblib"

            # bikin input CSV lengkap dengan AUX_COLS
            df_raw = pd.DataFrame(
                {
                    "Gender": ["M", "F"],
                    "Age": [30, 40],
                    "Height": [170, 160],
                    "Weight": [70, 60],
                    "BMI": [24.2, 23.4],
                    "Systolic": [120, 110],
                    "Diastolic": [80, 70],
                    "Smoker": [0, 1],
                    "Hemoglobin": [13.5, 14.0],
                    "Random Blood Glucose": [100, 110],
                    "SGOT": [20, 22],
                    "SGPT": [21, 25],
                    "Alkaline Phosphatase": [60, 62],
                    "SIN": ["14515", "9723"],
                    "Subject Initials": ["YSSA", "RDHO"],
                }
            )
            df_raw.to_csv(input_path, index=False)

            # file model kosong, isinya diabaikan karena joblib.load di-patch
            model_path.write_bytes(b"dummy")

            argv = [
                "run_model.py",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--model",
                str(model_path),
            ]

            with patch.object(sys, "argv", argv):
                rm.main()

            self.assertTrue(output_path.exists())

            out_df = pd.read_csv(output_path)
            self.assertEqual(list(out_df.columns), ["SIN", "Subject Initials", "prediction"])
            self.assertEqual(
                out_df["SIN"].astype(str).tolist(),
                ["14515", "9723"],
            )
            # DummyPipe -> semua pred 0 -> label "low"
            self.assertEqual(out_df["prediction"].tolist(), ["low", "low"])

    def test_main_errors_when_input_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir_str:
            tmpdir = Path(tmpdir_str)

            input_path = tmpdir / "missing.csv"     # tidak dibuat
            output_path = tmpdir / "output.csv"
            model_path = tmpdir / "model_logreg.joblib"
            model_path.write_bytes(b"dummy")

            argv = [
                "run_model.py",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--model",
                str(model_path),
            ]

            stderr = io.StringIO()
            with patch.object(sys, "argv", argv), patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit) as cm:
                    rm.main()

            self.assertEqual(cm.exception.code, 1)
            self.assertIn("Input file not found", stderr.getvalue())

    def test_main_errors_when_model_missing(self):
        with tempfile.TemporaryDirectory() as tmpdir_str:
            tmpdir = Path(tmpdir_str)

            input_path = tmpdir / "input.csv"
            output_path = tmpdir / "output.csv"
            model_path = tmpdir / "model_logreg.joblib"   # tidak dibuat

            # input CSV minimal
            pd.DataFrame({"Gender": ["M"], "Age": [30]}).to_csv(input_path, index=False)

            argv = [
                "run_model.py",
                "--input",
                str(input_path),
                "--output",
                str(output_path),
                "--model",
                str(model_path),
            ]

            stderr = io.StringIO()
            with patch.object(sys, "argv", argv), patch("sys.stderr", stderr):
                with self.assertRaises(SystemExit) as cm:
                    rm.main()

            self.assertEqual(cm.exception.code, 1)
            self.assertIn("Model file not found", stderr.getvalue())

from django.test import TestCase
from predictions.models import PredictionResult

class PredictionResultStrTests(TestCase):

    def test_str_full_fields(self):
        obj = PredictionResult(
            sin="12345",
            subject_initials="AB",
            prediction="high",
        )
        self.assertEqual(str(obj), "12345 | AB → high")

    def test_str_missing_sin(self):
        obj = PredictionResult(
            sin=None,
            subject_initials="CD",
            prediction="low",
        )
        self.assertEqual(str(obj), "N/A | CD → low")

    def test_str_missing_subject_initials(self):
        obj = PredictionResult(
            sin="99999",
            subject_initials=None,
            prediction="medium",
        )
        self.assertEqual(str(obj), "99999 | N/A → medium")

    def test_str_missing_both_fields(self):
        obj = PredictionResult(
            sin=None,
            subject_initials=None,
            prediction="unknown",
        )
        self.assertEqual(str(obj), "N/A | N/A → unknown")
