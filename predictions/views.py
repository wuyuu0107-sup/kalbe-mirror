import csv
import io
import os
import tempfile
import uuid

from django.core.cache import cache
from django.http import Http404, HttpResponse
from .models import PredictionResult
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import PredictRequestSerializer
from .services import SubprocessModelRunner, IModelRunner
from django.utils.decorators import method_decorator
from dashboard.tracking import track_feature

@method_decorator(track_feature("prediksi"), name="dispatch")
class PredictCsvView(APIView):
    """
    Controller depends on abstraction (IModelRunner) => DIP
    """
    def __init__(self, model_runner: IModelRunner = None, **kwargs):
        super().__init__(**kwargs)
        self.model_runner = model_runner or SubprocessModelRunner()

    def post(self, request, *args, **kwargs):
        serializer = PredictRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        csv_file = serializer.validated_data['file']

        # Save uploaded CSV to a safe temp file (not persisted)
        with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as tmp_in:
            for chunk in csv_file.chunks():
                tmp_in.write(chunk)
            tmp_in_path = tmp_in.name

        try:
            rows = self.model_runner.run(tmp_in_path)
        except Exception as e:
            return Response({"detail": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        finally:
            # clean input file
            try:
                os.remove(tmp_in_path)
            except FileNotFoundError:
                pass

        with transaction.atomic():
            objs = []
            for row in rows:
                objs.append(
                    PredictionResult(
                        sin=row.get("SIN") or None,
                        subject_initials=row.get("Subject Initials") or None,
                        prediction=row.get("prediction") or "",
                        # optional: store raw row and/or original filename for traceability
                        input_data=csv_file.name,
                        meta=row,
                    )
                )
            if objs:
                PredictionResult.objects.bulk_create(objs)

        # JSON for the frontend table (unchanged)
        download_id, filename = self._cache_download(rows, csv_file.name)

        # JSON for the frontend table + download handle
        return Response(
            {
                "rows": rows,
                "download_id": download_id,
                "download_filename": filename,
            },
            status=200,
        )

    def _cache_download(self, rows, source_name: str):
        if not rows:
            csv_data = "prediction\n"
        else:
            headers = list(rows[0].keys())
            buffer = io.StringIO()
            writer = csv.DictWriter(buffer, fieldnames=headers)
            writer.writeheader()
            for row in rows:
                writer.writerow(row)
            csv_data = buffer.getvalue()

        filename = self._build_filename(source_name)
        download_id = uuid.uuid4().hex
        payload = {"csv": csv_data, "filename": filename}
        cache.set(_make_cache_key(download_id), payload, DOWNLOAD_CACHE_TIMEOUT)
        return download_id, filename

    def _build_filename(self, original_name: str):
        base = (original_name or "predictions").rsplit(".", 1)[0]
        return f"{base}_predictions.csv"


class PredictCsvDownloadView(APIView):
    """
    Streams a cached CSV that was prepared by PredictCsvView.
    """

    def get(self, request, download_id: str, *args, **kwargs):
        payload = cache.get(_make_cache_key(download_id))
        if not payload:
            raise Http404("Download expired or not found.")

        csv_content = payload.get("csv", "")
        filename = payload.get("filename", "predictions.csv")
        response = HttpResponse(csv_content, content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response
