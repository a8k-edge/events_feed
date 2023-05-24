import secrets
from collections.abc import Collection
from datetime import datetime
from datetime import timedelta
from typing import Any
from typing import TYPE_CHECKING
from zoneinfo import ZoneInfo

if TYPE_CHECKING:
    from main import Location


class Eventbrite:

    @staticmethod
    def generate_token() -> str:
        return secrets.token_bytes(16).hex()

    @staticmethod
    def get_cookies(token: str) -> dict[str, str]:
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

    @staticmethod
    def get_headers(token: str) -> dict[str, str]:
        assert len(token) == 32

        return {
            'authority': 'www.eventbrite.com',
            'accept': '*/*',
            'accept-language': 'en-US,en;q=0.9,ru-RU;q=0.8,ru;q=0.7,fr;q=0.6,uk;q=0.5,ar;q=0.4,de;q=0.3',  # noqa: E501
            'content-type': 'application/json',
            'origin': 'https://www.eventbrite.com',
            'referer': 'https://www.eventbrite.com/d/online/events--tomorrow/?page=1',
            'sec-ch-ua': '"Google Chrome";v="113", "Chromium";v="113", "Not-A.Brand";v="24"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/113.0.0.0 Safari/537.36',  # noqa: E501
            'x-csrftoken': token,
            'x-requested-with': 'XMLHttpRequest',
        }

    @staticmethod
    def get_json(*, page: int, delta_days: int) -> dict[str, Collection[str]]:
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


class Meetup:
    @staticmethod
    def get_json(
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
                'first': 50,
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

    @staticmethod
    def get_headers() -> dict[str, str]:
        return {
            'authority': 'www.meetup.com',
            'accept': '*/*',
            'accept-language': 'en-US',
            'apollographql-client-name': 'nextjs-web',
            'content-type': 'application/json',
            'origin': 'https://www.meetup.com',
            'referer': 'https://www.meetup.com/find/?eventType=online&source=EVENTS&sortField=DATETIME',  # noqa: E501
            'sec-ch-ua': '"Chromium";v="112", "Google Chrome";v="112", "Not:A-Brand";v="99"',  # noqa: E501
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/112.0.0.0 Safari/537.36',  # noqa: E501
            'x-meetup-view-id': 'efea661b-5526-4445-855e-e24425510b83',
        }
