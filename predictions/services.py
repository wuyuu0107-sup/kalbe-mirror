import csv
import glob
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Protocol
import sys
from django.conf import settings

# Default to predictions/run_model.py if not set in settings
_DEFAULT_RUNNER = getattr(settings, "ML_RUNNER_PY", None) or str(
    Path(__file__).with_name("run_model.py")
)

class IModelRunner(Protocol):
    def run(self, input_csv_path: str) -> List[Dict]:
        ...

@dataclass
class SubprocessModelRunner:
    """
    Runs the external ML pipeline unchanged.

    To make relative paths inside run_model.py work (e.g. 'model_logreg.joblib'),
    we copy run_model.py and any *.joblib next to it into a temporary folder and
    run the script with cwd=tempdir. We only pass temp file paths around; no persistence.
    """
    ml_runner_py: str = _DEFAULT_RUNNER

    def run(self, input_csv_path: str) -> List[Dict]:
        runner_path = Path(self.ml_runner_py).resolve()
        if not runner_path.is_file():
            raise FileNotFoundError(f"ML runner not found at {runner_path}")

        runner_src_dir = runner_path.parent
        tempdir = Path(tempfile.mkdtemp(prefix="mlrun_"))

        try:
            # Copy run_model.py
            runner_tmp = tempdir / runner_path.name
            shutil.copy2(runner_path, runner_tmp)

            # Copy all *.joblib model files beside run_model.py
            for joblib_file in glob.glob(str(runner_src_dir / "*.joblib")):
                shutil.copy2(joblib_file, tempdir / Path(joblib_file).name)

            # Output path inside tempdir
            output_csv_path = tempdir / "prediction_result.csv"

            cmd = [
                sys.executable,
                str(runner_tmp),
                "--input",
                input_csv_path,
                "--output",
                str(output_csv_path),
            ]

            completed = subprocess.run(
                cmd,
                cwd=str(tempdir),       # crucial so relative paths in run_model.py resolve
                capture_output=True,
                text=True,
            )

            if completed.returncode != 0:
                raise RuntimeError(f"ML runner failed: {completed.stderr or completed.stdout}")

            return self._read_output_csv(output_csv_path)

        finally:
            # Clean up the temp workspace
            try:
                shutil.rmtree(tempdir, ignore_errors=True)
            except Exception:
                pass

    def _read_output_csv(self, path: Path) -> List[Dict]:
        with open(path, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            return [dict(row) for row in reader]
