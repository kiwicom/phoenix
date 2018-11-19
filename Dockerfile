FROM python:3.7-alpine3.8

WORKDIR /app

COPY *requirements.txt /app/

ARG pypi_username
ARG pypi_password
RUN apk add --no-cache --virtual=.run-deps curl pcre libpq libffi libxslt libxml2 make tini jq && \
    apk add --no-cache --virtual=.build-deps musl-dev build-base libffi-dev postgresql-dev curl-dev libxslt-dev libxml2-dev linux-headers pcre-dev && \
    pip install --no-cache-dir -r requirements.txt -r tests-requirements.txt && \
    apk del .build-deps

COPY . /app/

RUN apk add --no-cache nodejs nodejs-npm && \
    npm config set unsafe-perm true && \
    npm install -g sass@1.6.2 && \
    sass phoenix/core/static/style.scss phoenix/core/static/style.css && \
    sass phoenix/outages/static/outages/outage_form.scss phoenix/outages/static/outages/outage_form.css && \
    apk del nodejs nodejs-npm && \
    cd /app

ENV DJANGO_SETTINGS_MODULE=phoenix.core.settings

ENTRYPOINT ["/sbin/tini", "--"]
RUN python manage.py collectstatic --no-input
CMD [ "ddtrace-run", "gunicorn", "phoenix", "--config", ".misc/gunicorn_config.py" ]

EXPOSE 8000
LABEL name=phoenix version=dev
