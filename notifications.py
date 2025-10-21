# Create new file: notifications.py
from models import db, Notification
from datetime import datetime

def create_notification(user_id, title, message, notification_type=None, related_id=None):
    """Create a new notification for a user"""
    notification = Notification(
        user_id=user_id,
        title=title,
        message=message,
        notification_type=notification_type,
        related_id=related_id
    )
    
    db.session.add(notification)
    db.session.commit()
    return notification

def create_bulk_notifications(user_ids, title, message, notification_type=None, related_id=None):
    """Create notifications for multiple users"""
    notifications = []
    for user_id in user_ids:
        notification = Notification(
            user_id=user_id,
            title=title,
            message=message,
            notification_type=notification_type,
            related_id=related_id
        )
        notifications.append(notification)
    
    db.session.add_all(notifications)
    db.session.commit()
    return notifications

def get_unread_count(user_id):
    """Get count of unread notifications for a user"""
    return Notification.query.filter_by(
        user_id=user_id, 
        is_read=False
    ).count()

def mark_as_read(notification_id, user_id):
    """Mark a specific notification as read"""
    notification = Notification.query.filter_by(
        id=notification_id, 
        user_id=user_id
    ).first()
    
    if notification:
        notification.is_read = True
        db.session.commit()
    return notification

def mark_all_as_read(user_id):
    """Mark all notifications as read for a user"""
    Notification.query.filter_by(
        user_id=user_id, 
        is_read=False
    ).update({'is_read': True})
    db.session.commit()