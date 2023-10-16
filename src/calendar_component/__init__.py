# mypy: ignore-errors
import os

import streamlit.components.v1 as components

DEV = __name__ == '__main__'

if DEV:
    _component_func = components.declare_component(
        "calendar",
        url="http://localhost:3001",
    )
else:
    parent_dir = os.path.dirname(os.path.abspath(__file__))
    build_dir = os.path.join(parent_dir, "frontend/build")
    _component_func = components.declare_component("calendar", path=build_dir)


def calendar(
    events=[],
    options={},
    custom_css="",
    license_key="CC-Attribution-NonCommercial-NoDerivatives",
    key=None,
):
    component_value = _component_func(
        events=events,
        options=options,
        custom_css=custom_css,
        license_key=license_key,
        key=key,
        default={},
    )

    return component_value


if __name__ == '__main__':
    import streamlit as st

    st.set_page_config(page_title="Calendar")

    mode = st.selectbox(
        "Calendar Mode:",
        (
            "list",
            "daygrid",
            "timegrid",
            "timeline",
            "resource-daygrid",
            "resource-timegrid",
            "resource-timeline",
            "multimonth",
        ),
    )

    events = [{'start': '2023-10-07T12:00:00+03:00', 'url': 'https://gdg.community.dev/events/details/google-gdg-baku-presents-ml-study-jam-2023-10-07/', 'title': 'ML study Jam', 'end': '2023-10-28T14:00:00+03:00', 'source': 'GCD', 'going': 10}, {'start': '2023-10-07T22:00:00+03:00', 'url': 'https://gdg.community.dev/events/details/google-gdg-algiers-presents-open-source-week-2023-10-07/', 'title': 'Open Source Week', 'end': '2023-11-04T21:00:00+02:00', 'source': 'GCD'}, {'start': '2023-10-08T17:00:00+03:00', 'url': 'https://gdg.community.dev/events/details/google-gdg-cloud-rtp-presents-last-two-weeks-of-gen-ai-hackathon-2023-10-08/', 'title': 'Last two weeks of gen ai hackathon', 'end': '2023-10-15T18:00:00+03:00', 'source': 'GCD'}, {'start': '2023-10-13T20:00:00+03:00', 'url': 'https://gdg.community.dev/events/details/google-gdg-banjul-presents-road-to-devfest/', 'title': 'Road To Devfest', 'end': '2023-12-01T20:00:00+02:00', 'source': 'GCD'}, {'start': '2023-10-14T12:00:00+03:00', 'url': 'https://gdg.community.dev/events/details/google-gdg-bangangte-presents-devfest-bangangte-23/', 'title': 'DevFest Bangangté 23', 'end': '2023-10-15T10:46:08+03:00', 'source': 'GCD'},  # noqa: E501
              {'start': '2023-10-14T22:00:00+03:00', 'url': 'https://gdg.community.dev/events/details/google-gdg-algiers-presents-open-source-week-2023-10-14/', 'title': 'Open Source Week', 'end': '2023-11-11T21:00:00+02:00', 'source': 'GCD'}, {'start': '2023-10-15T03:00:00+03:00', 'url': 'https://www.techmeme.com/r2/2023.allthingsopen.org_-bGVYD4sB.htm', 'title': 'All Things Open', 'end': '2023-10-17T03:00:00+03:00', 'source': 'TechMeme'}, {'start': '2023-10-15T03:00:00+03:00', 'url': 'https://www.techmeme.com/r2/www.futureblockchainsummit.com_-bdTlok5E.htm', 'title': 'Future Blockchain Summit', 'end': '2023-10-18T03:00:00+03:00', 'source': 'TechMeme'}, {'start': '2023-10-15T06:30:00+03:00', 'url': 'https://gdg.community.dev/events/details/google-gdg-vizag-presents-startup-success-days-vizag/', 'title': 'Startup Success Days - Vizag', 'end': '2023-10-15T14:30:00+03:00', 'source': 'GCD'}, {'start': '2023-10-15T07:00:00+03:00', 'url': 'https://gdg.community.dev/events/details/google-gdg-tohoku-tech-dojo-akita-presents-dong-bei-techdao-chang-qiu-tian-dao-chang-di-20qi-5hui-mu/', 'title': '東北TECH道場 秋田道場 第20期 5回目', 'end': '2023-10-15T11:00:00+03:00', 'source': 'GCD'}]  # noqa: E501

    calendar_resources = [
        {"id": "a", "building": "Building A", "title": "Room A"},
        {"id": "b", "building": "Building A", "title": "Room B"},
        {"id": "c", "building": "Building B", "title": "Room C"},
        {"id": "d", "building": "Building B", "title": "Room D"},
        {"id": "e", "building": "Building C", "title": "Room E"},
        {"id": "f", "building": "Building C", "title": "Room F"},
    ]

    calendar_options = {
        "editable": "true",
        "navLinks": "true",
        "resources": calendar_resources,
    }

    if "resource" in mode:
        if mode == "resource-daygrid":
            calendar_options = {
                **calendar_options,
                "initialView": "resourceDayGridDay",
                "resourceGroupField": "building",
            }
        elif mode == "resource-timeline":
            calendar_options = {
                **calendar_options,
                "headerToolbar": {
                    "left": "today prev,next",
                    "center": "title",
                    "right": "resourceTimelineDay,resourceTimelineWeek,resourceTimelineMonth",
                },
                "initialView": "resourceTimelineDay",
                "resourceGroupField": "building",
            }
        elif mode == "resource-timegrid":
            calendar_options = {
                **calendar_options,
                "initialView": "resourceTimeGridDay",
                "resourceGroupField": "building",
            }
    else:
        if mode == "daygrid":
            calendar_options = {
                **calendar_options,
                "headerToolbar": {
                    "left": "today prev,next",
                    "center": "title",
                    "right": "dayGridDay,dayGridWeek,dayGridMonth",
                },
                "initialView": "dayGridMonth",
            }
        elif mode == "timegrid":
            calendar_options = {
                **calendar_options,
                "initialView": "timeGridWeek",
            }
        elif mode == "timeline":
            calendar_options = {
                **calendar_options,
                "headerToolbar": {
                    "left": "today prev,next",
                    "center": "title",
                    "right": "timelineDay,timelineWeek,timelineMonth",
                },
                "initialView": "timelineMonth",
            }
        elif mode == "list":
            calendar_options = {
                **calendar_options,
                "initialView": "listMonth",
            }
        elif mode == "multimonth":
            calendar_options = {
                **calendar_options,
                "initialView": "multiMonthYear",
            }

    state = calendar(
        events=st.session_state.get("events", events),
        options=calendar_options,
        custom_css="""
        .fc-event-past {
            opacity: 0.8;
        }
        .fc-event-time {
            font-style: italic;
        }
        .fc-event-title {
            font-weight: 700;
        }
        .fc-toolbar-title {
            font-size: 2rem;
        }
        """,
        key=mode,
    )
