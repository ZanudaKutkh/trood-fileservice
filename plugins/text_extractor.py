import io
import re

import textract
from django.db.models import signals

from file_service.files.models import File, FileTextContent
from trood.contrib.django.apps.plugins.core import TroodBasePlugin
from trood.contrib.django.apps.plugins.models import TroodPluginModel


class TextExtractorPlugin(TroodBasePlugin):
    id = 'extract_text'
    name = 'Text Extrator Plugin'
    version = 'v0.0.1'

    default_config = {
        'async': False,
        'extractable_mimetypes': [
            "application/pdf", "text/plain", "text/rtf", "application/rtf",
            "application/x-rtf", "text/csv", "application/msword",
            "text/richtext",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "application/vnd.openxmlformats-officedocument.wordprocessingml.template",
            "application/vnd.ms-word.document.macroEnabled.12",
            "application/vnd.ms-word.template.macroEnabled.12", "application/vnd.ms-excel",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            "application/vnd.openxmlformats-officedocument.spreadsheetml.template",
            "application/vnd.ms-excel.sheet.macroEnabled.12",
            "application/vnd.ms-excel.template.macroEnabled.12",
            "application/vnd.ms-excel.addin.macroEnabled.12",
            "application/vnd.ms-excel.sheet.binary.macroEnabled.12",
            "application/vnd.ms-powerpoint",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
            "application/vnd.openxmlformats-officedocument.presentationml.template",
            "application/vnd.openxmlformats-officedocument.presentationml.slideshow",
            "application/vnd.ms-powerpoint.addin.macroEnabled.12",
            "application/vnd.ms-powerpoint.presentation.macroEnabled.12",
            "application/vnd.ms-powerpoint.template.macroEnabled.12",
            "application/vnd.ms-powerpoint.slideshow.macroEnabled.12",
            "application/vnd.oasis.opendocument.spreadsheet",
            "application/vnd.oasis.opendocument.text",
            "application/vnd.oasis.opendocument.presentation"
        ]
    }

    @classmethod
    def register(cls):
        signals.post_save.connect(cls.extract, File)

    @classmethod
    def extract(cls, sender, **kwargs):
        plugin = TroodPluginModel.objects.filter(id=cls.id).first()
        if plugin and plugin.active:
            file = kwargs.get('instance')
            config = cls.get_config()

            extractable_mimetype = file.mimetype in config['extractable_mimetypes']

            not_extracted = True if not file.metadata or file.metadata.get(
                'text_extracted', 'not_extracted') == 'not_extracted' else False

            if extractable_mimetype and not_extracted:
                try:
                    filepath = file.file.path
                    b_text = textract.process(filepath)
                    title = file.origin_filename.split('.')[0]
                    raw_text = b_text.decode("utf-8")
                    text = re.sub(r'\s+', ' ', re.sub(r'<[^<]+>', ' ', raw_text))
                    FileTextContent.objects.create(
                        source=file, content=text, title=title)
                    cls._set_metadata(file, True)
                except:
                    cls._set_metadata(file, False)

    @classmethod
    def _set_metadata(self, file, value):
        if not file.metadata:
            metadata = {'text_extracted': value}
            file.metadata = metadata
            file.save()
        else:
            file.metadata['text_extracted'] = value
            file.save()

