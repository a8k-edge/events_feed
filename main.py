import glob
import json
import logging
import os
import sys
from collections.abc import Collection
from datetime import datetime
from enum import Enum
from typing import Any
from typing import Callable
from typing import Dict
from typing import List
from typing import Union

import jmespath
from prettytable import PrettyTable

from client import ConfTechService
from client import GDGService
from client import MeetupService


Transformer = Union[str, Callable]


def setup_logging():
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


class Source(Enum):
    EVENTBRITE = "Eventbrite"
    MEETUP = "Meetup"
    CONFTECH = "ConfTech"
    GCD = "GCD"


def main(delta_days: int = 3) -> None:
    setup_logging()

    # eb_events = EventbriteService().fetch_events(delta_days)
    meetup_events = MeetupService().fetch_events(delta_days)
    gdg_events = GDGService().fetch_events()
    conf_tech_events = ConfTechService().fetch_events()

    events = transform_events(
        # (Source.EVENTBRITE.value, eb_events),
        (Source.GCD.value, gdg_events),
        (Source.MEETUP.value, meetup_events),
        (Source.CONFTECH.value, conf_tech_events),
    )
    DataManager.save_data(events)


def transform_events(
    *event_groups: tuple[str, list[dict[str, Collection[str]]]]
) -> list[dict[str, str | None]]:
    schema_map: Dict[str, List[Transformer]] = {
        "id": ["id"],
        "title": ["title", "name"],
        "start_time": [
            "dateTime",
            # gcd start_time handle
            lambda d: None if 'start_time' in d else get_value(d, 'start_date'),
            "start_date+'T'+start_time",
            "startDate",
        ],
        "end_time": [
            "endTime",
            # gcd end_time handle
            lambda d: None if 'end_time' in d else get_value(d, 'end_date'),
            "end_date+'T'+end_time",
        ],
        "timezone": ["timezone"],
        "going": ["going"],
        "description": ["description", "summary", "event_type_title+'\n'+chapter.description"],
        "event_url": ["eventUrl", "url"],
        "image_url": ["group.groupPhoto.source", "image.original.url"],
        "is_online_event": ["onlineVenue", "is_online_event", "online", "event_type"],
    }
    transformed_events = []
    for source, events in event_groups:
        for event in events:
            transformed_events.append(transform_to_unified_schema(event, source, schema_map))
    return transformed_events


def transform_to_unified_schema(
    input_dict: Dict[str, Any],
    source: str,
    schema_map: Dict[str, List[Transformer]],
) -> Dict[str, Any]:
    output_dict = {"source": source}

    for unified_key, transformers in schema_map.items():
        values = []
        for transformer in transformers:
            if callable(transformer):
                value = transformer(input_dict)
            else:
                value = get_value(input_dict, transformer)
            if value == "T":
                continue
            if value is not None:
                values.append(value)

        # if len(values) > 1:
        #     logging.error(f"Multiple values found: {values=}, {transformers=}, {input_dict=}")
        #     raise ValueError(f"Multiple matching keys found {unified_key=}.")

        output_dict[unified_key] = values[0] if values else None

    return output_dict


def get_value(input_dict: dict[str, Any], query: str) -> Any:
    if '+' in query:
        tokens = query.split('+')
        values = [
            jmespath.search(token.strip(), input_dict)
            if token[0] not in ["'", '"']
            else token[1:-1]
            for token in tokens
        ]
        if len(tokens) != len(values):
            return None
        return ''.join([v for v in values if v])
    else:
        return jmespath.search(query.strip(), input_dict)


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
