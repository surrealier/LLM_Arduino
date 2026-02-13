from src.input_gate import InputGate


def test_accepts_stream_when_idle():
    gate = InputGate()

    assert gate.start_stream() is True
    assert gate.can_accept_audio() is True
    assert gate.end_stream() == InputGate.DECISION_ACCEPT


def test_drops_stream_while_busy():
    gate = InputGate()
    gate.mark_busy()

    assert gate.start_stream() is False
    assert gate.can_accept_audio() is False
    assert gate.end_stream() == InputGate.DECISION_DROP


def test_ignores_end_without_active_stream():
    gate = InputGate()

    assert gate.end_stream() == InputGate.DECISION_IGNORE


def test_accepts_new_stream_after_busy_cleared():
    gate = InputGate()
    gate.mark_busy()
    assert gate.start_stream() is False
    assert gate.end_stream() == InputGate.DECISION_DROP

    gate.mark_idle()
    assert gate.start_stream() is True
    assert gate.end_stream() == InputGate.DECISION_ACCEPT
