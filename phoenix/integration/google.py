from django.conf import settings
from google.oauth2 import service_account  # pylint: disable=no-name-in-module
import googleapiclient.discovery

SCOPES = ["https://www.googleapis.com/auth/admin.directory.group.member.readonly"]


def get_directory_api():
    credentials = service_account.Credentials.from_service_account_info(
        settings.GOOGLE_SERVICE_ACCOUNT, scopes=SCOPES
    )
    if settings.GOOGLE_ACC:
        credentials = credentials.with_subject(settings.GOOGLE_ACC)
    return googleapiclient.discovery.build(
        "admin", "directory_v1", credentials=credentials
    )
