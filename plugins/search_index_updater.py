import io
import re
import os

import textract
from django.db.models import signals
import requests

from file_service.files.models import FileTextContent
from trood.contrib.django.apps.plugins.core import TroodBasePlugin
from trood.contrib.django.apps.plugins.models import TroodPluginModel
from trood.core.utils import get_service_token


class SearchIndexUpdaterPlugin(TroodBasePlugin):
    id = 'search_index_updater'
    name = 'Search Index Updater Plugin'
    version = 'v0.0.1'

    default_config = {'async': False}

    def __init__(self):
        self.service_token = get_service_token()
        self.host = os.environ.get('SEARCH_URL', 'http://seacrh:8080')
        self.headers = {
            'Content-Type': 'application/json',
            'Authorization': self.service_token
        }

    @classmethod
    def register(cls):
        signals.post_save.connect(cls.update, FileTextContent)
        signals.post_delete.connect(cls.delete, FileTextContent)

    @classmethod
    def update(cls, sender, instance, created, **kwargs):
        plugin = TroodPluginModel.objects.filter(id=cls.id).first()
        if plugin and plugin.active:
            if created:
                action = 'create'
            else:
                action = 'update'

            response_data = {'events': [{
                'object': 'file',
                'action': action,
                'current': {
                    'id': instance.id,
                    'content': instance.content,
                    'source_id': instance.source_id,
                    'title': instance.title
                },
                'previous': {}
            }]}
            requests.post(f'{cls.host}/index/', json=response_data, headers=cls.headers)

    @classmethod
    def delete(cls, sender, instance, **kwargs):
        response_data = {'events': [{
            'object': 'file',
            'action': 'remove',
            'current': {},
            'previous': {
                'id': instance.id,
                'content': instance.content,
                'source_id': instance.source_id,
                'title': instance.title
            }
        }]}
        requests.post(f'{cls.host}/index/', json=response_data, headers=cls.headers)

