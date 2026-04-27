from django.contrib import admin

from billing.models import MessageTemplate

@admin.register(MessageTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'subject', 'updated_at')
    list_filter = ('template_type',)
    search_fields = ('name', 'subject')
    ordering = ('template_type',)