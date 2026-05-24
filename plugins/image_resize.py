import io
import os
from PIL import Image
from django.core.files.storage import default_storage
from slugify import slugify
from datetime import datetime
from django.conf import settings
from resizeimage import resizeimage
from file_service.files.models import File
from django.db.models import signals

from trood.contrib.django.apps.plugins.core import TroodBasePlugin
from trood.contrib.django.apps.plugins.models import TroodPluginModel


class ImageResizePlugin(TroodBasePlugin):
    id = 'image_resize'
    name = 'Image Resize plugin'
    version = 'v1.0.0'

    default_config = {
        'async': False,
        'types': ['IMAGE'],
        'sizes': [{
            'name': 'thumb', 'type': 'thumbnail', 'width': 100, 'height': 100
        }]
    }

    @classmethod
    def register(cls):
        signals.post_save.connect(cls.resize, File)

    @classmethod
    def resize(cls, sender, **kwargs):
        plugin = TroodPluginModel.objects.filter(id=cls.id).first()
        if plugin and plugin.active:
            file = kwargs.get('instance')
            config = cls.get_config()
            if file.type_id in config['types'] and (not file.metadata or 'resized' not in file.metadata):
                name, ext = os.path.splitext(file.filename)
                original = Image.open(file.file)

                resized_links = {}

                for size in config['sizes']:
                    if size['type'] in ('crop', 'cover', 'contain', 'width', 'height', 'thumbnail'):
                        resized = resizeimage.resize(size['type'], original, [size['width'], size['height']])
                        resized_name = '{}-{}-{}{}'.format(
                            slugify(name),
                            slugify(size['name']),
                            datetime.now().strftime('%d%m%y%H%M%S'),
                            ext
                        )

                        buffer = io.BytesIO()
                        resized.save(buffer, resized.format)
                        default_storage.save(resized_name, buffer)

                        resized_links[size['name']] = f'{settings.FILES_BASE_URL}{resized_name}'

                if resized_links:
                    if not file.metadata:
                        file.metadata = {}

                    file.metadata['resized'] = resized_links
                    file.save()
