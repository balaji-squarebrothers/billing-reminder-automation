def notification_count(request):
    try:
        user = getattr(request, "user", None)

        if not user or not user.is_authenticated:
            return {"unread_notifications_count": 0}

        from billing.models import Notification

        count = Notification.objects.filter(is_read=False).count()

        return {"unread_notifications_count": count}

    except Exception:
        return {"unread_notifications_count": 0}