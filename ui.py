import multiprocessing
import os
from datetime import datetime
from typing import Final

import humanize
import pandas as pd
import pytz
import streamlit as st
from tzlocal import get_localzone

from main import DataManager
from main import main


LOCAL_TZ: Final = get_localzone()
PID_FILE: Final = 'process_id.txt'


def app() -> None:
    st.title('Events')

    data = DataManager.load_latest_data()

    delta_days = st.number_input(
        'Select number of days for which to fetch events (delta_days)',
        min_value=1,
        max_value=7,
        value=1,
    )
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
            data = None

    st.divider()

    if data:
        col1, col2 = st.columns(2)
        with col1:
            sort_option = st.selectbox(
                "Sort by:",
                ["Start time (Latest first)", "Going (Largest first)"],
            )
        with col2:
            min_going = st.number_input('Filter by minimum Going', value=10)

        df_events = pd.DataFrame(data['events'])
        df_events['going'] = pd.to_numeric(df_events['going'], errors='coerce', downcast='integer')
        df_events['start_time'] = pd.to_datetime(df_events['start_time'], utc=True)
        df_events['end_time'] = pd.to_datetime(df_events['end_time'], utc=True)

        if sort_option == "Start time (Latest first)":
            df_events = df_events.sort_values(by='start_time')
        elif sort_option == "Going (Largest first)":
            df_events = df_events.sort_values(by='going', ascending=False)
        df_events = df_events[df_events['going'].ge(min_going) | df_events['going'].isnull()]

        # Format
        df_events['start_time'] = df_events['start_time'].dt.tz_convert(pytz.timezone('EET'))
        df_events['end_time'] = df_events['end_time'].dt.tz_convert(pytz.timezone('EET'))
        dt_format = '%a %H:%M'
        df_events['start_time'] = df_events['start_time'].dt.strftime(dt_format)
        df_events['end_time'] = df_events['end_time'].dt.strftime(dt_format)
        # target and noreferrer automatically added
        df_events['title'] = df_events.apply(
            lambda x: f'<div><a href="{x["event_url"]}">{x["title"]}</a></div>',
            axis=1,
        )
        df_events['source'] = df_events['source'].apply(str.title)

        # Style
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
                'index_level_0': [{'selector': '', 'props': 'white-space: nowrap !important;'}],
                'index_level_1': [{'selector': '', 'props': 'white-space: nowrap !important;'}],
                'End time': [{'selector': '', 'props': 'white-space: nowrap !important;'}],
                'Going': [{'selector': 'td', 'props': 'text-align: right;'}],
            }, overwrite=False,
        ).format({
            'Going': lambda x: str(int(x)) if x == x else 'Unknown',
        })

        # Display
        last_data_date = datetime.fromisoformat(data['date'] if data else '')
        time_ago = humanize.naturaltime(datetime.now() - last_data_date)
        st.text(f'Data date: {time_ago} ({last_data_date.strftime("%Y-%m-%d %H:%M")})')
        st.text(f"Displayed events (total): {len(df_events)} ({len(data['events'])})")
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
