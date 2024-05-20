import json
import logging
import re
import secrets
import time
import uuid
from collections.abc import Collection
from datetime import datetime, timedelta, timezone
from typing import Any, Final, NamedTuple
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

import cloudscraper
import jmespath
import pytz
import requests
from bs4 import BeautifulSoup
from chompjs import parse_js_object
from dateutil import parser

from tz import whois_timezone_info

EVENTBRITE_URL = 'https://www.eventbrite.com/api/v3/destination/search/'
MEETUP_URL = 'https://www.meetup.com/gql2'
CONF_TECH_URL = 'https://29flvjv5x9-dsn.algolia.net/1/indexes/*/queries'
GDG_URL = 'https://gdg.community.dev/api/event/'
C2CGLOBAL_URL = 'https://events.c2cglobal.com/api/search/'
DATABRICKS_URL = 'https://www.databricks.com/en-website-assets/page-data/events/page-data.json'
DATASTAX_URL = 'https://bbnkhnhl.apicdn.sanity.io/v2022-01-05/data/query/production'
SCALA_LANG_URL = 'https://www.scala-lang.org/events/'
CASSANDRA_URL = 'https://cassandra.apache.org/_/events.html'
LINUX_FOUNDATION_URL = 'https://events.linuxfoundation.org/'
WEAVIATE_URL = 'https://core.service.elfsight.com/p/boot/'
REDIS_URL = 'https://redis.com/api/archive'
POSTGRES_URL = 'https://www.postgresql.org/about/events/'
HOPSWORKS_URL = 'https://www.hopsworks.ai/events'
PYTHON_URL = 'https://www.python.org/events/'
EVENTYCO_URL = (
    'https://www.eventyco.com/events/conferences'
    '/tech~scala~elixir~data~devops~sre~security~rust~kafka~golang'
)
DBT_URL = 'https://www.getdbt.com/events'
DEV_EVENTS_URL = 'https://dev.events/'
TECH_CRUNCH_URL = 'https://techcrunch.com/wp-json/wp/v2/tc_events'
TECH_MEME_URL = 'https://www.techmeme.com/events'
BLOOMBERG_URL = 'https://www.bloomberglive.com/calendar/'
CLOUDNAIR_GOOGLE_URL = 'https://cloudonair.withgoogle.com/api/events?collection=6ce82b&order=asc&state=FUTURE&page=1&shallow=true'  # noqa: E501
COHERE_URL = 'https://cohere.com/events'
SAMSUNG_URL = 'https://www.samsung.com/global/ir/ir-events-presentations/events/'
TSMC_URL = 'https://pr.tsmc.com/english/events/tsmc-events'
NVIDIA_URL = 'https://www.nvidia.com/content/dam/en-zz/Solutions/about-nvidia/calendar/en-us.json'
GITHUB_URL = 'https://github.com/events'
SNOWFLAKE_URL = 'https://www.snowflake.com/about/events/'

EB_THRESHOLD = 15
MEETUP_PAGE_SIZE = 50
UA_HINTS = {
    'sec-ch-ua': '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-platform': '"Windows"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36"
    ),
}
ACCEPT_HEADERS = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9,ru-RU;q=0.8,ru;q=0.7,fr;q=0.6,uk;q=0.5,ar;q=0.4,de;q=0.3',  # noqa: E501
}


class Location(NamedTuple):
    name: str
    lat: float
    lon: float
    radius: int


# Relevant hardcoded location from meetup.com
LOCATIONS: Final = [
    Location(name="USA", lat=37.0902, lon=-95.7129, radius=1200),
    Location(name="Canada", lat=43.6532, lon=-79.3832, radius=200),
    Location(name="Austria", lat=48.2082, lon=16.3738, radius=50),
    Location(name="Australia", lat=-37.8136, lon=144.9631, radius=1000),
    Location(name="United Kingdom", lat=51.5072, lon=0.1276, radius=100),
    Location(name="Italy", lat=45.4642, lon=9.19, radius=50),
    Location(name="Finland", lat=60.1699, lon=24.9384, radius=250),
    Location(name="Denmark", lat=55.6761, lon=12.5683, radius=75),
    Location(name="Brazil", lat=-23.5558, lon=-46.6396, radius=1000),
    Location(name="Netherlands", lat=52.103207, lon=5.608742, radius=50),
    Location(name="Singapore", lat=1.355184, lon=103.819524, radius=20),
    Location(name="Israel", lat=32.0853, lon=34.7818, radius=200),
    Location(name="Ireland", lat=53.3498, lon=-6.2603, radius=200),
    Location(name="Hong Kong", lat=22.3193, lon=114.1694, radius=20),
    Location(name="Greece", lat=37.9838, lon=23.7275, radius=150),
    Location(name="Germany", lat=52.52, lon=13.405, radius=100),
    Location(name="France", lat=48.8566, lon=2.3522, radius=250),
    Location(name="Switzerland", lat=47.3769, lon=8.5417, radius=50),
    Location(name="Sweden", lat=63.441294, lon=16.578449, radius=400),
    Location(name="Spain", lat=41.3874, lon=2.1686, radius=200),
    Location(name="South Africa", lat=-29.792839, lon=24.76505, radius=400),
    Location(name="Norway", lat=61.02041, lon=8.784942, radius=500),
    Location(name="New Zealand", lat=-42.288765, lon=173.190186, radius=300),
]


class EventbriteService:

    def fetch_events(self, delta_days: int) -> list[dict[str, Any]]:
        logging.info("Fetching Eventbrite Events")
        page = 1
        has_next_page = True
        events = []
        token = secrets.token_bytes(16).hex()
        page_count = -1

        while has_next_page and page < EB_THRESHOLD:
            logging.info(f"EB Request start {page=} of {page_count=}")
            has_next_page, data = self._fetch_page(delta_days, page=page, token=token)
            if data:
                events += data['events']['results']
                page_count = data['events']['pagination']['page_count']
                has_next_page = page_count > page
                page += 1

        logging.info("Finished fetching EB events")
        return events

    def _fetch_page(self, delta_days: int, page: int, token: str) -> tuple[bool, Any]:
        try:
            response = requests.post(
                EVENTBRITE_URL,
                cookies=self.get_cookies(token),
                headers=self.get_headers(token),
                json=self.get_json(page=page, delta_days=delta_days),
            )
            response.raise_for_status()
            data = response.json()
            return True, data
        except Exception as exc:
            logging.info(f"[FAILED] EB fetched {page=}")
            logging.error(exc, exc_info=True)
            raise

    def get_cookies(self, token: str) -> dict[str, str]:
        assert len(token) == 32

        return {
            'mgrefby': '',
            'G': 'v%3D2%26i%3D718c7653-5619-4d76-a12b-7860a2785be8%26a%3D1112%26s%3D838621666468c8440c5c1c82bd79e02b4c0c32dd',  # noqa: E501
            'ebEventToTrack': '',
            'eblang': 'lo%3Den_GB%26la%3Den-gb',
            'csrftoken': token,
            'django_timezone': 'Europe/Kiev',
            'location': '{%22slug%22:%22online%22%2C%22place_id%22:null%2C%22latitude%22:null%2C%22longitude%22:null%2C%22place_type%22:null%2C%22current_place%22:%22Online%22%2C%22current_place_parent%22:%22%22%2C%22is_online%22:true}',  # noqa: E501
        }

    def get_headers(self, token: str) -> dict[str, str]:
        assert len(token) == 32

        return {
            'authority': 'www.eventbrite.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,ru-RU;q=0.8,ru;q=0.7,fr;q=0.6,uk;q=0.5,ar;q=0.4,de;q=0.3',  # noqa: E501
            'content-type': 'application/json',
            'origin': 'https://www.eventbrite.com',
            'referer': 'https://www.eventbrite.com/d/online/events--tomorrow/?page=1',
            **UA_HINTS,
            'x-csrftoken': token,
            'x-requested-with': 'XMLHttpRequest',
        }

    def get_json(self, *, page: int, delta_days: int) -> dict[str, Collection[str]]:
        from_day = datetime.now().date()
        to_day = datetime.now().date() + timedelta(days=delta_days)

        return {
            'event_search': {
                'dates': 'current_future',
                'date_range': {
                    'from': from_day.isoformat(),
                    'to': to_day.isoformat(),
                },
                'dedup': True,
                'languages': ['en'],
                'page': page,
                'page_size': 20,
                'price': 'free',
                'online_events_only': True,
                'include_promoted_events_for': {
                    'interface': 'search',
                    'request_source': 'web',
                },
            },
            'expand.destination_event': [
                'primary_venue',
                'image',
                'ticket_availability',
                'saves',
                'event_sales_status',
                'primary_organizer',
                'public_collections',
            ],
            'debug_experiment_overrides': {
                'search_exp_4': 'A',
            },
        }


class MeetupService:

    def fetch_events(self, delta_days: int) -> list[dict[str, Any]]:
        logging.info("Fetching Meetup Events")
        events = []
        location_len = len(LOCATIONS)

        for count, location in enumerate(LOCATIONS, start=1):
            logging.info(f"Meetup Location start {count}/{location_len} {location=}")
            has_next_page = True
            cursor = ''
            page = 1

            while has_next_page:
                logging.info(f"Meetup Request start {location.name=} {page=}")
                has_next_page, data = self._fetch_page(delta_days, location=location, cursor=cursor)
                # logging.info(data)
                if data:
                    has_next_page = data['data']['result']['pageInfo']['hasNextPage']
                    cursor = data['data']['result']['pageInfo']['endCursor']
                    if cursor == '':
                        has_next_page = False
                    events += [event['node'] for event in data['data']['result']['edges']]
                    page += 1

        logging.info("Finished fetching Meetup events")
        seen_ids = set()
        unique_data = []

        for item in events:
            if item['id'] not in seen_ids:
                seen_ids.add(item['id'])
                unique_data.append(item)
        return unique_data

    def _fetch_page(self, delta_days: int, location: Location, cursor: str) -> tuple[bool, Any]:
        try:
            response = requests.post(
                MEETUP_URL,
                headers=self.get_headers(),
                json=self.get_json(location=location, cursor=cursor, delta_days=delta_days),
            )
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError:
                logging.info(
                    f"{self.get_json(location=location, cursor=cursor, delta_days=delta_days)}")
                raise
            data = response.json()
            return True, data
        except Exception as exc:
            logging.info(f"[FAILED] Meetup fetched {location.name=} {cursor=}")
            logging.error(exc, exc_info=True)
            raise

    def get_json(self,
                 *,
                 location: 'Location',
                 cursor: str,
                 delta_days: int) -> dict[str, Collection[str]]:
        tz = ZoneInfo('US/Eastern')
        start_date = datetime.now(tz)
        end_date = start_date + timedelta(days=delta_days)

        ret_val: dict[str, Any] = {
            'operationName': 'recommendedEventsWithSeries',
            'variables': {
                'first': MEETUP_PAGE_SIZE,
                'lat': location.lat,
                'lon': location.lon,
                'radius': location.radius,
                'startDateRange': start_date.isoformat(timespec='seconds'),
                'endDateRange': end_date.isoformat(timespec='seconds'),
                'eventType': 'ONLINE',
                'sortField': 'DATETIME',
            },
            'extensions': {
                'persistedQuery': {
                    'version': 1,
                    'sha256Hash': '415d07768f1183a2a33a4eeb477f726'
                    '9e547a28735d3dccffad73a0c1b878c92',
                },
            },
        }
        if cursor:
            ret_val['variables']['after'] = cursor
        return ret_val

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'www.meetup.com',
            'accept': '*/*',
            'accept-language': 'en-US',
            'apollographql-client-name': 'nextjs-web',
            'content-type': 'application/json',
            'origin': 'https://www.meetup.com',
            'referer': 'https://www.meetup.com/find/?eventType=online&source=EVENTS&sortField=DATETIME',  # noqa: E501
            **UA_HINTS,
            'x-meetup-view-id': 'efea661b-5526-4445-855e-e24425510b83',
        }


class ConfTechService:
    """
        https://confs.tech/

        Use algolia as backend.
        POST {Application-ID}.algolia.net/1/indexes/*/queries?GET_PARAMS
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Conf Tech Events")
        response = requests.post(
            f"{CONF_TECH_URL}?{self.get_query()}",
            headers=self.get_headers(),
            data=self.get_data(),
        )
        data = response.json()
        return data['results'][0]['hits']

    def get_query(self) -> str:
        get_params = {
            'x-algolia-agent': [(
                'Algolia for JavaScript (4.18.0); Browser (lite); JS Helper (3.13.3); '
                'react (17.0.2); react-instantsearch (6.40.1)'
            )],
            'x-algolia-api-key': ['f2534ea79a28d8469f4e81d546297d39'],
            'x-algolia-application-id': ['29FLVJV5X9'],
        }
        return urlencode(get_params, doseq=True)

    def get_headers(self) -> dict[str, str]:
        return {
            'Accept': '*/*',
            'Accept-Language': 'en-US,en',
            'Connection': 'keep-alive',
            'Origin': 'https://confs.tech',
            'Referer': 'https://confs.tech/',
            'content-type': 'application/x-www-form-urlencoded',
            **UA_HINTS,
        }

    def get_data(self) -> str:
        return (
            '{"requests":[{"indexName":"prod_conferences","params":"facetFilters=%5B%5B%22topics%3Adevops%22%5D%5D&facets=%5B%22topics%22%2C%22continent%22%2C%22country%22%2C%22offersSignLanguageOrCC%22%5D'  # noqa: E501
            f'&filters=startDateUnix%3E{time.time()}'
            '&highlightPostTag=%3C%2Fais-highlight-0000000000%3E&highlightPreTag=%3Cais-highlight-0000000000%3E&hitsPerPage=600&maxValuesPerFacet=100&page=0&query=&tagFilters="}]}'  # noqa: E501
        )


class GDGService:
    """
        https://gdg.community.dev/events/#/calendar
        https://gdg.community.dev/api/event/?QUERY_PARAMS
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching GDG Events")
        start_date = datetime.now() - timedelta(days=31)
        end_date = datetime.now() + timedelta(days=31)
        params = {
            "fields": (
                "id,chapter,event_type,event_type_title,title,status,"
                "start_date,end_date,start_date_naive,end_date_naive,url"
            ),
            "start_date": start_date.strftime('%Y-%m-%d'),
            "end_date": end_date.strftime('%Y-%m-%d'),
        }
        response = requests.get(GDG_URL, params=params)
        return [
            item
            for item in response.json()['results']
            if datetime.fromisoformat(item["end_date"]).date() >= datetime.now(timezone.utc).date()
        ]

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'gdg.community.dev',
            'accept': 'application/json; version=bevy.1.0',
            'accept-language': 'en',
            'content-type': 'application/json',
            'referer': 'https://gdg.community.dev/events/',
            **UA_HINTS,
        }


class C2CGlobalService:
    """
        https://events.c2cglobal.com/events/#/list
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching C2C Global Events")
        params = {
            'result_types': 'upcoming_event',
            'country_code': 'Earth',
        }
        response = requests.get(C2CGLOBAL_URL, params=params, headers=self.get_headers())
        return response.json()['results']

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'events.c2cglobal.com',
            'accept': 'application/json; version=bevy.1.0',
            'accept-language': 'en',
            'content-type': 'application/json',
            'referer': 'https://events.c2cglobal.com/events/',
            **UA_HINTS,
        }


class DatabricksService:
    """
        https://www.databricks.com/events
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Databricks Events")
        response = requests.get(DATABRICKS_URL, headers=self.get_headers())
        data = response.json()
        events = jmespath.search('result.pageContext.globalContext.eventsData.eventsEN', data)
        filtred_events = self.filter_events(events)
        return filtred_events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'www.databricks.com',
            **ACCEPT_HEADERS,
            'referer': 'https://www.databricks.com/events',
            **UA_HINTS,
        }

    def filter_events(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        current_utc_time = datetime.utcnow().date()

        def is_upcoming(event):
            dateTimeData = event.get('fieldDateTimeTimezone', [])

            if (
                not dateTimeData
                or 'startDate' not in dateTimeData[0]
                or 'timezone' not in dateTimeData[0]
            ):
                return False

            start_date_str = dateTimeData[0]['startDate']
            timezone_str = dateTimeData[0]['timezone']

            start_date = datetime.strptime(start_date_str, "%Y-%m-%d %H:%M:%S %Z")
            event_utc_time = start_date.astimezone(pytz.timezone(timezone_str)).astimezone(pytz.utc)
            event_utc_date = event_utc_time.date()
            return event_utc_date >= current_utc_time

        return list(filter(is_upcoming, events))


class DatastaxService:
    """
        https://www.datastax.com/ko/events?mode=calendar
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Datastax Events")
        today = datetime.today()
        params = {
            "$search": '""',
            "$from": '"' + today.strftime('%Y-%m-%d') + '"',
            "$to": '"' + (today + timedelta(days=30)).strftime('%Y-%m-%d') + '"',
            "$start": '0',
            "$end": '24',
        }
        url = DATASTAX_URL + '?query=%0A%20%20%7B%0A%20%20%20%20%22results%22%3A%20*%5B_type%20%3D%3D%20%22event%22%20%26%26%20contentHidden%20!%3D%20true%20%26%26%20!(_id%20in%20path(%22drafts.**%22))%20%26%26%20count((dates%5B%5D.date)%5B%40%20%3E%3D%20%24from%20%26%26%20%40%20%3C%3D%20%24to%5D)%20%3E%200%20%20%5D%20%7C%20order(dates%5B0%5D.date%20asc)%20%20%7B%0A%20%20%20%20%20%20%0Aattendance-%3E%2C%0Adates%2C%0Aintro%2C%0Atitle%2C%0Atype-%3E%2C%0A%22slug%22%3A%20seo.slug.current%2C%0A%0A%20%20%20%20%7D%2C%0A%20%20%20%20%22count%22%3A%20count(*%5B_type%20%3D%3D%20%22event%22%20%26%26%20contentHidden%20!%3D%20true%20%26%26%20!(_id%20in%20path(%22drafts.**%22))%20%26%26%20count((dates%5B%5D.date)%5B%40%20%3E%3D%20%24from%20%26%26%20%40%20%3C%3D%20%24to%5D)%20%3E%200%20%20%5D)%2C%0A%20%20%20%20%22filters%22%3A%20%7B%0A%20%20%20%20%20%20%22attendance%22%3A%20*%5B_type%20%3D%3D%20%22event.attendance%22%5D%20%7B%0A%20%20%20%20%20%20%20%20_id%2C%0A%20%20%20%20%20%20%20%20name%2C%0A%20%20%20%20%20%20%20%20%22count%22%3A%20count(*%5B_type%20%3D%3D%20%22event%22%20%26%26%20contentHidden%20!%3D%20true%20%26%26%20!(_id%20in%20path(%22drafts.**%22))%20%26%26%20count((dates%5B%5D.date)%5B%40%20%3E%3D%20%24from%20%26%26%20%40%20%3C%3D%20%24to%5D)%20%3E%200%20%26%26%20references(%5E._id)%20%26%26%20true%5D)%2C%0A%20%20%20%20%20%20%7D%20%7C%20order(name%20asc)%20%5Bcount%20%3E%200%5D%2C%0A%20%20%20%20%20%20%22audience%22%3A%20*%5B_type%20%3D%3D%20%22event.audience%22%5D%20%7B%0A%20%20%20%20%20%20%20%20_id%2C%0A%20%20%20%20%20%20%20%20name%2C%0A%20%20%20%20%20%20%20%20%22count%22%3A%20count(*%5B_type%20%3D%3D%20%22event%22%20%26%26%20contentHidden%20!%3D%20true%20%26%26%20!(_id%20in%20path(%22drafts.**%22))%20%26%26%20count((dates%5B%5D.date)%5B%40%20%3E%3D%20%24from%20%26%26%20%40%20%3C%3D%20%24to%5D)%20%3E%200%20%26%26%20references(%5E._id)%20%26%26%20true%5D)%2C%0A%20%20%20%20%20%20%7D%20%7C%20order(name%20asc)%20%5Bcount%20%3E%200%5D%2C%0A%20%20%20%20%20%20%22industry%22%3A%20*%5B_type%20%3D%3D%20%22event.industry%22%5D%20%7B%0A%20%20%20%20%20%20%20%20_id%2C%0A%20%20%20%20%20%20%20%20name%2C%0A%20%20%20%20%20%20%20%20%22count%22%3A%20count(*%5B_type%20%3D%3D%20%22event%22%20%26%26%20contentHidden%20!%3D%20true%20%26%26%20!(_id%20in%20path(%22drafts.**%22))%20%26%26%20count((dates%5B%5D.date)%5B%40%20%3E%3D%20%24from%20%26%26%20%40%20%3C%3D%20%24to%5D)%20%3E%200%20%26%26%20references(%5E._id)%20%26%26%20true%5D)%2C%0A%20%20%20%20%20%20%7D%20%7C%20order(name%20asc)%20%5Bcount%20%3E%200%5D%2C%0A%20%20%20%20%20%20%22region%22%3A%20*%5B_type%20%3D%3D%20%22event.region%22%5D%20%7B%0A%20%20%20%20%20%20%20%20_id%2C%0A%20%20%20%20%20%20%20%20name%2C%0A%20%20%20%20%20%20%20%20%22count%22%3A%20count(*%5B_type%20%3D%3D%20%22event%22%20%26%26%20contentHidden%20!%3D%20true%20%26%26%20!(_id%20in%20path(%22drafts.**%22))%20%26%26%20count((dates%5B%5D.date)%5B%40%20%3E%3D%20%24from%20%26%26%20%40%20%3C%3D%20%24to%5D)%20%3E%200%20%26%26%20references(%5E._id)%20%26%26%20true%5D)%2C%0A%20%20%20%20%20%20%7D%20%7C%20order(name%20asc)%20%5Bcount%20%3E%200%5D%2C%0A%20%20%20%20%20%20%22type%22%3A%20*%5B_type%20%3D%3D%20%22event.type%22%5D%20%7B%0A%20%20%20%20%20%20%20%20_id%2C%0A%20%20%20%20%20%20%20%20name%2C%0A%20%20%20%20%20%20%20%20%22count%22%3A%20count(*%5B_type%20%3D%3D%20%22event%22%20%26%26%20contentHidden%20!%3D%20true%20%26%26%20!(_id%20in%20path(%22drafts.**%22))%20%26%26%20count((dates%5B%5D.date)%5B%40%20%3E%3D%20%24from%20%26%26%20%40%20%3C%3D%20%24to%5D)%20%3E%200%20%26%26%20references(%5E._id)%20%26%26%20true%5D)%2C%0A%20%20%20%20%20%20%7D%20%7C%20order(name%20asc)%20%5Bcount%20%3E%200%5D%2C%0A%20%20%20%20%7D%2C%0A%20%20%7D%0A%20%20'  # noqa: E501
        response = requests.get(url, params=params, headers=self.get_headers())
        data = response.json()
        events = data['result']['results']
        for i in range(len(events)):
            events[i]["event_url"] = "https://www.datastax.com/ko/" + events[i]["slug"]
        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'bbnkhnhl.apicdn.sanity.io',
            **ACCEPT_HEADERS,
            'accept': 'application/json',
            'origin': 'https://www.datastax.com',
            'referer': 'https://www.datastax.com/',
            **UA_HINTS,
        }


class ScalaLangService:
    """
        https://www.scala-lang.org/events/
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Scala Lang Events")
        response = requests.get(SCALA_LANG_URL, headers=self.get_headers())
        soup = BeautifulSoup(response.text, 'html.parser')

        events = []
        for el in soup.select('a.training-item'):
            start_end_str = (el
                             .select_one('div.training-text p:nth-of-type(2)')
                             .get_text(strip=True)
                             )

            start, _, end = start_end_str.partition(' - ')

            start_iso = datetime.strptime(start, "%d %B %Y").isoformat()
            end_iso = None
            if end:
                end_iso = datetime.strptime(end, "%d %B %Y").isoformat()

            events.append({
                'id': str(uuid.uuid4()),
                'event_url': el.get('href'),
                'title': el.select_one('h4').get_text(strip=True),
                'start_time': start_iso,
                'end_time': end_iso,
            })
        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'www.scala-lang.org',
            **ACCEPT_HEADERS,
            'cache-control': 'max-age=0',
            'referer': 'https://www.google.com/',
            **UA_HINTS,
        }


class CassandraService:
    """
        https://cassandra.apache.org/_/events.html
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Cassandra Events")
        response = requests.get(CASSANDRA_URL, headers=self.get_headers())
        soup = BeautifulSoup(response.text, 'html.parser')

        events = []
        for el in soup.select('div#all-tiles .openblock.card'):
            start_end_str = el.select_one('h4').get_text(strip=True)
            start_iso, end_iso = self.parse_date(start_end_str)

            events.append({
                'id': str(uuid.uuid4()),
                'event_url': el.select_one('.card-btn a').get('href'),
                'title': el.select_one('h3').get_text(strip=True),
                'start_time': start_iso,
                'end_time': end_iso,
            })

        filtred_events = self.filter_events(events)
        return filtred_events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'cassandra.apache.org',
            **ACCEPT_HEADERS,
            'cache-control': 'max-age=0',
            'referer': 'https://www.google.com/',
            **UA_HINTS,
        }

    def parse_date(self, start_end_str):
        """
            values: 'December 12-13, 2023' or 'March 14, 2023'
        """
        date_format = "%B %d, %Y"
        if "-" in start_end_str:
            start_str, end_str = start_end_str.split("-")
            start_str = start_str.strip()
            end_str = end_str.strip()

            # Extract year from start_str or end_str
            year_match = re.search(r'\d{4}', start_end_str)
            year = year_match.group(0) if year_match else None

            # Ensure year is present in start_str and end_str
            if year not in start_str:
                start_str += ", " + year
            if not re.search(r'[a-zA-Z]', end_str):
                # If month is absent in end_str, prepend it from start_str
                end_str = start_str.split(" ")[0] + " " + end_str
            if year not in end_str:
                end_str += ", " + year

            start_iso = datetime.strptime(start_str, date_format).isoformat()
            end_iso = datetime.strptime(end_str, date_format).isoformat()
        else:
            start_iso = end_iso = datetime.strptime(start_end_str.strip(), date_format).isoformat()
        return start_iso, end_iso

    def filter_events(self, events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        current_utc_time = datetime.utcnow().date()

        def is_upcoming(event):
            end_date = datetime.fromisoformat(event['end_time'])
            event_date = end_date.date()
            return event_date >= current_utc_time

        return list(filter(is_upcoming, events))


class LinuxFoundationService:
    """
        https://events.linuxfoundation.org/about/calendar/
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Linux Foundation Events")
        url = LINUX_FOUNDATION_URL + '?sfid=138&sf_action=get_data&sf_data=all&lang=en'
        response = requests.get(url, headers=self.get_headers())
        html_text = response.json()['results']
        soup = BeautifulSoup(html_text, 'html.parser')

        events = []
        for el in soup.select('article'):
            start_end_str = el.select_one('span.date').get_text()
            start_iso, end_iso = self.parse_date(start_end_str)
            events.append({
                'id': el.get('id'),
                'title': el.select_one('h5').get_text(strip=True),
                'event_url': el.select_one('h5 a')['href'],
                'start_time': start_iso,
                'end_time': end_iso,
            })
        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'cassandra.apache.org',
            **ACCEPT_HEADERS,
            'cache-control': 'max-age=0',
            'referer': 'https://www.google.com/',
            **UA_HINTS,
        }

    def parse_date(self, date_str):
        """
            Values:
            ' Oct 16–17, 2023 '
            'Nov 6, 2023'
            'Apr 29–May 1, 2024'
        """
        parts = date_str.strip().split('–')

        if len(parts) == 1:
            # Single date
            start_iso = end_iso = parser.parse(parts[0]).isoformat()
        else:
            first_part = parts[0].strip()
            second_part = parts[1].strip()

            month = first_part.split()[0]
            year = second_part.split()[-1]

            if not re.search('[a-zA-Z]', second_part):
                # Same month range (e.g., Oct 16–17, 2023)
                second_part = f"{month} {second_part}"

            first_part = f"{first_part} {year}"

            start_iso = parser.parse(first_part).isoformat()
            end_iso = parser.parse(second_part).isoformat()

        return start_iso, end_iso


class WeaviateService:
    """
        https://weaviate.io/events
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Weavite Events")

        params = {
            'page': 'https://weaviate.io/events',
            'w': '01a3e7d9-f320-4491-a464-8339fafe3e80',
        }
        response = requests.get(WEAVIATE_URL, params=params, headers=self.get_headers())
        data = response.json()

        events = jmespath.search('data.widgets | values(@) | [0].data.settings.events', data)
        today = datetime.now()
        upcomming_events = [
            event
            for event in events
            if datetime.strptime(event['end']['date'], "%Y-%m-%d") >= today
        ]

        return upcomming_events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'core.service.elfsight.com',
            **ACCEPT_HEADERS,
            'origin': 'https://weaviate.io',
            'referer': 'https://weaviate.io/',
            **UA_HINTS,
        }


class RedisService:
    """
        https://redis.com/events-and-webinars/
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Redis Events")

        data = {
            'wpx_api': 'archive',
            'wpx_paging': '1',
            'wpx_cpt': 'wpx-webinars-od',
            'wpx_loop': 'webinar',
            'wpx_language': 'en',
            'wpx_count': '21',
        }
        # Pagination stops when no events with date
        has_next = True
        page = 1
        events = []

        while has_next:
            data['wpx_paging'] = str(page)
            response = requests.post(REDIS_URL, headers=self.get_headers(), data=data)
            soup = BeautifulSoup(response.text, 'html.parser')

            for el in soup.select('div.events-item'):
                start_str = el.select_one('span.tableau-result-date').get_text(strip=True)
                try:
                    start_iso = parser.parse(start_str).isoformat()
                except parser.ParserError:
                    has_next = False
                    break

                events.append({
                    'id': str(uuid.uuid4()),
                    'event_url': el.select_one('a').get('href'),
                    'title': el.select_one('p.tableau-result-desc').get_text(strip=True),
                    'start_time': start_iso,
                })
            page += 1

        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'redis.com',
            **ACCEPT_HEADERS,
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://redis.com',
            'referer': 'https://redis.com/events-and-webinars/',
            **UA_HINTS,
        }


class PostgresService:
    """
        https://www.postgresql.org/about/events/
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Postgres Events")
        response = requests.get(POSTGRES_URL, headers=self.get_headers())
        soup = BeautifulSoup(response.text, 'html.parser')

        events = []
        for el_hr in soup.select('hr.eventseparator'):
            title_div, date_div = el_hr.find_next_siblings('div', limit=2)

            start_str, _, end_str = date_div.select_one('strong')\
                .get_text(strip=True)\
                .partition(' – ')

            # Start date should always exists.
            start_iso = parser.parse(start_str).isoformat()
            end_iso = None
            if end_str:
                end_iso = parser.parse(end_str).isoformat()

            events.append({
                'id': str(uuid.uuid4()),
                'title': title_div.select_one('a').get_text(strip=True),
                'event_url': title_div.select_one('a').get('href'),
                'start_time': start_iso,
                'end_time': end_iso,
            })
        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'www.postgresql.org',
            **ACCEPT_HEADERS,
            'cache-control': 'max-age=0',
            'referer': 'https://www.google.com/',
            **UA_HINTS,
        }


class HopsworksService:
    """
        https://www.hopsworks.ai/events
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Hopsworks Events")
        response = requests.get(HOPSWORKS_URL, headers=self.get_headers())
        soup = BeautifulSoup(response.text, 'html.parser')

        events = []
        for el in soup.select('div[data-w-tab="Tab 1"] .w-dyn-list .w-dyn-item'):
            date_els = (el
                        .select_one('.event_details')
                        .select('.event_date:not(.w-condition-invisible)')
                        )
            date_str = date_els[0].get_text(strip=True)
            start_end_time_str = date_els[1].select_one('div').get_text(strip=True)
            tz = date_els[1].select('div')[1].get_text(strip=True)

            start_str, _, end_str = start_end_time_str.partition(' // ')
            if end_str:
                end_str = date_str + ' ' + end_str + ' ' + tz
            start_str = date_str + ' ' + start_str + ' ' + tz

            start_iso = parser.parse(
                start_str,
                fuzzy=True,
                tzinfos={tz: int(whois_timezone_info[tz])},
            ).isoformat()

            end_iso = None
            if end_str:
                end_iso = parser.parse(
                    end_str,
                    fuzzy=True,
                    tzinfos={tz: int(whois_timezone_info[tz])},
                ).isoformat()

            events.append({
                'id': str(uuid.uuid4()),
                'title': el.select_one('.type-div').get_text(strip=True),
                'event_url': "https://www.hopsworks.ai" + el.select_one('a').get('href'),
                'start_time': start_iso,
                'end_time': end_iso,
            })

        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'www.hopsworks.ai',
            **ACCEPT_HEADERS,
            'cache-control': 'max-age=0',
            'referer': 'https://www.google.com/',
            **UA_HINTS,
        }


class PythonService:
    """
        https://www.python.org/events/
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Python Events")
        response = requests.get(PYTHON_URL, headers=self.get_headers())
        soup = BeautifulSoup(response.text, 'html.parser')

        events = []
        for el in soup.select('.list-recent-events li'):
            start_str = el.select_one('time').get('datetime')
            start_iso = parser.parse(start_str).isoformat()
            events.append({
                'id': str(uuid.uuid4()),
                'title': el.select_one('h3').get_text(strip=True),
                'event_url': "https://www.python.org" + el.select_one('a').get('href'),
                'start_time': start_iso,
            })

        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'www.python.org',
            **ACCEPT_HEADERS,
            'cache-control': 'max-age=0',
            'referer': 'https://www.google.com/',
            **UA_HINTS,
        }


class EventycoService:
    """
        https://www.eventyco.com/events/conferences/tech~scala~elixir~data~devops~sre~security~rust~kafka~golang
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Eventyco Events")

        events = []
        names = set()
        has_next = True
        page = 1
        date_threshold = datetime.now() + timedelta(days=10)

        while has_next:
            url = EVENTYCO_URL + f'~{page}'
            response = requests.get(url, headers=self.get_headers())
            soup = BeautifulSoup(response.text, 'html.parser')

            for ld_script in soup.select('script[type="application/ld+json"]'):
                data = json.loads(ld_script.text)

                name = data['name']
                if name in names:
                    continue
                names.add(name)

                start_date_str = data['startDate']
                start_date = parser.parse(start_date_str)
                if start_date > date_threshold:
                    has_next = False
                    break

                events.append({
                    'id': str(uuid.uuid4()),
                    'title': name,
                    'event_url': data['organizer']['url'],
                    'start_time': start_date_str,
                    'end_time': data['endDate'],
                })

            page += 1

        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'www.eventyco.com',
            **ACCEPT_HEADERS,
            'cache-control': 'max-age=0',
            **UA_HINTS,
        }


class DbtService:
    """
        https://www.getdbt.com/events
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching dbt Events")
        response = requests.get(DBT_URL, headers=self.get_headers())
        soup = BeautifulSoup(response.text, 'html.parser')

        events = []
        for el in soup.select('#all-posts-container article'):
            title = el['data-title']
            date_el = el.select_one('.blog-posts__card-content span.d-block')
            if date_el is None:
                # Featured with no date
                continue

            date_str = date_el.get_text(strip=True).split(' - ')[0]
            date_iso = parser.parse(date_str).isoformat()
            events.append({
                'id': str(uuid.uuid4()),
                'title': title,
                'event_url': el.select_one('a')['href'],
                'start_time': date_iso,
            })

        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'www.getdbt.com',
            **ACCEPT_HEADERS,
            'cache-control': 'max-age=0',
            **UA_HINTS,
        }


class DevEventsService:
    """
        https://dev.events/
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching DevEvents Events")

        events = []
        has_next = True
        date_threshold = datetime.now().date() + timedelta(days=10)
        page = 1
        last_date = None

        # TODO: parse ld instead of html
        while has_next:
            response = requests.get(DEV_EVENTS_URL + f"?page={page}", headers=self.get_headers())
            soup = BeautifulSoup(response.text, 'html.parser')

            for el in soup.select("#events .row.columns:not(.featured)"):
                if el.select_one("nav") is not None:
                    continue
                range_date_str = str(el.select_one("time").find(text=True, recursive=False))
                title = el.select_one("h2.title").get_text(strip=True)

                start_datetime = end_datetime = None
                year = datetime.now().year
                if '-' in range_date_str:
                    start_str, _, end_str = range_date_str.partition('-')
                    start_month = start_str.split()[0]

                    start_datetime = parser.parse(start_str + f' {year}')
                    if end_str[0].isdigit():
                        end_datetime = parser.parse(f'{start_month} {end_str} {year}')
                    else:
                        end_datetime = parser.parse(end_str + f' {year}')
                else:
                    start_datetime = parser.parse(range_date_str + f' {year}')

                last_date = start_datetime.date()
                if start_datetime.date() > date_threshold:
                    break

                start_iso = start_datetime.isoformat()
                end_iso = None
                if end_datetime:
                    end_iso = end_datetime.isoformat()

                events.append({
                    'id': str(uuid.uuid4()),
                    'title': title,
                    'event_url': 'https://dev.events/' + el.select_one('h2.title a')['href'],
                    'start_time': start_iso,
                    'end_time': end_iso,
                })

            # TODO: handle the last page
            # it is very unlikely we will reach last page earlier than date threshold
            if last_date is None or last_date > date_threshold:
                has_next = False
            page += 1

        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'Accept': '*/*',
            'Referer': 'https://dev.events/',
            **UA_HINTS,
        }


class TechCrunchService:
    """
        https://techcrunch.com/events/
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching DevEvents Events")

        events = []
        params = {
            '_embed': 'true',
            'upcoming': 'true',
            'parent': '0',
            'cachePrevention': '0',
        }
        response = requests.get(TECH_CRUNCH_URL, params=params, headers=self.get_headers())
        data = response.json()
        for event in data:
            start_iso = parser.parse(event['dates']['begin']).isoformat()
            end_iso = parser.parse(event['dates']['end']).isoformat()

            events.append({
                'id': event['id'],
                'title': event['title']['rendered'],
                'event_url': event['link'],
                'start_time': start_iso,
                'end_time': end_iso,
            })

        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'techcrunch.com',
            **ACCEPT_HEADERS,
            'content-type': 'application/json; charset=utf-8',
            'referer': 'https://techcrunch.com/events/',
            **UA_HINTS,
        }


class TechMemeService:
    """
        https://www.techmeme.com/events
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching TechMeme Events")
        response = requests.get(TECH_MEME_URL, headers=self.get_headers())
        soup = BeautifulSoup(response.text, 'html.parser')

        date_threshold = datetime.now() + timedelta(days=30)
        events = []

        for el in soup.select('#events div.rhov'):
            divs = el.select('div')[:2]
            range_date_str = divs[0].get_text(strip=True)
            title = divs[1].get_text(strip=True)
            if title.startswith("Earnings: "):
                continue

            start_datetime = end_datetime = None
            year = datetime.now().year
            if '-' in range_date_str:
                start_str, _, end_str = range_date_str.partition('-')
                start_month = start_str.split()[0]

                start_datetime = parser.parse(start_str + f' {year}')
                if end_str[0].isdigit():
                    end_datetime = parser.parse(f'{start_month} {end_str} {year}')
                else:
                    end_datetime = parser.parse(end_str + f' {year}')
            else:
                start_datetime = parser.parse(range_date_str + f' {year}')

            if start_datetime > date_threshold:
                break

            start_iso = start_datetime.isoformat()
            end_iso = None
            if end_datetime:
                end_iso = end_datetime.isoformat()
            events.append({
                'id': str(uuid.uuid4()),
                'title': title,
                'event_url': 'https://www.techmeme.com' + el.select_one('a')['href'],
                'start_time': start_iso,
                'end_time': end_iso,
            })

        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'www.getdbt.com',
            **ACCEPT_HEADERS,
            'cache-control': 'max-age=0',
            **UA_HINTS,
        }


class BloombergService:
    """
        https://www.bloomberglive.com/calendar/
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Bloomberg Events")
        response = requests.get(BLOOMBERG_URL, headers=self.get_headers())
        soup = BeautifulSoup(response.text, 'html.parser')

        events = []
        date_threshold = datetime.now() + timedelta(days=30)

        for el in soup.select('main .grid-fullscreen article'):
            a_el = el.select_one('a')
            title = a_el.select_one('h2').get_text(strip=True)
            start_datetime = parser.parse(a_el['data-eventdate'])

            if start_datetime > date_threshold:
                break
            start_iso = start_datetime.isoformat()

            events.append({
                'id': str(uuid.uuid4()),
                'title': title,
                'event_url': a_el['href'],
                'start_time': start_iso,
            })

        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'www.bloomberglive.com',
            **ACCEPT_HEADERS,
            'cache-control': 'max-age=0',
            **UA_HINTS,
        }


class CloudnairGoogleService:
    """
        https://cloudonair.withgoogle.com/
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Cloudnair Google Events")
        response = requests.get(CLOUDNAIR_GOOGLE_URL, headers=self.get_headers())
        data = response.json()
        events = data['events']
        for e in events:
            e['event_url'] = 'https://cloudonair.withgoogle.com/events/' + e['url_slug']
        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'cloudonair.withgoogle.com',
            **ACCEPT_HEADERS,
            'cache-control': 'max-age=0',
            **UA_HINTS,
        }


class CohereService:
    """
        https://cohere.com/events
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Cohere Events")
        response = requests.get(COHERE_URL, headers=self.get_headers())
        soup = BeautifulSoup(response.text, 'html.parser')

        script = soup.select_one('#__NEXT_DATA__').text
        data = parse_js_object(script)

        events = data['props']['pageProps']['eventsList']
        for e in events:
            e['event_url'] = 'https://cohere.com/events/' + e['slug']['current']

        return events

    def get_headers(self) -> dict[str, str]:
        return {
            'authority': 'cohere.com',
            **ACCEPT_HEADERS,
            'cache-control': 'max-age=0',
            **UA_HINTS,
        }


class SamsungService:
    """
        https://www.samsung.com/global/ir/ir-events-presentations/events/
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Samsung Events")
        response = requests.get(SAMSUNG_URL, headers=self.get_headers())
        soup = BeautifulSoup(response.text, 'html.parser')

        events = []
        for event_el in soup.select('.ir-event-view-area .ir-event-list li'):

            range_date_text = event_el.select_one('dd').text
            start_datetime = end_datetime = None

            if '-' in range_date_text:
                start_date_text, _, end_date_text = range_date_text.partition('-')
                year_partition, _, year = end_date_text.partition(',')
                start_datetime = parser.parse(start_date_text + f' {year}')
                end_datetime = parser.parse(year_partition + f' {year}')
            else:
                start_datetime = parser.parse(range_date_text)

            start_iso = start_datetime.isoformat()
            end_iso = end_datetime.isoformat() if end_datetime else None

            events.append({
                "title": event_el.select_one('dt').text,
                "event_url": SAMSUNG_URL,
                "start_time": start_iso,
                "end_time": end_iso,
            })

        return events

    def get_headers(self) -> dict[str, str]:
        return {
            **ACCEPT_HEADERS,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
            'image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'cache-control': 'max-age=0',
            **UA_HINTS,
        }


class TSMCService:
    """
        https://pr.tsmc.com/english/events/tsmc-events
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching TSMC Events")
        scraper = cloudscraper.create_scraper()
        response = scraper.get(TSMC_URL)
        soup = BeautifulSoup(response.text, 'html.parser')

        events = []
        for event_el in soup.select('.view-id-events li.item'):
            date_text = event_el.select_one('.event-date-location div').text
            start_datetime = parser.parse(date_text)

            events.append({
                "title": event_el.select_one('h3.event-title').text,
                "event_url": event_el.select_one('div.event-register a').get('href'),
                "start_time": start_datetime.isoformat(),
                "end_time": None,
            })

        return events


class NVIDIAService:
    """
        https://www.nvidia.com/en-us/events/
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching NVIDIA Events")
        ts = str(time.time()).replace('.', '')
        response = requests.get(NVIDIA_URL + f'?{ts}', headers=self.get_headers())
        data = response.json()
        dtnow = datetime.now()

        events = []
        for origin in data:
            if origin['startDate'] == 'TBC':
                continue

            start_date = parser.parse(origin['startDate'])

            end_date = None
            if 'endDate' in origin and origin['endDate'] != "":
                end_date = parser.parse(origin['endDate'])
                if end_date < dtnow:
                    continue
            elif start_date < dtnow:
                continue
            events.append({
                "title": origin['title'],
                "event_url": origin['url'],
                "start_time": start_date.isoformat(),
                "end_time": end_date.isoformat() if end_date else None,
            })
        return events

    def get_headers(self) -> dict[str, str]:
        return {
            **ACCEPT_HEADERS,
            **UA_HINTS,
            'priority': 'u=1, i',
            'referer': 'https://www.nvidia.com/en-us/events/',
            'x-queueit-ajaxpageurl': 'https%3A%2F%2Fwww.nvidia.com%2Fen-us%2Fevents%2F',
        }


class GithubService:
    """
        https://github.com/events
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Github Events")
        response = requests.get(GITHUB_URL, headers=self.get_headers())
        soup = BeautifulSoup(response.text, 'html.parser')

        events = []
        for event_el in soup.select('main ul.list-style-none.mb-4 li div.d-lg-block'):

            range_date_text = event_el.select_one('p.color-fg-muted.f5').text
            start_datetime = end_datetime = None

            if '-' in range_date_text:
                start_date_text, _, end_date_text = range_date_text.partition('-')
                start_datetime = parser.parse(start_date_text)
                end_datetime = parser.parse(end_date_text)
            else:
                start_datetime = parser.parse(range_date_text)

            events.append({
                "title": event_el.select_one('h3').text,
                "event_url": event_el.select_one('h3 a').get('href'),
                "start_time": start_datetime.isoformat(),
                "end_time": end_datetime.isoformat() if end_datetime else None,
            })

        return events

    def get_headers(self) -> dict[str, str]:
        return {
            **ACCEPT_HEADERS,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
            'image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'cache-control': 'max-age=0',
            **UA_HINTS,
        }


class SnowflakeService:
    """
        https://www.snowflake.com/about/events/
    """

    def fetch_events(self) -> list[dict[str, Any]]:
        logging.info("Fetching Snowflake Events")
        response = requests.get(SNOWFLAKE_URL, headers=self.get_headers())
        soup = BeautifulSoup(response.text, 'html.parser')

        events = []
        for event_el in soup.select('.search-filter-results .cell'):

            range_date_text = event_el.select_one('.card-header p').text
            start_datetime = end_datetime = None

            if '-' in range_date_text:
                start_date_text, _, end_date_text = range_date_text.partition('-')
                start_datetime = parser.parse(start_date_text, fuzzy=True)
                end_datetime = parser.parse(end_date_text, fuzzy=True)
            else:
                start_datetime = parser.parse(range_date_text, fuzzy=True)

            events.append({
                "title": event_el.select_one('h4').text,
                "event_url": event_el.select_one('p a.card-link').get('href'),
                "start_time": start_datetime.isoformat(),
                "end_time": end_datetime.isoformat() if end_datetime else None,
            })

        return events

    def get_headers(self) -> dict[str, str]:
        return {
            **ACCEPT_HEADERS,
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,'
            'image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'cache-control': 'max-age=0',
            **UA_HINTS,
        }
