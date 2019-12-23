# The Phoenix

A system for managing outage announcements on Slack.

[![Python: 3.7](https://img.shields.io/badge/python-3.7-blue.svg)](https://python.org)
[![Code style: black](https://img.shields.io/badge/code%20style-black-black.svg)](https://github.com/ambv/black)
[![Discord](https://img.shields.io/discord/427417507276783616.svg)](https://discord.gg/2FXqeha)
[![Gitlab pipeline status (branch)](https://img.shields.io/gitlab/pipeline/kiwicom/phoenix/master.svg)](https://gitlab.com/kiwicom/phoenix/pipelines)

## Example announcement
![phoenix example announcement](example_announcement.png)

<!-- Generated using https://github.com/thlorenz/doctoc -->
<!-- START doctoc generated TOC please keep comment here to allow auto update -->
<!-- DON'T EDIT THIS SECTION, INSTEAD RE-RUN doctoc TO UPDATE -->
**Table of Contents**

- [Features](#features)
    - [Permission model in Phoenix](#permission-model-in-phoenix)
    - [Authorization using Google Suite groups](#authorization-using-google-suite-groups)
    - [Gitlab issues due date notification](#gitlab-issues-due-date-notification)
    - [Monitoring notifications agregation](#monitoring-notifications-agregation)
- [Prerequisites](#prerequisites)
    - [Slack](#slack)
    - [Access keys (Passing the keys to phoenix is described in Configuration)](#access-keys-passing-the-keys-to-phoenix-is-described-in-configuration)
        - [IDP - GOOGLE](#idp-google)
        - [Google API (optional)](#google-api-optional)
        - [Gitlab API (optional)](#gitlab-api-optional)
        - [Monitoring (optional)](#monitoring-optional)
- [Configuration](#configuration)
- [Development setup](#development-setup)
- [Scheduled jobs](#scheduled-jobs)
- [Testing](#testing)

<!-- END doctoc generated TOC please keep comment here to allow auto update -->


## Features

### Permission model in Phoenix

Phoenix uses two django permissions for authorization:
- `Can add announcement` — only users with this permission can use Slack commands for creating announcements.
- `Can change outage` — users with this permission can edit all announcements without limitations.

You can create your own permission group setup using these permissions or you can run `docker-compose exec app python manage.py init_instance` which will create the following two groups for you:
- `on_call` — uses the permission `Can add announcement`. Can be assigned to users automatically.
- `edit_all_outages` — uses the permission `Can change outage`. Has to be assigned manually.

### Authorization using Google Suite groups (Optional)
Phoenix has the ability to automatically update the `on_call` group. It will list specified groups in G Suite and add users from those groups to the Phoenix group `on_call`.

**Setup:**
- Create and configure `GOOGLE_SERVICE_ACCOUNT` ([see Google API](#google-api-optional)).
- Specify groups that should be used for synchronizaition. Go to admin (e.g.: `localhost:8000/admin`)`Home > Integration > Google groups` and create entries for specific G Suite groups.

### Due date notifications for Gitlab issues (Optional)
Phoenix supports custom notifications for the due dates of Gitlab issues. It can be configured to send notifications a certain number of days before the due date is reached. Phoenix will then notify the assignees of the issue via direct messages on Slack.

**Setup:**
- Create and configure GITLAB_PRIVATE_TOKEN ([see Gitlab API](#gitlab-api-optional))
- Optionaly you can specify list of days to notify before due date using environment variable `GITLAB_POSTMORTEM_DAYS_TO_NOTIFY`. Default is [3,7], this means phoenix will send notifications 3 and 7 days before due date.

### Monitoring notifications agregation (Optional)
Phoenix has small feature for agregating notification data from monitoring. Currently it supports integrations with Pingdom (webhook) and Datadog (scrapping slack channels for notifications). There's simple list view in Web GUI under `Monitors`. Metabase can be easily used for data analysis.

**Setup:**
- `Pingdom`: simply add the webhook `<phoenix_url>/integration/pingdom` to all checks you want to aggregate the data from.
- `Datadog`: generate and configure `DATADOG_API_KEY` and `DATADOG_APP_KEY`. Phoenix will join (daily task) all Slack channels used by Datadog for alerting and it will aggregate the data about all alerts.


## Prerequisites

### Slack

- Slack token with the following scopes:

  - `channels:history`
  - `channels:read`
  - `channels:write`
  - `chat:write:bot`
  - `chat:write:user`
  - `groups:write`
  - `im:write`
  - `bot`
  - `commands`
  - `pins:write`
  - `reactions:read`
  - `users:read`
  - `users:read.email`
  - `users.profile:read`

- Slack channel ID for announcements
- Slack bot
- Slash command — point to `<phoenix_url>/slack/announce`
- Interactive components — point to `<phoenix_url>/slack/interaction`
- Event subscription — point to `<phoenix_url>/slack/events` and subscribe to bot events: `reaction_added`, `message.channels` and workspace event `team_join`


### Access keys (Passing keys to Phoenix is described in [Configuration](#configuration))

#### IDP — GOOGLE

- Create Google oauth credentials for Phoenix, callback url pattern is `<phoenix_url>/accounts/google/login/callback/`.
- Credentials will be used in Django admin section create a social application object.

#### Google API (optional)
- Needed for the authorization system and listing users from specified Google groups.
- Create a Google service account with `domain-wide authority` and scope `https://www.googleapis.com/auth/admin.directory.group.member.readonly`.

#### Gitlab API (optional)
- Needed for issue due date notification. Lists all issues in a repository and notifies on approaching due dates.
- Create a Gitlab `personal access token` with an `api` scope. Access will be granted for all repositories under the user who created the `personal access token`.

#### Monitoring (optional)
- Phoenix supports implementations with Datadog and Sentry. You just need to generate the keys and pass them to Phoenix.
- For `datadog` generate Datadog API and APP keys.
- For `sentry` get Sentry DSN.


## Configuration

Phoenix is able to retrieve configuration/secrets from environment variables. The list below includes the names of configuration options.

- `DB_HOST, DB_NAME, DB_USER, DB_PASSWORD, DB_PORT` - database connection settings. Defaults to `postgres://postgres:postgres@postgres/postgres` if not provided
- `ALLOWED_EMAIL_DOMAIN` - can specify email address domain restriction. These settings will only allow logins from a specified domain. User synchronization will transform all email domains to the specified one. If not specified, all domains are allowed. Default: `None`
- `SLACK_TOKEN` — Slack application OAuth Access Token
- `SLACK_ANNOUNCE_CHANNEL_ID` — Slack channel ID where Phoenix should announce outages
- `SLACK_BOT_ID` — Bot ID
- `SLACK_BOT_TOKEN` — Bot User OAuth Access Token
- `SLACK_VERIFICATION_TOKEN` — used to verify whether Phoenix API endpoints are called by Slack
- `SLACK_EMOJI` — emoji name, e.g. `point_up`, If you add a reaction with this emoji to a comment in an outage-dedicated channel, it will be shared in the thread under the main outage announcement. Default: `point_up`
- `SLACK_NOTIFY_SALES_CHANNEL_ID` — sets `channel ID` for notification about announcement of outage which affects sales. (optional)
- `SLACK_NOTIFY_B2B_CHANNEL_ID` — sets `channel ID` for notification about announcement of outage which affects B2B partners. (optional)
- `SECRET_KEY` — secret key for Django application
- `DEBUG` - switches to debug mode. Default: False
- `DATADOG_API_KEY` — [see Monitoring](#monitoring-optional)
- `DATADOG_APP_KEY` — [see Monitoring](#monitoring-optional)
- `DATADOG_SERVICE_NAME` — sets `env` tag for Datadog. Default: `Phoenix-default`
- `SENTRY_DSN` — [see Monitoring](#monitoring-optional)
- `GOOGLE_SERVICE_ACCOUNT` — Google API service account data (json format) [see Google API](#google-api-optional)
- `GOOGLE_ACC` — specifies which Google account will be used by the Google API
- `GITLAB_URL` — defines the Gitlab API url. Default `https://gitlab.skypicker.com`. If you don't specify a value, the Postmortem notifications feature will be turned off
- `GITLAB_PRIVATE_TOKEN` — Gitlab API access token [see Gitlab API](#gitlab-api-optional). If you don't specify the value, Postmortem notifications feature will be turned off.
- `GITLAB_POSTMORTEM_DAYS_TO_NOTIFY` — used for setting the list of days to notify postmortem assignees before the issue due date. Default `3,7` (3 and 7 days before ETA)
- `REDIS_URL` — specifies a Redis URL (in GCP k8s, this is the IP address of the Redis service). Default: `redis`
- `REDIS_PORT` — specifies a Redis port. Default: `6379`
- `NOTIFY_BEFORE_ETA` — defines in minutes how long before an announcement ETA to notify assignees. Default: 10 (minutes)

- `DEVEL_GOOGLE_OAUTH_CLIENT_ID` — optional setting used in the `init_devel_instance` command
- `DEVEL_GOOGLE_OAUTH_SECRET` — optional setting used in the `init_devel_instance` command
- `ALLOW_ALL_TO_NOTIFY` - allow everyone to announce outage

## Development setup

Create an `.env` file next to `docker-compose.yml` file with your desired configuration, for example:

```
# THIS IS USED FOR BUILD
PYPI_USERNAME=<your username for pypi.skypicker.com>
PYPI_PASSWD=<password>


# specify these following variables if you don't want to use vault
DATABASE_URL=postgres://postgres:postgres@postgres/postgres
SLACK_TOKEN=<TOKEN>
SLACK_ANNOUNCE_CHANNEL_ID=<channel id>
SLACK_BOT_ID=<TOKEN>
SLACK_BOT_TOKEN=<TOKEN>
SLACK_VERIFICATION_TOKEN=<TOKEN>
SLACK_EMOJI=<emoji>
DEBUG=True
ALLOWED_EMAIL_DOMAIN=<email domain>

# This are used by init_devel_instance command to automate initial setup
DEVEL_GOOGLE_OAUTH_CLIENT_ID=<client id>
DEVEL_GOOGLE_OAUTH_SECRET=<secret>
```

Run phoenix:

`docker-compose up`

Phoenix is available at port `8000`. Run migrations:

`docker-compose exec app python manage.py migrate`

**Next, you can run a custom Django command (if you've specified DEVEL_GOOGLE_OAUTH_CLIENT_ID and DEVEL_GOOGLE_OAUTH_SECRET):**

`docker-compose exec app python manage.py init_devel_instance`

**This will execute all the steps in the next section. Or you can do this manually:**

Import Slack users to Phoenix:

`docker-compose exec app python manage.py sync_users`

Create superuser for the admin section:

`docker-compose exec app python manage.py createsuperuser`

Afterwards, you can log in to the admin section at `localhost:8000/admin` to view the data.

In admin section, it's required to execute the following configuration:

- Update the site domain to `localhost:8000` (based on this is generated absolute url outside request/response context)
- Create a social application object based on this instructions: <https://django-allauth.readthedocs.io/en/latest/providers.html#django-configuration>
- Create systems objects for Outages. Currently, this is manual. In the future, data migration will take care of this

**Now you can logout. Navigate to `http://localhost:8000` and log in via Google.**

## Scheduled jobs

- Every 20 minutes it executes a check of unresolved outages. It pings assignees to inform them that the ETA will be reached soon. Manual run: `docker-compose exec app python manage.py notify`
- Every 8 hours it executes an update of user groups according to Google Groups (if turned on). Manual run: `docker-compose exec app python manage.py sync_user_groups`
- Once a day it executes a task that lists all Datadog configurations and it joins Phoenix Slack bot in all Slack channels used by Datadog (if turned on). Manual run: `docker-compose exec app python manage.py join_alert_channels`
- Once a day it executes a Gitlab issues notification which notifies the assignees about an approaching due date (if configured). Manual run: `docker-compose exec app python manage.py gitlab_notify`


## Testing

Running analysis tools (coala, pylint).
**Pylint will wait for kiwi PYPI credentials at the beginning of the `pylint installdeps` step. There's no prompt for a username.**

`tox`

Phoenix unittests require database for testing.. Docker and docker-compose are required for running tests locally.

`docker-compose -f docker-compose.yml -f docker-compose-tests.yml run app pytest`
