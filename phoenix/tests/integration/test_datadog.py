from unittest.mock import patch

from phoenix.integration.datadog import get_all_slack_channels


@patch("phoenix.integration.datadog.api.Monitor.get_all")
def test_get_all_slack_channels(mocked_get_all):
    mocked_get_all.return_value = (
        "@slack-alerts{{/is_warning}}{{#is_warning_"
        "recovery}}@slack-alerts{{/is_warning_recov"
        "ery}}{{#is_alert}}@slack-alerts-a{{/is_alert"
        "}}{{#is_alert_recovery}}@slack-alerts-test{{"
        "/is_alert_recovery}}"
    )
    data = get_all_slack_channels()
    test_data = ["alerts-test", "alerts", "alerts-a"]
    assert data.sort() == test_data.sort()
