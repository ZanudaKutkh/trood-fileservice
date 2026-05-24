from file_service.files.models import File, FileTextContent
from trood.contrib.django.apps.plugins.core import TroodBasePlugin

from django.db.models import signals

import pytesseract
from PIL import Image
from pdf2image import convert_from_bytes


class OcrPlugin(TroodBasePlugin):
    id = 'ocr_text_extractor'
    name = 'OCR Text Extractor Plugin'
    version = 'v0.0.1'

    default_config = {
        "config": "preserve_interword_spaces=1",
        "lang": "rus+eng"
    }

    @classmethod
    def register(cls):
        signals.m2m_changed.connect(cls.extract, sender=File.tags.through)

    @classmethod
    def extract(cls, sender, **kwargs):
        """
        A method that monitors the addition of a tag for OCR text extraction.
        If a file was created or updated with tag 'ocr', then we should extract text from it.
        """
        if kwargs.get('action') == 'post_add':
            obj = kwargs.get('instance')
            ocr_tag = obj.tags.all().filter(tag='ocr').first()
            if ocr_tag:
                try:
                    text = cls._convert_to_text(obj)
                    filename = obj.origin_filename.split('.')[0]
                    FileTextContent.objects.update_or_create(source=obj, title=filename, defaults={'content': text})
                    cls._set_metadata(obj, True)
                except:
                    cls._set_metadata(obj, False)

    @classmethod
    def _convert_to_text(cls, obj):
        """
        A method that starts extracting text from a file depending on its extension

        :param obj: Object from which you want to extract the text
        :type obj: file_service.files.models.File
        :return: Extracted text from file
        :rtype: str
        """

        if obj.mimetype == 'application/pdf':
            text = cls.pdf_to_text(file=obj.file.file, lang=cls.default_config.get('lang'), default_config=cls.default_config.get('config'))
        else:
            text = cls.image_to_text(file=obj.file.file, lang=cls.default_config.get('lang'), default_config=cls.default_config.get('config'))
        return text

    @staticmethod
    def image_to_text(file, lang, default_config):
        """
        Extract all text from given image.

        :param file: An image from which you want to extract the text
        :type file: file_service.files.models.File
        :param lang: Language of the text on the image
        :type lang: str
        :param default_config: Tesseract configuration
        :type default_config: str
        :return: Extracted text from image
        :rtype: str
        """
        text = pytesseract.image_to_string(Image.open(file), lang=lang, config=default_config)
        return text

    @staticmethod
    def pdf_to_text(file, lang, default_config):
        """
        Extract all text from given pdf file.

        :param file: A file from which you want to extract the text
        :type file: file_service.files.models.File
        :param lang: Language of the text in the file
        :type lang: str
        :param default_config: Tesseract configuration
        :type default_config: str
        :return: Extracted text from the file
        :rtype: str
        """
        with file.open(mode='rb') as f:
            pages = convert_from_bytes(f.read())
        text = ''
        for page in pages:
            data = str((pytesseract.image_to_string(page, lang=lang, config=default_config)))
            text += data.replace('-\n', '')
        return text

    @classmethod
    def _set_metadata(cls, file, value):
        if not file.metadata:
            metadata = {'text_extracted': value}
            file.metadata = metadata
            file.save()
        else:
            file.metadata['text_extracted'] = value
            file.save()
