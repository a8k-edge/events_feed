from datetime import datetime
from typing import Final

import humanize
import pandas as pd
import streamlit as st
from dateutil import parser
from tzlocal import get_localzone

from main import DataManager
from main import main


LOCAL_TZ: Final = get_localzone()


def app() -> None:
    st.title('Events Fetcher')

    data = DataManager.load_latest_data()

    delta_days = st.number_input(
        'Select number of days for which to fetch events (delta_days)',
        min_value=1,
        max_value=7,
        value=1,
    )

    if st.button('Fetch New Events'):
        with st.spinner('Fetching events...'):
            main(int(delta_days) or 1)
            st.success('Done fetching new events.')

    if data:
        last_data_date = datetime.fromisoformat(data['date'] if data else '')
        time_ago = humanize.naturaltime(datetime.now() - last_data_date)
        st.text(f'Latest data date: {last_data_date.strftime("%Y-%m-%d %H:%M")} ({time_ago})')
        events = data['events']
        df_events = pd.DataFrame(events)

        df_events['start_time'] = df_events['start_time'].apply(lambda x: try_parsing_date(x))
        df_events = df_events.sort_values(by='start_time')
        df_events['start_time'] = df_events['start_time'].dt.strftime('%Y-%m-%d %H:%M')

        df_events['going'] = pd.to_numeric(df_events['going'], errors='coerce', downcast='integer')
        min_going = st.number_input(
            'Filter by minimum Going',
            min_value=int(df_events['going'].min()),
            max_value=int(df_events['going'].max()),
            value=int(df_events['going'].min()),
        )
        df_events = df_events[df_events['going'].ge(min_going) | df_events['going'].isnull()]

        # target and noreferrer automatically added
        df_events['event_url'] = df_events['event_url'].apply(lambda x: f'<a href="{x}">🔗</a>')
        df_events = df_events[['title', 'start_time', 'going', 'event_url']]

        st.text(f"Total events: {len(events)}")
        st.text(f"Filtered events: {len(df_events)}")
        st.write(df_events.to_html(escape=False, index=False), unsafe_allow_html=True)


def try_parsing_date(text):
    if not text:
        return None
    return parser.parse(text).astimezone(LOCAL_TZ)


if __name__ == "__main__":
    app()
