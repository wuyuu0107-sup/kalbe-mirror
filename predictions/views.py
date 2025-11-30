import tempfile
from .models import PredictionResult
from django.db import transaction
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .serializers import PredictRequestSerializer
from .services import SubprocessModelRunner, IModelRunner

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
                import os
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
        return Response({"rows": rows}, status=200)