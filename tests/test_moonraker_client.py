"""Tests for the shared Moonraker client's non-network logic.

The transport itself is not exercised here: it needs a real server and the
value in this module is the response parsing and the retry ordering, both of
which are pure.
"""

from __future__ import annotations

import pytest

from moonraker_client import MoonrakerClient, status_of

QUERY_URL = "http://printer.local:7125/printer/objects/query"


class TestStatusOf:
    def test_extracts_the_status_mapping(self):
        payload = {"result": {"status": {"extruder": {"temperature": 210.0}}}}
        assert status_of(payload) == {"extruder": {"temperature": 210.0}}

    @pytest.mark.parametrize(
        "payload",
        [
            None,
            {},
            "not a mapping",
            {"result": None},
            {"result": "not a mapping"},
            {"result": {}},
            {"result": {"status": None}},
            {"result": {"status": []}},
        ],
    )
    def test_every_unexpected_shape_collapses_to_empty(self, payload):
        assert status_of(payload) == {}


class TestCandidateUrls:
    def test_the_configured_url_comes_first(self):
        client = MoonrakerClient(QUERY_URL)
        assert client.candidate_urls()[0] == QUERY_URL

    def test_the_scheme_swapped_variant_is_offered_as_a_fallback(self):
        client = MoonrakerClient(QUERY_URL)
        assert "https://printer.local:7125/printer/objects/query" in (
            client.candidate_urls()
        )

    def test_there_are_no_duplicates(self):
        client = MoonrakerClient(QUERY_URL)
        urls = client.candidate_urls()
        assert len(urls) == len(set(urls))

    def test_a_remembered_working_url_is_tried_first(self):
        client = MoonrakerClient(QUERY_URL)
        swapped = "https://printer.local:7125/printer/objects/query"
        client._working_url = swapped
        assert client.candidate_urls()[0] == swapped


class TestHostLabel:
    def test_reports_host_and_port(self):
        assert MoonrakerClient(QUERY_URL).host_label == "printer.local:7125"
