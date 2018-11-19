"""Link to docs: http://docs.gunicorn.org/en/stable/settings.html"""
import multiprocessing

workers = multiprocessing.cpu_count() * 2 + 1

bind = ":8000"

accesslog = "-"  # send access log to stdout
