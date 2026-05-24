from django.conf import settings
from django.conf.urls import include, url
from django.conf.urls.static import static
from django.views.generic import TemplateView
from rest_framework.routers import DefaultRouter

from trood.contrib.django.apps.plugins.views import TroodPluginsViewSet
from .files import views as files_views

router = DefaultRouter()

router.register(r'files', files_views.FilesViewSet)
router.register(r'extensions', files_views.FileExtensionViewSet)
router.register(r'types', files_views.FileTypeViewSet)
router.register(r'templates', files_views.FileTemplateViewSet)
router.register(r'plugins', TroodPluginsViewSet)
router.register(r'probe', files_views.ProbeViewset, basename='probe')
router.register(r'tag', files_views.FileTag)

urlpatterns = [
    url(r'^api/v1.0/', include((router.urls, 'file_service'), namespace='api')),
]

if settings.DEBUG:
    urlpatterns += [
        url('swagger/', TemplateView.as_view(template_name='swagger_ui.html'), name='swagger-ui'),
    ] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT) \
      + static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
