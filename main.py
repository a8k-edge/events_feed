import glob
import json
import logging
import os
import sys
from collections.abc import Collection
from datetime import datetime
from typing import Any
from typing import Final
from typing import NamedTuple

import requests
from prettytable import PrettyTable

from payload import Eventbrite
from payload import Meetup


os.makedirs('logs', exist_ok=True)
logfile = os.path.join('logs', f'logs_{datetime.now():%Y-%m-%d_%H.%M}.log')
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(logfile),
        logging.StreamHandler(sys.stdout),
    ],
)


class Location(NamedTuple):
    name: str
    lat: float
    lon: float
    radius: int


# Relevant hardcoded location from meetup.com
LOCATIONS: Final = [
    Location(name="USA", lat=37.0902, lon=-95.7129, radius=1200),
    # Location(name="Canada", lat=43.6532, lon=-79.3832, radius=200),
    # Location(name="Austria", lat=48.2082, lon=16.3738, radius=50),
    Location(name="Australia", lat=-37.8136, lon=144.9631, radius=1000),
    Location(name="United Kingdom", lat=51.5072, lon=0.1276, radius=100),
    Location(name="Italy", lat=45.4642, lon=9.19, radius=50),
    Location(name="Finland", lat=60.1699, lon=24.9384, radius=250),
    Location(name="Denmark", lat=55.6761, lon=12.5683, radius=75),
    # Location(name="China", lat=31.2304, lon=121.4737, radius=1000),
    Location(name="Brazil", lat=-23.5558, lon=-46.6396, radius=1000),
    # Location(name="Belgium", lat=50.8476, lon=4.3572, radius=50),
    Location(name="Netherlands", lat=52.103207, lon=5.608742, radius=50),
    Location(name="Singapore", lat=1.355184, lon=103.819524, radius=20),
    # Location(name="Kenya", lat=0.659799, lon=37.884, radius=200),
    Location(name="Israel", lat=32.0853, lon=34.7818, radius=200),
    # Location(name="Ireland", lat=53.3498, lon=-6.2603, radius=200),
    # Location(name="India", lat=21.99029, lon=78.651019, radius=750),
    Location(name="Hong Kong", lat=22.3193, lon=114.1694, radius=20),
    # Location(name="Greece", lat=37.9838, lon=23.7275, radius=150),
    Location(name="Germany", lat=52.52, lon=13.405, radius=100),
    # Location(name="France", lat=48.8566, lon=2.3522, radius=250),
    # Location(name="UAE", lat=25.2048, lon=55.2708, radius=100),
    Location(name="Switzerland", lat=47.3769, lon=8.5417, radius=50),
    # Location(name="Sweden", lat=63.441294, lon=16.578449, radius=400),
    # Location(name="Spain", lat=41.3874, lon=2.1686, radius=200),
    Location(name="South Africa", lat=-29.792839, lon=24.76505, radius=400),
    Location(name="Norway", lat=61.02041, lon=8.784942, radius=500),
    # Location(name="Nigeria", lat=8.811187, lon=8.094624, radius=400),
    Location(name="New Zealand", lat=-42.288765, lon=173.190186, radius=300),
]


def main(delta_days: int = 3) -> None:
    eb_events = fetch_eventbrite_events(delta_days)
    meetup_events = fetch_meetup_events(delta_days)

    events = transform_events(eb_events, meetup_events)
    DataManager.save_data(events)


def fetch_eventbrite_events(delta_days: int) -> list[dict[str, Collection[str]]]:
    page = 1
    has_next_page = True
    events = []
    token = Eventbrite.generate_token()
    threshold: Final = 15
    page_count = -1

    while has_next_page and page < threshold:
        logging.info(f"EB Request start {page=} of {page_count=}")
        try:
            response = requests.post(
                'https://www.eventbrite.com/api/v3/destination/search/',
                cookies=Eventbrite.get_cookies(token),
                headers=Eventbrite.get_headers(token),
                json=Eventbrite.get_json(page=page, delta_days=delta_days),
            )
            response.raise_for_status()
            data = response.json()
        except Exception as exc:
            logging.info(f"[FAILED] EB fetched {page=}")
            logging.error(exc, exc_info=True)
            raise

        events += data['events']['results']
        page_count = data['events']['pagination']['page_count']
        has_next_page = page_count > page
        page += 1

    logging.info("Finished fetching EB events")
    return events


def fetch_meetup_events(delta_days: int) -> list[dict[str, Collection[str]]]:
    events = []
    location_len = len(LOCATIONS)

    for count, location in enumerate(LOCATIONS, start=1):
        logging.info(f"Meetup Location start {count}/{location_len} {location=}")
        has_next_page = True
        # Pagination token
        cursor = ''
        page = 1

        while has_next_page:
            logging.info(f"Meetup Request start {location.name=} {page=}")
            try:
                response = requests.post(
                    'https://www.meetup.com/gql',
                    headers=Meetup.get_headers(),
                    json=Meetup.get_json(
                        location=location,
                        cursor=cursor,
                        delta_days=delta_days,
                    ),
                )
                response.raise_for_status()
                data = response.json()
            except Exception as exc:
                logging.info(f"[FAILED] Meetup fetched {location.name=} {page=}")
                logging.error(exc, exc_info=True)
                raise

            has_next_page = data['data']['rankedEvents']['pageInfo']['hasNextPage']
            cursor = data['data']['rankedEvents']['pageInfo']['endCursor']
            events += [event['node'] for event in data['data']['rankedEvents']['edges']]
            page += 1

    logging.info("Finished fetching Meetup events")
    return events


def transform_events(
    *event_groups: list[dict[str, Collection[str]]]
) -> list[dict[str, str | None]]:
    transformed_events = []
    for events in event_groups:
        for event in events:
            transformed_events.append(transform_to_unified_schema(event))
    return transformed_events


def transform_to_unified_schema(input_dict: dict[str, Collection[str]]) -> dict[str, str | None]:
    schema_map = {
        "id": ["id"],
        "title": ["title", "name"],
        "start_time": ["dateTime", "start_date+'T'+start_time"],
        "end_time": ["endTime", "end_date+'T'+end_time"],
        "timezone": ["timezone"],
        "going": ["going"],
        "description": ["description", "summary"],
        "event_url": ["eventUrl", "url"],
        "image_url": ["group.groupPhoto.source", "image.original.url"],
        "is_online_event": ["onlineVenue", "is_online_event"],
    }

    output_dict = {}
    for unified_key, original_keys in schema_map.items():
        values = []
        for key in original_keys:
            value = get_value(input_dict, key)
            if value is not None:
                values.append(value)
        # if input_dict has several keys from a list map
        try:
            assert len(values) <= 1, values
        except AssertionError:
            logging.error(f"{values=} {original_keys=} {input_dict}")
            raise
        output_dict[unified_key] = values[0] if values else None

    return output_dict


def get_value(input_dict: dict[str, Collection[str]], key: str) -> str | None:
    # If '+' in key, handle it as a concatenation of tokens
    if '+' in key:
        tokens = key.split('+')
        values = [
            get_value_from_key(input_dict, token.strip())
            if token[0] not in ["'", '"']
            else token[1:-1]
            for token in tokens
        ]
        if None in values:
            return None
        else:
            # getting type error as values may include None
            return ''.join(values)  # type: ignore
    else:
        return get_value_from_key(input_dict, key.strip())


def get_value_from_key(input_dict: dict[str, Collection[str]], key: str) -> Any | None:
    keys = key.split('.')
    current_dict = input_dict
    for k in keys:
        if isinstance(current_dict, dict):
            current_dict = current_dict.get(k)  # type: ignore
        else:
            return None
    return current_dict


class DataManager:
    DATA_DIRECTORY = "data"

    @classmethod
    def save_data(cls, events: list[dict[str, str | None]]) -> None:
        os.makedirs(cls.DATA_DIRECTORY, exist_ok=True)

        date_str = datetime.now().strftime('%Y_%m_%d_%H.%M')
        filename = os.path.join(cls.DATA_DIRECTORY, f'data_{date_str}.json')

        data = {
            'date': datetime.now().isoformat(),
            'events': events,
        }

        with open(filename, 'w') as f:
            json.dump(data, f)
        logging.info(f"Data saved in file: {filename}")

    @classmethod
    def load_latest_data(cls) -> Any:
        files = glob.glob(f'{cls.DATA_DIRECTORY}/data_*.json')
        if not files:
            return {}

        latest_file = max(files, key=os.path.getctime)
        with open(latest_file, 'r') as f:
            data = json.load(f)

        logging.info(f"Data loaded from file: {latest_file}")
        return data


if __name__ == '__main__':
    main(delta_days=1)

    data = DataManager.load_latest_data()
    table = PrettyTable()
    table.field_names = ["id", "title", "start_time", "going"]
    for event in data['events']:
        table.add_row([event["id"], event["title"], event["start_time"], event["going"]])

    print("Events:")
    print(table)

    print(f"Total events: {len(data['events'])}")
