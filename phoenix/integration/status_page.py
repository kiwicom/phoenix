import functools
import json
import logging

from django.conf import settings
import requests

logger = logging.getLogger()


DISABLED = False

mandatory_settings = ("STATUS_PAGE_API_KEY", "STATUS_PAGE_URL", "STATUS_PAGE_ID")
for name in mandatory_settings:
    if not getattr(settings, name, None):
        logger.warning(f"{name} missing... StatusPage functionality disabled.")
        DISABLED = True


def run_if_enabled(f):
    @functools.wraps(f)
    def wrapper(*args, **kwargs):
        if not DISABLED:
            return f(*args, **kwargs)

    return wrapper


api_key = settings.STATUS_PAGE_API_KEY
api = requests.Session()
api.headers.update({"Authorization": api_key})


def log_error(resp, message):
    logger.error(f"{message} [{resp.status_code}]: {resp.json()}")


def get_url(path):
    base_url = settings.STATUS_PAGE_API_URL
    return f"{base_url}{path}"


def update_incident_url(incident_id):
    base_url = settings.STATUS_PAGE_UPDATE_INCIDENT_URL
    url = f"{base_url}pages/{settings.STATUS_PAGE_ID}/incidents/{incident_id}#update"
    return url


@run_if_enabled
def create_incident(components, eta=None):
    url = get_url(f"/pages/{settings.STATUS_PAGE_ID}/incidents")
    body = "We are trying to resolve the problem."
    if eta:
        body = f"{body} ETA: {eta}"
    component_names = [c.name for c in components]
    incident_name = f"{', '.join(component_names)} incident"
    status = "partial_outage"
    components_status = {c.status_page_id: status for c in components}
    incident = {
        "incident": {
            "name": incident_name,
            "status": "investigating",
            "body": body,
            "component_ids": [c.status_page_id for c in components],
            "components": components_status,
        }
    }
    resp = api.post(url, data=json.dumps(incident))
    if resp.status_code >= requests.codes.bad_request:
        log_error(resp, "Error create StatuPage incident")
        return None
    return resp.json()


@run_if_enabled
def resolve_incident(incident_id, components):
    url = get_url(f"/pages/{settings.STATUS_PAGE_ID}/incidents/{incident_id}")
    status = "operational"
    components_status = {c.status_page_id: status for c in components}
    incident = {
        "incident": {
            "status": "resolved",
            "boyd": "Incident has been resolved.",
            "component_ids": [c.status_page_id for c in components],
            "components": components_status,
        }
    }
    resp = api.patch(url, data=json.dumps(incident))
    if resp.status_code >= requests.codes.bad_request:
        log_error(resp, "Error resolving StatuPage incident")
        return None
    return resp.json()["id"]
