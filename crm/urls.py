from django.contrib import admin
from django.urls import path, re_path, include

from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import TemplateView

from django.contrib.sitemaps.views import sitemap
from exhibition.sitemap import sitemaps


handler404 = 'exhibition.views.__404__'

urlpatterns = [
	path('admin/', admin.site.urls),
	path('accounts/', include('allauth.urls')),
	path('designers/', include('designers.urls')),
	path('', include('exhibition.urls')),
	path('', include('rating.urls')),
	path('', include('blog.urls')),
	re_path(r'^ckeditor/', include('ckeditor_uploader.urls')),
	re_path(r'^chaining/', include('smart_selects.urls')),
	re_path(r'^sitemap\.xml$', sitemap, {'sitemaps': sitemaps}, name='django.contrib.sitemaps.views.sitemap'),
	path('robots.txt', TemplateView.as_view(template_name="robots.txt", content_type='text/plain')),
]

if settings.DEBUG:
	import debug_toolbar

	urlpatterns.append(path('__debug__/', include(debug_toolbar.urls)))
	urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

