import smtplib

from django.conf import settings


def send_email(message):
    """Helper function for sending email."""
    with smtplib.SMTP(settings.SMTP_ADDR) as smtp:
        smtp.send_message(message)
