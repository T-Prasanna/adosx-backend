from django.urls import path
from reconciler import views

urlpatterns = [
    path("orgs/", views.orgs_list),
    path("discrepancies/", views.discrepancies),
]
