from community import views
from django.conf.urls import url

urlpatterns = [
    url(r'^create$',
        views.CommunityCreateView.as_view(), name='community_create'),
    url(r'^(?P<community_id>[0-9]+)$',
        views.CommunityDetailView.as_view(), name='community_detail'),
    url(r'^create_addon$',
        views.ListCreateAddOnView.as_view(), name='create_addon'),
    url(r'^list_addons$',
        views.ListCreateAddOnView.as_view(), name='addon_list'),
    url(r'^list_addons/(?P<addon_id>[0-9]+)$',
        views.AddOnDetailView.as_view(), name='addon_detail'),
    url(r'^delete_addon/(?P<addon_id>[0-9]+)$',
        views.AddOnDeleteView.as_view(), name='delete_addon'),
]