import logging
import secrets
from collections.abc import Collection
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import Final
from typing import NamedTuple
from zoneinfo import ZoneInfo

import requests


EVENTBRITE_URL = 'https://www.eventbrite.com/api/v3/destination/search/'
MEETUP_URL = 'https://www.meetup.com/gql'
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


class EventbriteService:

    def fetch_events(self, delta_days: int) -> list[dict[str, Any]]:
        page = 1
        has_next_page = True
        events = []
        token = self.generate_token()
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

    def generate_token(self) -> str:
        return secrets.token_bytes(16).hex()

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
                if data:
                    has_next_page = data['data']['rankedEvents']['pageInfo']['hasNextPage']
                    cursor = data['data']['rankedEvents']['pageInfo']['endCursor']
                    events += [event['node'] for event in data['data']['rankedEvents']['edges']]
                    page += 1

        logging.info("Finished fetching Meetup events")
        return events

    def _fetch_page(self, delta_days: int, location: Any, cursor: str) -> tuple[bool, Any]:
        try:
            response = requests.post(
                MEETUP_URL,
                headers=self.get_headers(),
                json=self.get_json(location=location, cursor=cursor, delta_days=delta_days),
            )
            response.raise_for_status()
            data = response.json()
            return True, data
        except Exception as exc:
            logging.info(f"[FAILED] Meetup fetched {location.name=} {cursor=}")
            logging.error(exc, exc_info=True)
            raise

    def get_json(
        self,
        *,
        location: 'Location',
        cursor: str,
        delta_days: int
    ) -> dict[str, Collection[str]]:
        tz = ZoneInfo('US/Eastern')
        start_date = datetime.now(tz)
        end_date = start_date + timedelta(days=delta_days)

        ret_val: dict[str, Any] = {
            'operationName': 'categorySearch',
            'variables': {
                'first': MEETUP_PAGE_SIZE,
                'lat': location.lat,
                'lon': location.lon,
                'radius': location.radius,
                'topicCategoryId': None,
                'startDateRange': start_date.isoformat(timespec='seconds'),
                'endDateRange': end_date.isoformat(timespec='seconds'),
                'eventType': 'online',
                'sortField': 'DATETIME',
            },
            'query': 'query categorySearch($lat: Float!, $lon: Float!, $categoryId: Int, $topicCategoryId: Int, $startDateRange: ZonedDateTime, $endDateRange: ZonedDateTime, $first: Int, $after: String, $eventType: EventType, $radius: Int, $isHappeningNow: Boolean, $isStartingSoon: Boolean, $sortField: RankedEventsSortField) {\n  rankedEvents(\n    filter: {lat: $lat, lon: $lon, categoryId: $categoryId, topicCategoryId: $topicCategoryId, startDateRange: $startDateRange, endDateRange: $endDateRange, eventType: $eventType, radius: $radius, isHappeningNow: $isHappeningNow, isStartingSoon: $isStartingSoon}\n    input: {first: $first, after: $after}\n    sort: {sortField: $sortField}\n  ) {\n    pageInfo {\n      ...PageInfoDetails\n      __typename\n    }\n    count\n    edges {\n      node {\n        ...BuildMeetupEvent\n        isNewGroup\n        covidPrecautions {\n          venueType\n          __typename\n        }\n        __typename\n      }\n      recommendationId\n      recommendationSource\n      __typename\n    }\n    __typename\n  }\n}\n\nfragment PageInfoDetails on PageInfo {\n  hasNextPage\n  endCursor\n  __typename\n}\n\nfragment BuildMeetupEvent on Event {\n  id\n  title\n  dateTime\n  endTime\n  description\n  duration\n  timezone\n  eventType\n  currency\n  images {\n    ...PhotoDetails\n    __typename\n  }\n  venue {\n    id\n    address\n    neighborhood\n    city\n    state\n    country\n    lat\n    lng\n    zoom\n    name\n    radius\n    __typename\n  }\n  onlineVenue {\n    type\n    url\n    __typename\n  }\n  isSaved\n  eventUrl\n  group {\n    ...BuildMeetupGroup\n    __typename\n  }\n  going\n  maxTickets\n  tickets(input: {first: 3}) {\n    ...TicketsConnection\n    __typename\n  }\n  isAttending\n  rsvpState\n  __typename\n}\n\nfragment PhotoDetails on Image {\n  id\n  baseUrl\n  preview\n  source\n  __typename\n}\n\nfragment BuildMeetupGroup on Group {\n  id\n  slug\n  isPrivate\n  isOrganizer\n  isNewGroup\n  ...GroupDetails\n  __typename\n}\n\nfragment GroupDetails on Group {\n  id\n  name\n  urlname\n  timezone\n  link\n  city\n  state\n  country\n  groupPhoto {\n    ...PhotoDetails\n    __typename\n  }\n  __typename\n}\n\nfragment TicketsConnection on EventTicketsConnection {\n  count\n  edges {\n    node {\n      id\n      user {\n        id\n        name\n        memberPhoto {\n          ...PhotoDetails\n          __typename\n        }\n        __typename\n      }\n      __typename\n    }\n    __typename\n  }\n  __typename\n}\n',  # noqa: E501
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
