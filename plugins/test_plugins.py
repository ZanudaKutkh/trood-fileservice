import textract
import re
from plugins.pdf_file_generator import PDFFileGenerator
from plugins.png_file_generator import PNGFileGenerator
from plugins.docx_file_generator import DOCXFileGenerator
import tempfile
import pytest


@pytest.fixture
def template():
    template = """
        <style>
            @page { size: A4; }
            * { }
        </style>
            <div>
                {{text}}
            </div>
        """
    return template


def get_extracted_text(file_path):
    b_text = textract.process(file_path)
    raw_text = b_text.decode("utf-8")
    text = re.sub(r'\s+', ' ', re.sub(r'<[^<]+>', ' ', raw_text)).strip()
    return text


def test_pdf_file_generator(template):
    with tempfile.TemporaryDirectory() as tmpdirname:
        file_path = f'{tmpdirname}/temp_test.pdf'
        with open(file_path, 'wb') as pdf_file:
            file_content = PDFFileGenerator.create(template, {'text': 'test'})
            pdf_file.write(file_content)
        text = get_extracted_text(file_path)
        assert text == 'test'


def test_png_file_generator(template):
    with tempfile.TemporaryDirectory() as tmpdirname:
        file_path = f'{tmpdirname}/temp_test.png'
        with open(file_path, 'wb') as png_file:
            file_content = PNGFileGenerator.create(template, {'text': 'test'})
            png_file.write(file_content)
        text = get_extracted_text(file_path)
        assert text == 'test'


def test_docx_file_generator(template):
    with tempfile.TemporaryDirectory() as tmpdirname:
        file_path = f'{tmpdirname}/temp_test.docx'
        with open(file_path, 'wb') as docx_file:
            file_content = DOCXFileGenerator.create(template, {'text': 'test'})
            docx_file.write(file_content)
        text = get_extracted_text(file_path)
        assert text == 'test'
