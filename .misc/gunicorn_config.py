"""Link to docs: http://docs.gunicorn.org/en/stable/settings.html"""
import os

workers = os.environ.get("WEB_CONCURRENCY", 4)

bind = ":8000"

accesslog = "-"  # send access log to stdout
