import logging

from omnivoice.session import _log_call_end


def test_call_end_log_excludes_transcripts_and_payloads(caplog):
    sentinel = "PRIVATE_CALLER_CONTENT_SHOULD_STAY_IN_STORAGE"
    metrics = {
        "errors": 1,
        "turns": [{"user_transcript": sentinel, "agent_response": sentinel}],
        "end_reason": sentinel,
        "tool_summary": {"arguments": sentinel},
    }
    with caplog.at_level(logging.INFO, logger="omnivoice.media"):
        _log_call_end(metrics)
    assert "Call ended errors=1 turns=1" in caplog.text
    assert sentinel not in caplog.text
