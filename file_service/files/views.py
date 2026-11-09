import time
import os
import logging
import re
from django.conf import settings
from django.db import transaction
from django.core.files.base import ContentFile
from django.shortcuts import get_object_or_404
from django.http import HttpResponseRedirect
from django.views.decorators.clickjacking import xframe_options_exempt
import requests
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, MultiPartParser, JSONParser
from rest_framework.exceptions import ValidationError

from file_service.files import models, serializers
from rest_framework.response import Response
from django.template import Context
from django.template import Template as DjangoTemplate

from rest_framework.pagination import PageNumberPagination

logger = logging.getLogger('file_service')


def _prepare_spreadsheet_for_preview(file_bytes, ext):
    """
    LibreOffice Calc headless export has a documented regression (tdf#169919):
    native cell hyperlinks (<hyperlink ref="XX">) in .xlsx are rendered as plain text
    without interactive PDF link annotations (/Subtype /Link).
    Converting them to HYPERLINK() formulas in memory preserves working clickable links.
    """
    if ext != '.xlsx':
        return file_bytes
    try:
        import io, zipfile, re, xml.etree.ElementTree as ET, xml.sax.saxutils as saxutils
        in_buf = io.BytesIO(file_bytes)
        out_buf = io.BytesIO()

        with zipfile.ZipFile(in_buf, 'r') as zin, zipfile.ZipFile(out_buf, 'w') as zout:
            rels_map = {}
            for item in zin.infolist():
                if item.filename.startswith('xl/worksheets/_rels/') and item.filename.endswith('.rels'):
                    sheet_name = item.filename.replace('xl/worksheets/_rels/', 'xl/worksheets/').replace('.rels', '')
                    tree = ET.fromstring(zin.read(item.filename))
                    rels = {}
                    for rel in tree:
                        if 'hyperlink' in rel.attrib.get('Type', '').lower() and 'Target' in rel.attrib:
                            rels[rel.attrib.get('Id')] = rel.attrib.get('Target')
                    if rels:
                        rels_map[sheet_name] = rels

            if not rels_map:
                return file_bytes

            strings = []
            if 'xl/sharedStrings.xml' in zin.namelist():
                sst_tree = ET.fromstring(zin.read('xl/sharedStrings.xml'))
                ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                for si in sst_tree.findall('main:si', ns):
                    t_elem = si.find('main:t', ns)
                    strings.append(t_elem.text if t_elem is not None else '')

            for item in zin.infolist():
                content = zin.read(item.filename)
                if item.filename in rels_map:
                    rels = rels_map[item.filename]
                    xml_text = content.decode('utf-8')
                    tree = ET.fromstring(xml_text)
                    ns = {'main': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                    hls = tree.findall('.//main:hyperlink', ns)

                    cell_fixes = {}
                    for hl in hls:
                        ref = hl.attrib.get('ref')
                        r_id = hl.attrib.get('{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id')
                        target = rels.get(r_id)
                        if ref and target:
                            c_elem = tree.find(f'.//main:c[@r="{ref}"]', ns)
                            display = target
                            if c_elem is not None:
                                t_attr = c_elem.attrib.get('t')
                                v_elem = c_elem.find('main:v', ns)
                                if v_elem is not None and v_elem.text:
                                    if t_attr == 's' and v_elem.text.isdigit():
                                        idx = int(v_elem.text)
                                        if idx < len(strings):
                                            display = strings[idx] or target
                                    else:
                                        display = v_elem.text
                            cell_fixes[ref] = (target, display)

                    for ref, (target, display) in cell_fixes.items():
                        f_target = target.replace('"', '""')
                        f_display = display.replace('"', '""')
                        formula_text = f'HYPERLINK("{f_target}", "{f_display}")'
                        xml_formula = saxutils.escape(formula_text)
                        xml_display = saxutils.escape(display)

                        pattern = rf'<c\s+r="{ref}"[^>]*>.*?</c>'
                        repl = f'<c r="{ref}" t="str"><f>{xml_formula}</f><v>{xml_display}</v></c>'
                        xml_text = re.sub(pattern, repl, xml_text)

                    content = xml_text.encode('utf-8')
                zout.writestr(item, content)

        return out_buf.getvalue()
    except Exception as e:
        logger.warning("Failed to preprocess xlsx hyperlinks: %s", e)
        return file_bytes


class StandardResultsSetPagination(PageNumberPagination):
    page_size = 10
    page_size_query_param = 'page_size'
    max_page_size = 100


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

    pagination_class = StandardResultsSetPagination

    def dispatch(self, request, *args, **kwargs):
        if 'rql' in request.GET:
            mutable_get = request.GET.copy()
            mutable_get['rql'] = re.sub(r'(%5B|%5D|%22|\[|\]|")', '', mutable_get['rql'])
            request.GET = mutable_get
        return super().dispatch(request, *args, **kwargs)

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

    @action(detail=True, methods=['GET'])
    @xframe_options_exempt
    def preview(self, request, pk=None):
        file_obj = get_object_or_404(models.File, pk=pk)

        # 1. Если это PDF или изображение — отдаем оригинальную ссылку сразу
        if file_obj.mimetype == 'application/pdf' or (file_obj.type and file_obj.type.id in ('PDF', 'IMAGE')):
            return HttpResponseRedirect(file_obj.file_url)

        # 2. Проверяем кэш готовых превью
        preview_dir = os.path.join(settings.MEDIA_ROOT, 'previews')
        os.makedirs(preview_dir, exist_ok=True)
        preview_filename = f"{file_obj.id}.pdf"
        preview_path = os.path.join(preview_dir, preview_filename)
        preview_url = f"{settings.FILES_BASE_URL}previews/{preview_filename}"

        if not os.path.exists(preview_path):
            file_bytes = None
            try:
                if hasattr(file_obj.file, 'path') and os.path.exists(file_obj.file.path):
                    with open(file_obj.file.path, 'rb') as f:
                        file_bytes = f.read()
                elif hasattr(file_obj.file, 'storage') and file_obj.file.storage.exists(file_obj.file.name):
                    with file_obj.file.open('rb') as f:
                        file_bytes = f.read()
                else:
                    try:
                        with file_obj.file.open('rb') as f:
                            file_bytes = f.read()
                    except (FileNotFoundError, OSError, ValueError):
                        file_bytes = None
            except Exception as e:
                logger.warning("Could not read original file %s: %s", pk, e)
                file_bytes = None

            if not file_bytes:
                return Response({
                    "status": "ERROR",
                    "message": "Original file not found on storage"
                }, status=status.HTTP_404_NOT_FOUND)

            try:
                upload_name = file_obj.origin_filename or file_obj.filename or f"doc_{file_obj.id}.docx"
                post_data = {}
                ext = os.path.splitext(upload_name)[1].lower()
                if ext in ('.xlsx', '.xls', '.ods', '.csv', '.tsv'):
                    post_data['singlePageSheets'] = 'true'
                    file_bytes = _prepare_spreadsheet_for_preview(file_bytes, ext)

                resp = requests.post(
                    "http://gotenberg:3000/forms/libreoffice/convert",
                    files={"files": (upload_name, file_bytes)},
                    data=post_data,
                    timeout=60
                )
                if resp.status_code == 200:
                    tmp_preview_path = f"{preview_path}.tmp.{os.getpid()}"
                    with open(tmp_preview_path, 'wb') as out_f:
                        out_f.write(resp.content)
                    os.replace(tmp_preview_path, preview_path)
                else:
                    logger.error("Gotenberg conversion failed for %s: %s", pk, resp.text)
                    return Response({
                        "status": "ERROR",
                        "message": f"Gotenberg conversion failed: {resp.text}"
                    }, status=status.HTTP_502_BAD_GATEWAY)
            except Exception as e:
                logger.exception("Preview generation failed for file %s", pk)
                return Response({
                    "status": "ERROR",
                    "message": f"Preview generation error: {str(e)}"
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        response = HttpResponseRedirect(preview_url)
        response['X-Frame-Options'] = 'SAMEORIGIN'
        return response

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
