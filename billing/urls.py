from django.urls import path
from . import views


urlpatterns = [
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('templates/', views.template_list, name='template_list'),
    path('notify/', views.notification_list, name='notification_list'),
    path('send/<str:email_type>/<str:invoice_id>/', views.send_email, name='send_email'),
    path('confirm/<str:token>/', views.confirm_termination, name='confirm_termination'),
    path('confirm/accept/<str:token>/', views.accept_termination, name='accept_termination')
]