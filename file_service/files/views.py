import time
import os
import logging
from django.conf import settings
from django.db import transaction
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser, JSONParser
from rest_framework.exceptions import ValidationError

from file_service.files import models, serializers
from rest_framework.response import Response
from django.template import Context
from django.template import Template as DjangoTemplate

logger = logging.getLogger('file_service')


def render_file(template, file_format, data, user):
    """
    A helper function to render the file and it will return an error if
    there is a problem in rendering the file.
    """
    generator = settings.FILE_GENERATORS.get(file_format, None)
    if not generator:
        return {"error": "File with format {} cannot be created".format(file_format)}
    else:
        file_data = generator.create(template.body_template, data)

        file_name = DjangoTemplate(
            template.filename_template
        ).render(Context(data)) + generator.get_config('extension')

        file = models.File(
            owner=user.id,
            file=ContentFile(file_data, name=file_name),
            origin_filename=file_name,
            filename=file_name
        )
        file.save()

        return serializers.FileSerializer(file).data


# Class-based for creating the file.


class BaseViewSet(viewsets.ModelViewSet):
    def perform_create(self, serializer):
        serializer.save(owner=self.request.user.id)


class FilesViewSet(BaseViewSet):
    """
    Display the file form and handle the actions on the files.
    """
    parser_classes = (FormParser, MultiPartParser, JSONParser)

    queryset = models.File.objects.all()
    serializer_class = serializers.FileSerializer
    filter_fields = ('deleted', )

    @action(detail=False, methods=['POST'])
    def upload_many(self, request):
        files = request.FILES.getlist('files')

        if not files:
            raise ValidationError("No files provided. Please use the 'files' key.")

        if len(files) > 20:
            raise ValidationError("Too many files. Maximum 20 files per batch allowed.")

        results = []
        logger.info("Batch upload started", extra={"user_id": request.user.id, "files_count": len(files)})

        try:
            with transaction.atomic():
                for f in files:
                    serializer = self.get_serializer(data={'file': f})
                    serializer.is_valid(raise_exception=True)
                    self.perform_create(serializer)
                    results.append(serializer.data)
                    logger.info("File uploaded successfully in batch", extra={"upload_filename": f.name, "upload_size": f.size})
        except Exception as e:
            logger.error("Batch upload failed", extra={"error": str(e)})
            raise e

        return Response(results, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['POST'])
    def from_template(self, request):
        """
        For creating a file from template.
        """
        template = request.data.pop("template", None)

        if template is None:
            return Response(data={"status": "ERROR", "message": "Empty template field"}, status=status.HTTP_400_BAD_REQUEST)
        elif isinstance(template, str):
            template = get_object_or_404(models.FileTemplate.objects.all(), alias=template)
        elif isinstance(template, dict):
            template = models.FileTemplate(**template)

        file_format = request.data.pop("format", None)
        data = request.data.pop("data", None)

        result = render_file(template, file_format, data, request.user)

        return Response(
            data=result, status=status.HTTP_201_CREATED,
            headers={
                "Warning": "Endpoint /api/v1.0/files/from_template is deprecated and will be removed in NOV-23-2019"
            }
        )

    @action(detail=True, methods=['GET'])
    def content(self, request, pk=None):
        content = models.FileTextContent.objects.filter(source_id=pk).first()
        if content:
            serializer = serializers.FileTextContentSerializer(instance=content)
            return Response(serializer.data)
        return Response(
            data={"status": "ERROR", "message": "No content for current file"},
            status=status.HTTP_404_NOT_FOUND
        )


    def perform_destroy(self, instance):
        """
        For deleting the file. It will change the
        deleted satatus of the file to True.
        """
        instance.deleted = True
        instance.save()


class FileExtensionViewSet(BaseViewSet):
    """
    Display the file extention form.
    """
    queryset = models.FileExtension.objects.all()
    serializer_class = serializers.FileExtensionSerializer


class FileTypeViewSet(BaseViewSet):
    """
    Display the file type form.
    """
    queryset = models.FileType.objects.all()
    serializer_class = serializers.FileTypeSerializer


class FileTemplateViewSet(BaseViewSet):
    """
    Display the file template form and handle the actions on the files.
    """
    queryset = models.FileTemplate.objects.all()
    serializer_class = serializers.FileTemplateSerializer

    @action(detail=False, methods=['POST'])
    def preview(self, request):
        """
        It will preview template rendering without save.
        """
        serializer = self.serializer_class(data=request.data)
        if serializer.is_valid(True):
            template = models.FileTemplate(**serializer.validated_data)
            result = render_file(template, request.data.get('format'), template.example_data, request.user)
            if "error" in result:
                return Response(data={"status": "ERROR", "error": result['error']}, status=status.HTTP_400_BAD_REQUEST)
            return Response(data={"status": "OK", "data": result}, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['POST'])
    def render(self, request, pk=None):
        """
        It will render template to file.
        """
        template = get_object_or_404(self.queryset, pk=pk)

        # preview is a boolean flag for previewing template with example data
        if request.data.get("preview") == 'true':
            data = template.example_data
        else:
            data = request.data.pop("data", None)

        result = render_file(template, request.data.get('format'), data, request.user)
        if "error" in result:
            return Response(data={"status": "ERROR", "error": result['error']}, status=status.HTTP_400_BAD_REQUEST)
        return Response(data={"status": "OK", "data": result}, status=status.HTTP_201_CREATED)


class ProbeViewset(viewsets.ViewSet):
    def list(self, request):
        return Response(data={
            "status": self.get_status(),
            "version": self.get_version(),
            "uptime": self.get_uptime()
        })

    def get_status(self):
        return "healthy"

    def get_version(self):
        filepath = os.path.join(settings.BASE_DIR, "VERSION")
        with open(filepath, "r") as version_file:
            version = version_file.readlines()
        return "".join(version).strip()

    def get_uptime(self):
        return int(time.time() - settings.START_TIME)


class FileTag(BaseViewSet):
    """
    Display the file tag form.
    """
    queryset = models.Tag.objects.all()
    serializer_class = serializers.FileTagSerializer
