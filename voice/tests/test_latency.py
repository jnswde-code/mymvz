"""Latency figures per answer and per call."""

import logging

from mymvz_voice.latency import LatencyLog


def test_answers_without_measured_turn_are_skipped():
    log = LatencyLog()
    log.observe({})
    log.observe({"llm_node_ttft": 0.2})
    assert log.values == []
    assert log.summary() is None


def test_each_answer_is_logged_as_numbers_only(caplog):
    log = LatencyLog()
    with caplog.at_level(logging.INFO, logger="mymvz_voice.latency"):
        log.observe({"e2e_latency": 0.8123, "llm_node_ttft": 0.4, "tts_node_ttfb": 0.25})
        log.observe({"e2e_latency": 1.2})
    assert caplog.messages == [
        "Latenz Satzende bis Antwort: 0.812 s (LLM erstes Token 0.400 s, TTS erstes Audio 0.250 s)",
        "Latenz Satzende bis Antwort: 1.200 s (LLM erstes Token –, TTS erstes Audio –)",
    ]


def test_summary_at_the_end_of_the_call(caplog):
    log = LatencyLog()
    for value in (0.5, 0.9, 0.7):
        log.observe({"e2e_latency": value})
    with caplog.at_level(logging.INFO, logger="mymvz_voice.latency"):
        log.log_summary()
    assert caplog.messages == ["Latenz im Gespräch: 3 Antworten, Median 0.700 s, höchstens 0.900 s"]
