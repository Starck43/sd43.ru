from django.contrib import admin
from django.urls import path, re_path, include

from django.conf import settings
from django.conf.urls.static import static
from django.views.generic.base import TemplateView

from django.contrib.sitemaps.views import sitemap
from exhibition.sitemap import sitemaps as exhibition_sitemaps
from designers.sitemap import designer_sitemaps
from exhibition.views import robots_txt

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
	# Sitemap для основного домена (выставка)
	path('sitemap.xml', sitemap, {'sitemaps': exhibition_sitemaps}, name='exhibition-sitemap'),

	# Sitemap для поддоменов дизайнеров
	path('designers/<str:slug>/sitemap.xml', sitemap, {'sitemaps': designer_sitemaps}, name='designer-sitemap'),
	path('robots.txt', robots_txt, name='robots-txt'),
]

if settings.DEBUG:
	import debug_toolbar

	urlpatterns.append(path('__debug__/', include(debug_toolbar.urls)))
	urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)

