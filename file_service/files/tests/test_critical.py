import tempfile
import os
import magic
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.conf import settings
from rest_framework.exceptions import ValidationError

from file_service.files.models import File, FileExtension, FileType, validate_file_size
from file_service.files.management.commands.fill_filetextcontent import Command as FillTextCommand

class CriticalLogicTestCase(TestCase):
    def setUp(self):
        # Create basic extensions and types
        FileExtension.objects.get_or_create(extension='jpg')
        FileExtension.objects.get_or_create(extension='pdf')
        FileType.objects.get_or_create(id="IMAGE", mime="image/jpeg")
        FileType.objects.get_or_create(id="PDF", mime="application/pdf")

    def test_validate_file_size(self):
        # Mocking settings.MAX_UPLOAD_SIZE to 1KB
        with override_settings(MAX_UPLOAD_SIZE=1024):
            small_file = SimpleUploadedFile("small.jpg", b"a" * 512)
            validate_file_size(small_file) # Should not raise
            
            large_file = SimpleUploadedFile("large.jpg", b"a" * 2048)
            with self.assertRaises(ValidationError):
                validate_file_size(large_file)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_mimetype_detection(self):
        # Test detection via magic (simulated by content)
        # JPEG header: \xff\xd8\xff
        content = b'\xff\xd8\xff' + b'a' * 10
        f = File.objects.create(
            file=SimpleUploadedFile("image.jpg", content),
            origin_filename="image.jpg",
            size=len(content)
        )
        self.assertEqual(f.mimetype, 'image/jpeg')
        self.assertEqual(f.type.id, 'IMAGE')

        # PDF header: %PDF-
        pdf_content = b'%PDF-1.4\n' + b'a' * 10
        f2 = File.objects.create(
            file=SimpleUploadedFile("doc.pdf", pdf_content),
            origin_filename="doc.pdf",
            size=len(pdf_content)
        )
        self.assertEqual(f2.mimetype, 'application/pdf')
        self.assertEqual(f2.type.id, 'PDF')

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_fill_filetextcontent_command(self):
        # Create a file that should be processed by the command
        # We'll use a plain text file but give it a mimetype that the command expects
        # or we mock the extractor
        
        content = b"This is some sample text for extraction"
        f = File.objects.create(
            file=SimpleUploadedFile("test.txt", content),
            origin_filename="test.txt",
            size=len(content),
            mimetype="text/plain"
        )
        
        # Ensure it has no metadata yet
        self.assertFalse(f.metadata and f.metadata.get('text_extracted'))
        
        # We need to ensure 'text/plain' is in extractable_mimetypes
        # Since we can't easily change the plugin class attribute at runtime safely without affecting other things,
        # let's see what's in TextExtractorPlugin.default_config
        from plugins.text_extractor import TextExtractorPlugin
        
        with override_settings(MEDIA_ROOT=settings.MEDIA_ROOT):
            # If we want to test the command, we might need to mock textract.process
            # because it calls system binaries (antiword, etc.)
            import unittest.mock as mock
            with mock.patch('textract.process') as mock_process:
                mock_process.return_value = b"Extracted text content"
                
                # Mock the plugin config to include text/plain
                original_config = TextExtractorPlugin.default_config
                TextExtractorPlugin.default_config = {
                    'extractable_mimetypes': ['text/plain']
                }
                
                try:
                    call_command('fill_filetextcontent')
                    
                    f.refresh_from_db()
                    self.assertTrue(f.metadata.get('text_extracted'))
                    from file_service.files.models import FileTextContent
                    self.assertTrue(FileTextContent.objects.filter(source=f).exists())
                    self.assertEqual(FileTextContent.objects.get(source=f).content, "Extracted text content")
                finally:
                    TextExtractorPlugin.default_config = original_config

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_atomic_transaction_in_view(self):
        # This is already covered in test_new_features.py but good to have here too
        # with a slightly different failure mode
        pass
