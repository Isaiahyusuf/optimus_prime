import pytest

from safety.health_monitor import HealthMonitor
from safety.kill_switch import KillSwitch


def test_health_monitor_starts_healthy():
    monitor = HealthMonitor()

    assert monitor.is_healthy() is True
    assert monitor.reason() is None


def test_health_monitor_can_mark_unhealthy():
    monitor = HealthMonitor()

    monitor.mark_unhealthy("Exchange connectivity lost")

    assert monitor.is_healthy() is False
    assert monitor.reason() == "Exchange connectivity lost"


def test_health_monitor_blocks_when_unhealthy():
    monitor = HealthMonitor()

    monitor.mark_unhealthy("Exchange connectivity lost")

    with pytest.raises(RuntimeError, match="EXECUTION_UNHEALTHY"):
        monitor.check()


def test_health_monitor_can_recover():
    monitor = HealthMonitor()

    monitor.mark_unhealthy("Temporary exchange failure")
    monitor.mark_healthy()

    assert monitor.is_healthy() is True
    assert monitor.reason() is None

    monitor.check()


def test_health_monitor_requires_failure_reason():
    monitor = HealthMonitor()

    with pytest.raises(ValueError):
        monitor.mark_unhealthy("")

    assert monitor.is_healthy() is True


def test_exchange_connectivity_check_marks_healthy():
    monitor = HealthMonitor()

    class FakeExchange:
        def get_server_time(self):
            return {"server_time": "1234567890"}

    assert monitor.check_exchange_connectivity(FakeExchange()) is True
    assert monitor.is_healthy() is True
    assert monitor.reason() is None


def test_exchange_connectivity_failure_marks_unhealthy():
    monitor = HealthMonitor()

    class FakeExchange:
        def get_server_time(self):
            raise RuntimeError("Connection refused")

    assert monitor.check_exchange_connectivity(FakeExchange()) is False
    assert monitor.is_healthy() is False
    assert "Exchange connectivity check failed" in monitor.reason()


def test_unhealthy_monitor_activates_kill_switch():
    monitor = HealthMonitor()
    kill_switch = KillSwitch()

    monitor.mark_unhealthy("Exchange connectivity lost")
    monitor.enforce_kill_switch(kill_switch)

    assert kill_switch.is_active() is True
    assert kill_switch.reason() == "Exchange connectivity lost"


def test_healthy_monitor_does_not_activate_kill_switch():
    monitor = HealthMonitor()
    kill_switch = KillSwitch()

    monitor.enforce_kill_switch(kill_switch)

    assert kill_switch.is_active() is False
    assert kill_switch.reason() is None


def test_exchange_failure_propagates_to_kill_switch():
    monitor = HealthMonitor()
    kill_switch = KillSwitch()

    class FakeExchange:
        def get_server_time(self):
            raise RuntimeError("Bybit unavailable")

    assert monitor.check_exchange_connectivity(FakeExchange()) is False
    assert monitor.is_healthy() is False

    monitor.enforce_kill_switch(kill_switch)

    assert kill_switch.is_active() is True
    assert "Bybit unavailable" in kill_switch.reason()
