from email.headerregistry import Group

from django.contrib import admin
from django.contrib.auth.admin import GroupAdmin
from django.contrib.auth.models import Group

from billing.models import ActionTracker, EmailLog, GroupPermission, EmailTemplate, Notification

class GroupPermissionInline(admin.TabularInline):
    model = GroupPermission
    extra = 1

admin.site.unregister(Group)

@admin.register(Group)
class CustomGroupAdmin(GroupAdmin):
    inlines = [GroupPermissionInline]

@admin.register(EmailLog)
class EmailLogAdmin(admin.ModelAdmin):
    list_display = ['ticket', 'invoice', 'email_type', 'status', 'retry_count', 'sent_by', 'sent_at']
    list_filter = ['status', 'email_type']
    search_fields = ('invoice__id', 'ticket')
    readonly_fields = ['ticket', 'sent_at']

    actions = ['retry_selected_emails']

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'type', 'message', 'created_at']
    list_filter = ['type']
    filter_horizontal = ['target_groups']

@admin.register(EmailTemplate)
class EmailTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'template_type', 'subject', 'is_active', 'updated_at')
    list_filter = ('template_type', 'is_active')
    search_fields = ('name', 'subject')
    ordering = ('template_type',)

@admin.register(ActionTracker)
class ActionTrackerAdmin(admin.ModelAdmin):
    list_display = ['invoice', 'suspension_sent', 'confirmation_sent', 'queue_sent', 'termination_sent']
    readonly_fields = ['updated_at']