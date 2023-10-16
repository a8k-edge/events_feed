import multiprocessing
import os
from datetime import datetime
from typing import Final

import humanize
import pandas as pd
import pytz
import streamlit as st

from calendar_component import calendar
from fetch import DataManager, Source, main

PID_FILE: Final = 'process_id.txt'


SOURCE_COLORS = {
    Source.EVENTBRITE: "#E63946",
    Source.MEETUP: "#F28D35",
    Source.CONFTECH: "#F1FAEE",
    Source.GCD: "#A8DADC",
    Source.C2CGLOBAL: "#457B9D",
    Source.DATABRICKS: "#1D3557",
    Source.DATASTAX: "#F4A261",
    Source.SCALA_LANG: "#2A9D8F",
    Source.CASSANDRA: "#E76F51",
    Source.LINUX_FOUNDATION: "#264653",
    Source.WEAVIATE: "#2B9348",
    Source.REDIS: "#F0F3BD",
    Source.POSTGRES: "#BBBFCA",
    Source.HOPSWORKS: "#6B705C",
    Source.PYTHON: "#FFBA08",
    Source.EVENTYCO: "#FFD166",
    Source.DBT: "#EF476F",
    Source.DEV_EVENTS: "#073B4C",
    Source.TECH_CRUNCH: "#118AB2",
    Source.TECH_MEME: "#6A0572",
    Source.BLOOMBERG: "#5A189A"
}


def app() -> None:
    st.set_page_config(page_title="Events Feed", page_icon="📆", layout="wide")

    sidebar = st.sidebar
    delta_days = sidebar.number_input('Delta Days', min_value=1, value=3)
    fetch_button_clicked = sidebar.button('Fetch New Events')

    if BackgroundProcessHandler.is_running():
        sidebar.warning(
            f'A background job is currently running with PID {BackgroundProcessHandler.get_pid()}.')
    elif fetch_button_clicked:
        multiprocessing.Process(
            target=BackgroundProcessHandler.start, args=(main, (int(delta_days),)),
        ).start()
        sidebar.warning('A background job is currently')

    min_going = sidebar.number_input('Filter by minimum Going', value=10)
    selected_sources = sidebar.multiselect(
        "Select sources:",
        options=[source.value for source in Source],
        default=[],
    )

    event_manager = EventManager()
    if event_manager.data:
        df_events = event_manager.get_processed_data(selected_sources, min_going)
        df_events = df_events.rename(
            columns={
                'end_time': 'end',
                'start_time': 'start',
                'event_url': 'url',
            },
        )
        df_events = df_events[['start', 'url', 'title', 'end', 'source', 'going']]
        events = df_events.to_dict('records')

        for event in events:
            color = SOURCE_COLORS[Source(event['source'])]
            event['backgroundColor'] = color
            event['borderColor'] = color

        last_data_date = datetime.fromisoformat(
            event_manager.data['date'] if event_manager.data else '')
        time_ago = humanize.naturaltime(datetime.now() - last_data_date)
        sidebar.text(f'Date: {time_ago} ({last_data_date.strftime("%Y-%m-%d %H:%M")})')
        sidebar.text(f"{len(df_events)} Filtred events ({len(event_manager.data['events'])} Total)")

        calendar(
            events=events,
            options={"initialView": "listMonth", "height": 650},
            key=(selected_sources, min_going)
        )


class EventManager:
    def __init__(self):
        self.data = DataManager.load_latest_data()

    @staticmethod
    def _custom_format(dt):
        if pd.isna(dt):
            return ''
        return dt.isoformat()

    def _transform_data(self, df_events):
        df_events['going'] = pd.to_numeric(df_events['going'], errors='coerce', downcast='integer')
        df_events['going'] = df_events['going'].astype(
            object).where(df_events['going'].notna(), None)

        df_events['start_time'] = pd.to_datetime(
            df_events['start_time'], utc=True, infer_datetime_format=True, format='mixed')
        df_events['end_time'] = pd.to_datetime(
            df_events['end_time'], utc=True, infer_datetime_format=True, format='mixed')

        df_events['start_time'] = df_events['start_time'].dt.tz_convert(
            pytz.timezone('EET')).apply(self._custom_format)
        df_events['end_time'] = df_events['end_time'].dt.tz_convert(
            pytz.timezone('EET')).apply(self._custom_format)

        return df_events

    def get_processed_data(self, selected_sources, min_going):
        if not self.data:
            return pd.DataFrame()

        df_events = pd.DataFrame(self.data['events'])
        df_events = self._transform_data(df_events)

        if selected_sources:
            df_events = df_events[df_events['source'].isin(selected_sources)]
        df_events = df_events[df_events['going'].ge(min_going) | df_events['going'].isnull()]
        return df_events


class BackgroundProcessHandler:
    @classmethod
    def start(cls, function, args):
        with open(PID_FILE, 'w') as f:
            f.write(str(os.getpid()))

        try:
            function(*args)
        finally:
            os.remove(PID_FILE)

    @classmethod
    def is_running(cls):
        return os.path.exists(PID_FILE)

    @classmethod
    def get_pid(cls):
        with open(PID_FILE, 'r') as f:
            return int(f.read())


if __name__ == "__main__":
    app()
