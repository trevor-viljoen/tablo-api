"""Tests for Pydantic models."""

import pytest
from pydantic import ValidationError

from tablo_api.models import TabloDevice, TabloChannel, TabloStream, _CloudChannel


class TestTabloDevice:
    def test_valid(self):
        d = TabloDevice(sid="SID_1", name="Tablo", local_url="http://10.0.0.5:8885",
                        lighthouse_token="tok")
        assert d.sid == "SID_1"

    def test_missing_field_raises(self):
        with pytest.raises(ValidationError):
            TabloDevice(sid="x", name="x", local_url="x")  # lighthouse_token missing


class TestTabloChannel:
    def test_display_name(self):
        ch = TabloChannel(identifier="S1", call_sign="KFOR", major=4, minor=1)
        assert ch.display_name == "4.1 KFOR"

    def test_sort_order(self):
        a = TabloChannel(identifier="A", call_sign="A", major=5, minor=2)
        b = TabloChannel(identifier="B", call_sign="B", major=4, minor=1)
        assert sorted([a, b]) == [b, a]

    def test_defaults(self):
        ch = TabloChannel(identifier="x", call_sign="X", major=3, minor=1)
        assert ch.network == ""
        assert ch.kind == "ota"


class TestTabloStream:
    def test_valid(self):
        s = TabloStream(channel_identifier="S1", playlist_url="http://example.com/a.m3u8")
        assert s.playlist_url == "http://example.com/a.m3u8"
        assert s.token is None

    def test_optional_fields(self):
        s = TabloStream(channel_identifier="S1", playlist_url="http://x.com/a.m3u8",
                        token="tok", expires="2026-01-01T00:00:00Z", keepalive=30)
        assert s.keepalive == 30


class TestCloudChannelParsing:
    def test_ota_channel(self):
        raw = {
            "identifier": "S1",
            "name": "KFOR",
            "kind": "ota",
            "ota": {"major": 4, "minor": 1, "callSign": "KFOR", "network": "NBC"},
        }
        ch = _CloudChannel.model_validate(raw)
        assert ch.ota is not None
        assert ch.ota.major == 4

    def test_unknown_fields_ignored(self):
        raw = {"identifier": "X", "kind": "ota", "logos": [], "someNewField": True}
        ch = _CloudChannel.model_validate(raw)
        assert ch.identifier == "X"
