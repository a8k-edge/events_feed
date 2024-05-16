import glob
import json
import logging
import os
import sys
from collections.abc import Collection
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Union

import jmespath
from prettytable import PrettyTable

from services import (BloombergService, C2CGlobalService,
                      CloudnairGoogleService, CohereService, ConfTechService,
                      DatabricksService, DatastaxService, DbtService,
                      DevEventsService, EventycoService, GDGService,
                      HopsworksService, LinuxFoundationService, MeetupService,
                      PostgresService, PythonService, RedisService,
                      ScalaLangService, TechCrunchService, TechMemeService,
                      WeaviateService)

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
    C2CGLOBAL = "C2C Global"
    DATABRICKS = "Databricks"
    DATASTAX = "Datastax"
    SCALA_LANG = "Scala Lang"
    CASSANDRA = "Cassandra"
    LINUX_FOUNDATION = "Linux Foundation"
    WEAVIATE = "Weaviate"
    REDIS = "Redis"
    POSTGRES = "Postgres"
    HOPSWORKS = "Hopsworks.ai"
    PYTHON = "Python"
    EVENTYCO = "Eventyco"
    DBT = "dbt"
    DEV_EVENTS = "dev.events"
    TECH_CRUNCH = "TechCrunch"
    TECH_MEME = "TechMeme"
    BLOOMBERG = "Bloomberg"
    CLOUDNAIR_GOOGLE = "Cloudnair"
    COHERE = "Cohere"


def main(delta_days: int = 3) -> None:
    setup_logging()

    # eb_events = EventbriteService().fetch_events(delta_days)
    # cassandra_events = CassandraService().fetch_events()

    meetup_events = MeetupService().fetch_events(delta_days)
    gdg_events = GDGService().fetch_events()
    conf_tech_events = ConfTechService().fetch_events()
    c2c_global_events = C2CGlobalService().fetch_events()
    databricks_events = DatabricksService().fetch_events()
    datastax_events = DatastaxService().fetch_events()
    scala_lang_events = ScalaLangService().fetch_events()
    linux_foundation_events = LinuxFoundationService().fetch_events()
    weaviate_events = WeaviateService().fetch_events()
    redis_events = RedisService().fetch_events()
    postgres_events = PostgresService().fetch_events()
    hopsworks_events = HopsworksService().fetch_events()
    python_events = PythonService().fetch_events()
    eventyco_events = EventycoService().fetch_events()
    dbt_events = DbtService().fetch_events()
    devevents_events = DevEventsService().fetch_events()
    tech_crunch_events = TechCrunchService().fetch_events()
    tech_meme_events = TechMemeService().fetch_events()
    bloomberg_events = BloombergService().fetch_events()
    cloudnair_events = CloudnairGoogleService().fetch_events()
    cohere_events = CohereService().fetch_events()

    events = transform_events(
        # (Source.EVENTBRITE.value, eb_events),
        # (Source.CASSANDRA.value, cassandra_events),

        (Source.MEETUP.value, meetup_events),
        (Source.GCD.value, gdg_events),
        (Source.CONFTECH.value, conf_tech_events),
        (Source.C2CGLOBAL.value, c2c_global_events),
        (Source.DATABRICKS.value, databricks_events),
        (Source.DATASTAX.value, datastax_events),
        (Source.SCALA_LANG.value, scala_lang_events),
        (Source.LINUX_FOUNDATION.value, linux_foundation_events),
        (Source.WEAVIATE.value, weaviate_events),
        (Source.REDIS.value, redis_events),
        (Source.POSTGRES.value, postgres_events),
        (Source.HOPSWORKS.value, hopsworks_events),
        (Source.PYTHON.value, python_events),
        (Source.EVENTYCO.value, eventyco_events),
        (Source.DBT.value, dbt_events),
        (Source.DEV_EVENTS.value, devevents_events),
        (Source.TECH_CRUNCH.value, tech_crunch_events),
        (Source.TECH_MEME.value, tech_meme_events),
        (Source.BLOOMBERG.value, bloomberg_events),
        (Source.CLOUDNAIR_GOOGLE.value, cloudnair_events),
        (Source.COHERE.value, cohere_events),
    )
    DataManager.save_data(events)


def transform_events(
    *event_groups: tuple[str, list[dict[str, Collection[str]]]],
) -> list[dict[str, str | None]]:
    schema_map: Dict[str, List[Transformer]] = {
        "id": ["id", "uuid", "type._id", "_id"],
        "title": ["title", "name"],
        "start_time": [
            "start_time",
            "dateTime",
            "dateTimeStart",
            # gcd start_time handle
            lambda d: None if 'start_time' in d else get_value(d, 'start_date'),
            "start_date+'T'+start_time",
            "startDate",
            "fieldDateTimeTimezone[0].startDate",
            "dates[0].date+'T'+dates[0].start",
            "start.date+'T'+start.time",
            "start",
        ],
        "end_time": [
            "end_time",
            "endTime",
            "dateTimeEnd",
            # gcd end_time handle
            lambda d: None if 'end_time' in d else get_value(d, 'end_date'),
            "end_date+'T'+end_time",
            "fieldDateTimeTimezone[0].endDate",
            "dates[0].date+'T'+dates[0].end",
            "end.date+'T'+end.time",
            "end",
        ],
        "timezone": [
            "timezone",
            "fieldDateTimeTimezone[0].timezone",
            "dates[0].dstimezone",
            "timeZone",
        ],
        "going": ["going", "rsvps.totalCount"],
        "description": ["description", "summary", "event_type_title+'\n'+chapter.description"],
        "event_url": [
            "event_url",
            "eventUrl",
            "url",
            "fieldEventUrl.url.path",
            "buttonLink.rawValue",
        ],
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
