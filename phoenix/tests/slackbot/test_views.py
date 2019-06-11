from phoenix.slackbot.views import get_handler, handle_events


def test_get_handler():
    handlers = (("events", handle_events), ("test_not_existing", None))
    for event_type, expected in handlers:
        assert get_handler(event_type) is expected
