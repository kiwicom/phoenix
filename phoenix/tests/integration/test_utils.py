from phoenix.integration.utils import is_pingdom_recovery


def test_is_pingdom_recovery_transaction():
    test_data = {
        "check_type": "TRANSACTION",
        "previous_state": "FAILING",
        "current_state": "SUCCESS",
    }
    assert is_pingdom_recovery(test_data)

    test_data["current_state"] = "FAILING"
    assert not is_pingdom_recovery(test_data)


def test_is_pingdom_recovery_uptime():
    test_data = {"check_type": "HTTP", "previous_state": "DOWN", "current_state": "UP"}
    assert is_pingdom_recovery(test_data)
    test_data["current_state"] = "DOWN"
    assert not is_pingdom_recovery(test_data)
