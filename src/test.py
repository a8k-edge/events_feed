import json
import os
from urllib.parse import urlparse, urlunparse

import pytest
import requests

from fetch import DataManager, main
from services import (C2CGLOBAL_URL, CONF_TECH_URL, EVENTBRITE_URL, GDG_URL,
                      LOCATIONS, MEETUP_URL, C2CGlobalService, ConfTechService,
                      GDGService, MeetupService)

MOCK_DIR = 'mock_data'
URL_MAPPINGS = {
    EVENTBRITE_URL: "eventbrite.json",
    MEETUP_URL: "meetup.json",
    CONF_TECH_URL: "conf_tech.json",
    GDG_URL: "gdg.json",
    C2CGLOBAL_URL: "c2c_global.json",
}


def test_main_integration(monkeypatch):
    monkeypatch.setattr(requests, "post", mock_requests)
    monkeypatch.setattr(requests, "get", mock_requests)
    main()

    saved_data = DataManager.load_latest_data()
    assert saved_data, "No data found in the saved file"
    assert 'events' in saved_data, "Events not found in the saved data"


@pytest.mark.skip
@pytest.mark.parametrize("service, method_name, methods_args", [
    (MeetupService(), "_fetch_page", (2, LOCATIONS[0], '')),
    (ConfTechService(), "fetch_events", tuple()),
    (GDGService(), "fetch_events", tuple()),
    (C2CGlobalService(), "fetch_events", tuple()),
])
def test_integration(monkeypatch, service, method_name, methods_args):
    actual_result = getattr(service, method_name)(*methods_args)
    monkeypatch.setattr(requests, "post", mock_requests)
    monkeypatch.setattr(requests, "get", mock_requests)
    mock_result = getattr(service, method_name)(*methods_args)

    actual_data = actual_result[1] if isinstance(actual_result, tuple) else actual_result
    mock_data = mock_result[1] if isinstance(mock_result, tuple) else mock_result

    actual_schema = extract_schema(actual_data)
    mock_schema = extract_schema(mock_data)

    # with open('logs\\actual_schema.json', 'w', encoding='utf-8') as f:
    #     json.dump(extract_schema(actual_data), f, indent=4)
    # with open('logs\\mock_schema.json', 'w', encoding='utf-8') as f:
    #     json.dump(extract_schema(mock_data), f, indent=4)

    assert contains_key_values(actual_schema, mock_schema)


def mock_requests(*args, **kwargs):
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
