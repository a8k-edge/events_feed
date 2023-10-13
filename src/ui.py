import multiprocessing
import os
from datetime import datetime
from typing import Final

import humanize
import pandas as pd
import pytz
import streamlit as st

from fetch import DataManager, Source, main

PID_FILE: Final = 'process_id.txt'


def app() -> None:
    st.title('Events')
    event_manager = EventManager()

    delta_days = st.number_input('Delta Days', min_value=1, value=1)
    event_manager.background_fetch(delta_days)
    st.divider()

    if event_manager.data:
        col1, col2, col3 = st.columns(3)
        with col1:
            sort_option = st.selectbox(
                "Sort by:",
                ["Start time (Latest first)", "Going (Largest first)"],
            )
        with col2:
            min_going = st.number_input('Filter by minimum Going', value=10)
        with col3:
            selected_sources = st.multiselect(
                "Select sources:",
                options=[source.value for source in Source],
                default=[],
            )

        df_events = event_manager.filter_and_sort_data(selected_sources, min_going, sort_option)
        df_events = event_manager.format_data(df_events)
        event_manager.display_events(df_events)


class EventManager:
    def __init__(self):
        self.data = DataManager.load_latest_data()

    def background_fetch(self, delta_days):
        if os.path.exists(PID_FILE):
            with open(PID_FILE, 'r') as f:
                pid = int(f.read())
            st.warning(f'A background job is currently running with PID {pid}.')

        if st.button('Fetch New Events'):
            with st.spinner('Fetching events...'):
                process = multiprocessing.Process(
                    target=background_fetch_wrapper, args=(int(delta_days),),
                )
                process.start()
                st.success('Started fetching new events in the background')
                self.data = None

    def filter_and_sort_data(self, selected_sources, min_going, sort_option):
        if not self.data:
            return
        df_events = pd.DataFrame(self.data['events'])
        df_events['going'] = pd.to_numeric(df_events['going'], errors='coerce', downcast='integer')
        df_events['start_time'] = pd.to_datetime(df_events['start_time'], utc=True)
        df_events['end_time'] = pd.to_datetime(df_events['end_time'], utc=True)

        if selected_sources:
            df_events = df_events[df_events['source'].isin(selected_sources)]
        df_events = df_events[df_events['going'].ge(min_going) | df_events['going'].isnull()]

        if sort_option == "Start time (Latest first)":
            df_events = df_events.sort_values(by='start_time')
        elif sort_option == "Going (Largest first)":
            df_events = df_events.sort_values(by='going', ascending=False)

        return df_events

    def format_data(self, df_events):
        now = datetime.now(pytz.timezone('EET'))

        def custom_format(dt):
            if pd.isna(dt):
                return ''

            days_difference = (dt - now).days

            if -3 <= days_difference <= 3:
                return dt.strftime('%a %H:%M')
            else:
                return dt.strftime('%b %d %H:%M')

        df_events['start_time'] = df_events['start_time'].dt\
            .tz_convert(pytz.timezone('EET'))\
            .apply(custom_format)

        df_events['end_time'] = df_events['end_time'].dt\
            .tz_convert(pytz.timezone('EET'))\
            .apply(custom_format)
        # .apply(lambda x: x.strftime(custom_format(x)))

        df_events['title'] = df_events.apply(
            lambda x: f'<div><a href="{x["event_url"]}">{x["title"]}</a></div>',
            axis=1,
        )
        return df_events

    def display_events(self, df_events):
        if not self.data:
            return
        df_events = df_events[['start_time', 'title', 'end_time', 'going', 'source']]
        df_events.set_index(['start_time', 'title'], inplace=True)
        df_events.rename_axis(index={'start_time': 'Start time', 'title': 'Title'}, inplace=True)
        df_events = df_events.rename(
            columns={
                'end_time': 'End time',
                'going': 'Going',
                'source': 'Source',
            },
        )
        styler = df_events.style.set_table_styles(
            {
                'End time': [{'selector': '', 'props': 'white-space: nowrap !important;'}],
                'Going': [{'selector': 'td', 'props': 'text-align: right;'}],
            },
            overwrite=False,
        ).format({
            'Going': lambda x: str(int(x)) if x == x else '',
        })
        styler = styler.set_table_styles([
            {
                'selector': '.level0',
                'props': 'white-space: nowrap !important; font-weight: normal;'
            },
            {
                'selector': '.level1',
                'props': 'font-weight: normal;'
            }
        ], overwrite=False)

        last_data_date = datetime.fromisoformat(self.data['date'] if self.data else '')
        time_ago = humanize.naturaltime(datetime.now() - last_data_date)
        st.text(f'Data date: {time_ago} ({last_data_date.strftime("%Y-%m-%d %H:%M")})')
        st.text(f"Displayed events (total): {len(df_events)} ({len(self.data['events'])})")
        st.write(styler.to_html(), unsafe_allow_html=True)


def background_fetch_wrapper(delta_days: int):
    with open(PID_FILE, 'w') as f:
        f.write(str(os.getpid()))

    try:
        main(delta_days)
    finally:
        os.remove(PID_FILE)


if __name__ == "__main__":
    app()
