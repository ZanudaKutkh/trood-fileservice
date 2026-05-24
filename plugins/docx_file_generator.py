from trood.contrib.django.apps.plugins.core import TroodBasePlugin
from django.conf import settings
from django.template import Context
from django.template import Template as DjangoTemplate
from file_service.utils.html2docx import HTML2DOCX


class DOCXFileGenerator(TroodBasePlugin):
    id = 'docx_file_generator'
    name = 'Generating docx files'
    version = 'v1.0.0'

    default_config = {
        'extension': '.docx'
    }

    @classmethod
    def register(cls):
        settings.FILE_GENERATORS["DOCX"] = cls

    @classmethod
    def create(cls, template_string, data):
        template = DjangoTemplate(template_string)
        document = HTML2DOCX(template.render(Context(data)))
        return document.write_docx()