import base64
import os
import tempfile
from django.test.utils import override_settings
from rest_framework.test import APITestCase, APIClient
from rest_framework.reverse import reverse
from rest_framework import status
from file_service.files.models import FileExtension, FileType, File
from trood.contrib.django.auth.authentication import TroodUser

class MultiUploadTestCase(APITestCase):
    def setUp(self):
        self.client = APIClient()
        trood_user = TroodUser({"id": 1})
        self.client.force_authenticate(user=trood_user)
        FileExtension.objects.get_or_create(extension='jpg')
        FileType.objects.get_or_create(id="IMAGE", mime="image/jpeg")

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_upload_many_success(self):
        url = reverse('api:file-upload-many')
        
        # Create 3 temporary files
        files = []
        for i in range(3):
            _, path = tempfile.mkstemp('.jpg')
            with open(path, 'wb') as f:
                f.write(b"fake image data")
            files.append(open(path, 'rb'))

        response = self.client.post(url, {'files': files}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(len(response.data), 3)
        self.assertEqual(File.objects.count(), 3)

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_upload_many_limit_exceeded(self):
        url = reverse('api:file-upload-many')
        
        files = []
        for i in range(21): # Limit is 20
            _, path = tempfile.mkstemp('.jpg')
            files.append(open(path, 'rb'))

        response = self.client.post(url, {'files': files}, format='multipart')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("Too many files", str(response.data))

    @override_settings(MEDIA_ROOT=tempfile.mkdtemp())
    def test_upload_many_atomic_failure(self):
        url = reverse('api:file-upload-many')
        
        # 1st file valid, 2nd file invalid (not allowed extension)
        _, path1 = tempfile.mkstemp('.jpg')
        _, path2 = tempfile.mkstemp('.exe') # Not in FileExtension
        
        files = [open(path1, 'rb'), open(path2, 'rb')]
        
        response = self.client.post(url, {'files': files}, format='multipart')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        # Check that NO files were created due to atomic transaction
        self.assertEqual(File.objects.count(), 0)

    def test_request_id_in_response(self):
        url = reverse('api:file-list')
        response = self.client.get(url, HTTP_X_REQUEST_ID='test-id-123')
        self.assertEqual(response['X-Request-ID'], 'test-id-123')
        
        # Test generation if missing
        response = self.client.get(url)
        self.assertIn('X-Request-ID', response)
        self.assertNotEqual(response['X-Request-ID'], '')
