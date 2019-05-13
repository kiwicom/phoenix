import smtplib

from django.conf import settings


def get_smtp(host, port, user, passwd, use_ssl=True):
    if use_ssl:
        smtp = smtplib.SMTP_SSL(host, port)
        smtp.login(user, passwd)
    else:
        smtp = smtplib.SMTP(host, port)
    return smtp


def send_email(message):
    """Helper function for sending email."""
    with get_smtp(settings.SMTP_HOST, settings.SMTP_PORT, settings.SMTP_USER, settings.SMTP_PASSWORD,
                  settings.SMTP_SSL) as smtp:
        smtp.send_message(message)
