import glob
import json
import logging
import os
import sys
from collections.abc import Collection
from datetime import datetime
from typing import Any

from prettytable import PrettyTable

from client import ConfTechService
from client import MeetupService


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


def main(delta_days: int = 3) -> None:
    # eb_events = EventbriteService().fetch_events(delta_days)
    meetup_events = MeetupService().fetch_events(delta_days)
    conf_tech_events = ConfTechService().fetch_events()

    events = transform_events(meetup_events, conf_tech_events)
    DataManager.save_data(events)


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
        "start_time": ["dateTime", "start_date+'T'+start_time", "startDate"],
        "end_time": ["endTime", "end_date+'T'+end_time"],
        "timezone": ["timezone"],
        "going": ["going"],
        "description": ["description", "summary"],
        "event_url": ["eventUrl", "url"],
        "image_url": ["group.groupPhoto.source", "image.original.url"],
        "is_online_event": ["onlineVenue", "is_online_event", "online"],
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
