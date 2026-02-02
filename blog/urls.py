from django.urls import path
from . import views

app_name = 'blog'

urlpatterns = [
	path("articles/", views.ArticleList.as_view(), name='article-list-url'),
	path("articles/<int:pk>/", views.ArticleDetail.as_view(), name="article-detail-url"),
]
