from trood.contrib.django.apps.plugins.core import TroodBasePlugin
from weasyprint import HTML
from django.conf import settings
from django.template import Context
from django.template import Template as DjangoTemplate


class PDFFileGenerator(TroodBasePlugin):
    id = 'pdf_file_generator'
    name = 'Generating pdf files'
    version = 'v1.0.0'

    default_config = {
        'extension': '.pdf'
    }

    @classmethod
    def register(cls):
        settings.FILE_GENERATORS["PDF"] = cls

    @classmethod
    def create(cls, template_string, data):
        template = DjangoTemplate(template_string)
        document = HTML(string=template.render(Context(data))).render()
        return document.write_pdf()
