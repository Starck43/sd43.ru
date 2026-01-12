from django.urls import path, re_path
from . import views

app_name = 'exhibition'

urlpatterns = [
	path('', views.index, name='index'),

	path('exhibitions/', views.ExhibitionsList.as_view(), kwargs={'exh_year': None}, name='exhibitions-list-url'),
	path('exhibition/<exh_year>/', views.ExhibitionDetail.as_view(), name='exhibition-detail-url'),
	path('exhibition/<exh_year>/<slug>/', views.WinnerProjectDetail.as_view(), name='winner-detail-url'),

	path('category/', views.CategoryList.as_view(), kwargs={'slug': None}, name='category-list-url'),
	path('category/<slug>/', views.ProjectsList.as_view(), name='projects-list-url'),
	path('projects/<owner>/project-<project_id>/', views.ProjectDetail.as_view(), name='project-detail-url'),
	path('projects/<exh_year>/', views.ProjectsListByYear.as_view(), name='projects-list-by-year-url'),

	path('jury/', views.JuryList.as_view(), kwargs={'exh_year': None}, name='jury-list-url'),
	path('jury/<exh_year>/', views.JuryList.as_view(), name='jury-list-url'),
	path('jury/<slug>/detail/', views.JuryDetail.as_view(), name='jury-detail-url'),

	path('partners/', views.PartnersList.as_view(), kwargs={'exh_year': None}, name='partners-list-url'),
	path('partners/<exh_year>/', views.PartnersList.as_view(), name='partners-list-url'),
	path('partner/<slug>/detail/', views.PartnerDetail.as_view(), name='partner-detail-url'),

	path('exhibitors/', views.ExhibitorsList.as_view(), kwargs={'exh_year': None}, name='exhibitors-list-url'),
	path('exhibitors/<exh_year>/', views.ExhibitorsList.as_view(), name='exhibitors-list-url'),
	path('exhibitor/<slug>/detail/', views.ExhibitorDetail.as_view(), name='exhibitor-detail-url'),

	path('winners/', views.WinnersList.as_view(), kwargs={'exh_year': None}, name='winners-list-url'),
	path('winners/<exh_year>/', views.WinnersList.as_view(), name='winners-list-url'),

	path('events/', views.EventsList.as_view(), kwargs={'exh_year': None}, name='events-list-url'),
	path('events/<exh_year>/', views.EventsList.as_view(), name='events-list-url'),
	path('events/<exh_year>/<pk>/', views.EventDetail.as_view(), name='event-detail-url'),

	# path('exhibition/events/<pk>/', views.event_detail.as_view(), name='event-detail-url'),
	# path('exhibition/<exh_year>/events/<pk>/', views.event_detail.as_view(), name='event-detail-url'),
	path('contacts/', views.contacts, name='contacts-url'),
	path('policy/', views.registration_policy, name='policy-url'),

	re_path(r'^search/', views.SearchSite.as_view(), name='search-results'),
	re_path(r'^success/$', views.success_message, name='success-message-url'),
	path('account/', views.account, name='account-url'),
	path('account/deactivate/', views.deactivate_user, name="deactivate-user"),
	path('reset_password/', views.send_reset_password_email),

	path('api/get-exhibitions-by-owner/', views.get_exhibitions_by_owner, name='get_exhibitions_by_owner'),
	path('api/get-exhibitors-by-exhibition/', views.get_exhibitors_by_exhibition, name='get_exhibitors_by_exhibition'),
	path('api/nominations-categories-mapping/', views.get_nominations_categories, name='nominations-mapping-url'),
	path('api/get-nominations/', views.get_nominations_for_exhibition, name='get-nominations-for-exhibition-url'),
	path('api/search-exhibitors/', views.search_exhibitors, name='search-exhibitors'),

	path('portfolio/add/', views.portfolio_upload, kwargs={'pk': None}, name='portfolio-upload-url'),
	path('portfolio/edit/<pk>', views.portfolio_upload, name='portfolio-upload-url'),
	path('health/', views.HealthCheckView.as_view(), name='health-check'),

	# path('<str:section>/about/', views.about_us, name='about-us-url'),
	# path('about/', views.about_us, name='about-us-url'),
]
