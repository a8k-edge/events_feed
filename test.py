import json
import os
from urllib.parse import urlparse
from urllib.parse import urlunparse

import pytest
import requests

from client import CONF_TECH_URL
from client import ConfTechService
from client import EVENTBRITE_URL
from client import LOCATIONS
from client import MEETUP_URL
from client import MeetupService
from main import DataManager
from main import main


MOCK_DIR = 'mock_data'
URL_MAPPINGS = {
    EVENTBRITE_URL: "eventbrite.json",
    MEETUP_URL: "meetup.json",
    CONF_TECH_URL: "conf_tech.json",
}


def mock_requests_post(*args, **kwargs):
    parsed_url = urlparse(args[0])
    cleared_url = parsed_url._replace(query="")
    url = str(urlunparse(cleared_url))
    file_name = URL_MAPPINGS.get(url)

    if file_name:
        with open(os.path.join(MOCK_DIR, file_name), "r", encoding='utf-8') as file:
            return MockResponse(json.load(file))

    raise ValueError(f"Unmocked URL: {url}")


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
def test_meetup_mock_integration(monkeypatch):
    delta_days = 3
    _, actual_data = MeetupService()._fetch_page(delta_days, location=LOCATIONS[0], cursor='')
    monkeypatch.setattr(requests, "post", mock_requests_post)
    _, mock_data = MeetupService()._fetch_page(delta_days, location=LOCATIONS[0], cursor='')

    # with open('logs\\actual_schema.json', 'w', encoding='utf-8') as f:
    #     json.dump(extract_schema(actual_data), f, indent=4)
    # with open('logs\\mock_schema.json', 'w', encoding='utf-8') as f:
    #     json.dump(extract_schema(mock_data), f, indent=4)
    assert extract_schema(actual_data) == extract_schema(mock_data), "Schema validation failed"


@pytest.mark.skip
def test_conf_tech_mock_integration(monkeypatch):
    actual_data = ConfTechService().fetch_events()
    monkeypatch.setattr(requests, "post", mock_requests_post)
    mock_data = ConfTechService().fetch_events()

    actual_schema = extract_schema(actual_data)
    mock_schema = extract_schema(mock_data)

    # with open('logs\\actual_schema.json', 'w', encoding='utf-8') as f:
    #     json.dump(extract_schema(actual_data), f, indent=4)
    # with open('logs\\mock_schema.json', 'w', encoding='utf-8') as f:
    #     json.dump(extract_schema(mock_data), f, indent=4)
    assert contains_key_values(actual_schema, mock_schema)


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


def contains_key_values(dict1, dict2):
    for key, value in dict2.items():
        if key not in dict1:
            return False

        if isinstance(value, dict):
            if not isinstance(dict1[key], dict):
                return False
            if not contains_key_values(dict1[key], value):
                return False
        else:
            if dict1[key] != value:
                return False

    return True
