import pytest

from safety.kill_switch import KillSwitch


def test_kill_switch_starts_inactive():
    kill_switch = KillSwitch()

    assert kill_switch.is_active() is False
    assert kill_switch.reason() is None


def test_kill_switch_can_activate_with_reason():
    kill_switch = KillSwitch()

    kill_switch.activate("Emergency safety stop")

    assert kill_switch.is_active() is True
    assert kill_switch.reason() == "Emergency safety stop"


def test_kill_switch_blocks_when_active():
    kill_switch = KillSwitch()

    kill_switch.activate("Emergency safety stop")

    with pytest.raises(RuntimeError, match="KILL_SWITCH_ACTIVE"):
        kill_switch.check()


def test_kill_switch_can_deactivate():
    kill_switch = KillSwitch()

    kill_switch.activate("Emergency safety stop")
    kill_switch.deactivate()

    assert kill_switch.is_active() is False
    assert kill_switch.reason() is None

    kill_switch.check()


def test_kill_switch_requires_activation_reason():
    kill_switch = KillSwitch()

    with pytest.raises(ValueError):
        kill_switch.activate("")

    assert kill_switch.is_active() is False
