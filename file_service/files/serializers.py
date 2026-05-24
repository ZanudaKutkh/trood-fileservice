import os
from uuid import uuid4

from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from rest_framework import serializers
from rest_framework.fields import JSONField

from file_service.files import models as files_models

from django.conf import settings


def move_uploaded_file(file, name=str(uuid4())):
    _, ext = os.path.splitext(file.name)
    file_path = default_storage.save(name + ext, ContentFile(file.read()))
    return file_path


class FileSerializer(serializers.ModelSerializer):
    file_url = serializers.SerializerMethodField()
    metadata = serializers.JSONField(required=False, allow_null=True)

    class Meta:
        model = files_models.File
        fields = (
            'id', 'owner', 'created', 'file',
            'file_url', 'filename', 'origin_filename',
            'type', 'mimetype', 'size',
            'ready', 'metadata', 'deleted', 'access', 'tags'
        )
        read_only_fields = ('created', 'id', 'type', 'mimetype', 'size', 'file_url', )

    def get_file_url(self, obj):
        return settings.FILES_BASE_URL + obj.file.name

    def to_internal_value(self, data):
        if 'file' in data and data.get('filename', '') == '':
            data.update({
                'filename': data['file'].name,
                'origin_filename': data['file'].name
            })

        return super(FileSerializer, self).to_internal_value(data)

    def to_representation(self, instance):
        result = super(FileSerializer, self).to_representation(instance)

        result.pop('file')
        return result


class FileExtensionSerializer(serializers.ModelSerializer):
    class Meta:
        model = files_models.FileExtension
        fields = ('id', 'extension')

    def save(self, **kwargs):
        extension = self.validated_data['extension'].lower()
        instance = super().save(**kwargs)
        instance.extension = extension
        instance.save()
        return instance


class FileTypeSerializer(serializers.ModelSerializer):
    class Meta:
        model = files_models.FileType
        fields = ('id', 'mime')


class FileTemplateSerializer(serializers.ModelSerializer):
    example_data = serializers.JSONField(required=False)

    class Meta:
        model = files_models.FileTemplate
        fields = ('id', 'alias', 'name', 'filename_template', 'body_template', 'example_data')


class FromTemplateSerializer(serializers.Serializer):
    data = serializers.JSONField()
    format = serializers.ChoiceField(choices=settings.FILE_GENERATORS.keys())
    template = serializers.CharField()
    access = serializers.ChoiceField(choices=files_models.File.ACCESS_CHOICES)
    tags = serializers.PrimaryKeyRelatedField(queryset=files_models.Tag.objects.all(), many=True)


class FileTagSerializer(serializers.ModelSerializer):
    class Meta:
        model = files_models.Tag
        fields = ('id', 'tag')


class FileTextContentSerializer(serializers.ModelSerializer):
    class Meta:
        model = files_models.FileTextContent
        fields = '__all__'
