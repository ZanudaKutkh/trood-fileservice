import os
import magic
import uuid
import mimetypes
import logging
from datetime import datetime

from slugify import slugify
from jsonfield import JSONField
from django.db import models
from django.conf import settings
from django.utils.translation import gettext_lazy as _
from rest_framework.exceptions import ValidationError

logger = logging.getLogger('file_service')


def create_unique_filename(instance, filename):
    """
    Provides a unique name for the file in such a way:
    filename + date(%d%m%y%H%M%S) + extention
    """
    name, ext = os.path.splitext(filename)
    return '{}-{}{}'.format(slugify(name), datetime.now().strftime('%d%m%y%H%M%S'), ext)


def validate_file_size(value):
    """
    Checks the validation of file size and return a
    proper message in case of exceeding the limit.
    """
    if value.size > settings.MAX_UPLOAD_SIZE:
        raise ValidationError(
            _('File %(name)s is too big. System limit: %(limit).1fMB') % {
                'name': value.name,
                'limit': settings.MAX_UPLOAD_SIZE / 1024 / 1024
            }
        )


def validate_file_extention(value):
    """
    Checks the validation of file extention and return a
    proper message in case of invalide extention.
    """
    ext = value.name.split('.')[-1].lower()

    # 1. System-wide restriction via ENV
    if settings.ALLOWED_EXTENSIONS and ext not in settings.ALLOWED_EXTENSIONS:
        raise ValidationError(_('Extension .%(ext)s is not allowed by system policy') % {'ext': ext})

    # 2. Dynamic restriction via DB
    allowed_extensions = FileExtension.objects.all().values_list('extension', flat=True)
    if len(allowed_extensions) and not ext in allowed_extensions and "*" not in allowed_extensions:
        raise ValidationError(_('Unsupported file type'))


class BaseModel(models.Model):
    """
    A base model which contains the id of owner.
    """
    owner = models.IntegerField(_('Owner'), null=True)

    class Meta:
        abstract = True


class FileType(BaseModel):
    """
    Type of files, such as:
    - image/jpeg
    - audio/x-hx-aac-adts
    etc.
    """
    id = models.CharField(primary_key=True, unique=True, max_length=32)
    mime = models.TextField()


class File(BaseModel):
    """
    File model with overriden save() function to customize saving behavior.
    """
    ACCESS_CHOICES = (
        ('PRIVATE', _('Private')),
        ('PROTECTED', _('Protected')),
        ('PUBLIC', _('Public'))
    )

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created = models.DateTimeField(_('Created Date'), auto_now_add=True)

    file = models.FileField(_('File'), upload_to=create_unique_filename, validators=(validate_file_size, validate_file_extention, ))

    filename = models.CharField(max_length=128, blank=True, null=True)
    origin_filename = models.CharField(_('Original filename'), max_length=128, blank=True, null=True)

    type = models.ForeignKey(FileType, null=True, blank=True, on_delete=models.SET_NULL)
    mimetype = models.CharField(_('Mimetype'), max_length=128, blank=True, null=True)
    size = models.IntegerField(_('File size'))
    ready = models.BooleanField(_('Ready'), default=True)

    deleted = models.BooleanField(_('Deleted'), default=False)

    metadata = JSONField(_('Meta data'), null=True, blank=True)
    tags = models.ManyToManyField('Tag', null=True, blank=True)
    access = models.CharField(choices=ACCESS_CHOICES, max_length=10, default='PROTECTED')

    def __str__(self):
        return self.filename if self.filename else 'No name'

    def save(self, *args, **kwargs):
        if not self.size:
            self.file.save(self.file.name, self.file, save=False)
            self.size = self.file.size

        if not self.mimetype:
            try:
                if settings.STORAGE_TYPE == 'DISK':
                    self.mimetype, enc = mimetypes.guess_type(self.file.path)
                elif settings.STORAGE_TYPE == 'DO_SPACES':
                    self.mimetype, enc = mimetypes.guess_type(self.file.storage.url(self.file.name))

                if not self.mimetype:
                    # Return pointer to start after magic check
                    self.mimetype = magic.from_buffer(self.file.read(2048), mime=True)
                    self.file.seek(0)
            except Exception as e:
                logger.exception("Mimetype detection failed for file %s", self.file.name)
                self.mimetype, _ = mimetypes.guess_type(self.file.name)
                if not self.mimetype:
                    self.mimetype = 'application/octet-stream'

            if self.mimetype:
                self.type = FileType.objects.filter(mime__contains=self.mimetype).first()

        super(File, self).save(*args, **kwargs)


class FileExtension(BaseModel):
    """
    Contains the extension of the file.
    """
    extension = models.CharField(max_length=255)


class FileTemplate(BaseModel):
    """
    File template model
    """
    alias = models.CharField(unique=True, max_length=128, null=True)
    name = models.CharField(max_length=128, blank=True, null=True)
    filename_template = models.CharField(max_length=128, blank=True, null=True)
    body_template = models.TextField()
    example_data = JSONField(null=True)


class Tag(BaseModel):
    """
    Contains file tags.
    """
    tag = models.CharField(unique=True, max_length=128)


class FileTextContent(models.Model):
    """
    A model, which contains the content of file text.
    """
    source = models.ForeignKey(File, on_delete=models.CASCADE)
    content = models.TextField()
    created = models.DateTimeField(auto_now_add=True)
    title = models.TextField(null=True)
