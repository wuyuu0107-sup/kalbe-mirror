from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.parsers import MultiPartParser, FormParser
from rest_framework.response import Response

from .models import CSVFile
from .serializers import CSVFileSerializer
from .permissions import IsResearcherOnly


class CSVFileListCreateView(generics.ListCreateAPIView):
    queryset = CSVFile.objects.all().order_by("-uploaded_at")
    serializer_class = CSVFileSerializer
    parser_classes = [MultiPartParser, FormParser]
    permission_classes = [IsResearcherOnly]

    def create(self, request, *args, **kwargs):
        # require a file under key 'file'
        uploaded_file = request.FILES.get("file")
        if not uploaded_file:
            return Response({"detail": "No file provided under 'file' field."}, status=status.HTTP_400_BAD_REQUEST)
        instance = CSVFile.objects.create(file_path=uploaded_file)
        serializer = self.get_serializer(instance, context={"request": request})
        headers = self.get_success_headers(serializer.data)
        return Response(serializer.data, status=status.HTTP_201_CREATED, headers=headers)

    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True, context={"request": request})
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)


class CSVFileRetrieveDestroyView(generics.RetrieveDestroyAPIView):
    queryset = CSVFile.objects.all()
    serializer_class = CSVFileSerializer
    permission_classes = [IsResearcherOnly]

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx["request"] = self.request
        return ctx


class CSVFileDownloadView(generics.GenericAPIView):
    permission_classes = [IsResearcherOnly]

    def get(self, request, pk):
        obj = get_object_or_404(CSVFile, pk=pk)
        try:
            file = obj.file_path.open("rb")
        except FileNotFoundError:
            raise Http404("File not found")
        response = FileResponse(file, as_attachment=True, filename=obj.filename)
        return response
