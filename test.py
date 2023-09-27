import json
import os

import pytest
import requests

from client import EVENTBRITE_URL
from client import LOCATIONS
from client import MEETUP_URL
from client import MeetupService
from main import DataManager
from main import main


MOCK_DIR = 'mock_data'


def mock_requests_post(*args, **kwargs):
    if args[0] == EVENTBRITE_URL:
        with open(os.path.join(MOCK_DIR, "eventbrite.json"), "r", encoding='utf-8') as file:
            return MockResponse(json.load(file))
    elif args[0] == MEETUP_URL:
        with open(os.path.join(MOCK_DIR, "meetup.json"), "r", encoding='utf-8') as file:
            return MockResponse(json.load(file))
    else:
        raise ValueError(f"Unmocked URL: {args[0]}")


class MockResponse:
    def __init__(self, json_data):
        self._json = json_data

    def json(self):
        return self._json

    @staticmethod
    def raise_for_status():
        pass


def test_main_integration(monkeypatch):
    monkeypatch.setattr(requests, "post", mock_requests_post)
    main()

    saved_data = DataManager.load_latest_data()
    assert saved_data, "No data found in the saved file"
    assert 'events' in saved_data, "Events not found in the saved data"


@pytest.mark.skip
def test_mock_integration(monkeypatch):
    delta_days = 3
    _, actual_data = MeetupService()._fetch_page(delta_days, location=LOCATIONS[0], cursor='')
    monkeypatch.setattr(requests, "post", mock_requests_post)
    _, mock_data = MeetupService()._fetch_page(delta_days, location=LOCATIONS[0], cursor='')

    # with open('logs\\actual_schema.json', 'w', encoding='utf-8') as f:
    #     json.dump(extract_schema(actual_data), f, indent=4)
    # with open('logs\\mock_schema.json', 'w', encoding='utf-8') as f:
    #     json.dump(extract_schema(mock_data), f, indent=4)
    assert extract_schema(actual_data) == extract_schema(mock_data), "Schema validation failed"


def extract_schema(json_obj, depth=0, max_depth=6):
    if depth > max_depth:
        return None

    if isinstance(json_obj, dict):
        schema = {}
        for key, value in json_obj.items():
            schema[key] = extract_schema(value, depth + 1, max_depth)
        return schema
    elif isinstance(json_obj, list):
        if json_obj:
            # Assume all items in the list have the same schema and use the first one
            return extract_schema(json_obj[0], depth + 1, max_depth)
        else:
            return []
    else:
        return type(json_obj).__name__
