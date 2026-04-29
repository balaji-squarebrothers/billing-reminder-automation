from billing.models import GroupPermission


def user_can(user, action):
    if not user or not user.is_authenticated:
        return False
    if user.is_superuser:
        return True
    user_group_ids = user.groups.values_list('id', flat=True)
    return GroupPermission.objects.filter(
        group_id__in=user_group_ids,
        action=action
    ).exists()

def get_user_permissions(user):
    return {
        "can_send_suspension": user_can(user, "send_suspension"),
        "can_send_confirmation": user_can(user, "send_confirmation"),
        "can_send_queue": user_can(user, "send_queue"),
        "can_send_termination": user_can(user, "send_termination"),
        "can_edit_email": user_can(user, "edit_email_body"),
    }