from django.urls import path
from . import views


urlpatterns = [
    path('invoices/', views.invoice_list, name='invoice_list'),
    path('templates/', views.template_list, name='template_list'),
    path('notify/', views.notification_list, name='notification_list'),
    path('send/<str:email_type>/<str:invoice_id>/', views.send_email, name='send_email'),
    path("retry-email/", views.retry_email, name="retry_email"),
    path('confirm/<str:token>/', views.confirm_termination, name='confirm_termination'),
    path('confirm/<str:token>/verify/', views.verify_otp, name='verify_otp'),
    path('confirm/<str:token>/resend/', views.resend_otp, name='resend_otp'),
]