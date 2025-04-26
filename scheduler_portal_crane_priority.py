# ECM Scheduler - Full Calendar Ops Upgrade

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import os

st.set_page_config(page_title="ECM Scheduler: Crane Priority", layout="wide")

# Dark background CSS
st.markdown(
    """
    <style>
    .main {
        background-color: #1e1e1e;
        color: white;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Initialize session state variables
if "current_day" not in st.session_state:
    st.session_state.current_day = datetime.today().date()
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "Week"

# Controls for calendar navigation
col1, col2, col3 = st.columns([1,2,1])
with col1:
    if st.button("⬅️ Previous"):
        if st.session_state.view_mode == "Day":
            st.session_state.current_day -= timedelta(days=1)
        elif st.session_state.view_mode == "Week":
            st.session_state.current_day -= timedelta(days=7)
        elif st.session_state.view_mode == "Month":
            st.session_state.current_day -= timedelta(days=30)
with col2:
    st.session_state.view_mode = st.selectbox("Select View", ["Day", "Week", "Month"], index=["Day", "Week", "Month"].index(st.session_state.view_mode))
with col3:
    if st.button("Next ➡️"):
        if st.session_state.view_mode == "Day":
            st.session_state.current_day += timedelta(days=1)
        elif st.session_state.view_mode == "Week":
            st.session_state.current_day += timedelta(days=7)
        elif st.session_state.view_mode == "Month":
            st.session_state.current_day += timedelta(days=30)

# Build dynamic calendar

def build_calendar(start_date, view_mode):
    timeslots = [time(8,0), time(9,30), time(11,0), time(12,30), time(14,0)]
    trucks = ["S20", "S21", "S23", "S17"]

    if view_mode == "Day":
        days = [start_date]
    elif view_mode == "Week":
        days = [start_date + timedelta(days=i) for i in range(7)]
    elif view_mode == "Month":
        days = [start_date + timedelta(days=i) for i in range(30)]

    # MultiIndex columns: (Day, Truck)
    columns = pd.MultiIndex.from_tuples(
        [(d.strftime('%a %b %d'), truck) for d in days for truck in trucks],
        names=["Day", "Truck"]
    )

    index = [t.strftime('%-I:%M %p') for t in timeslots]
    calendar = pd.DataFrame('', index=index, columns=columns)

    truck_map = {20: "S20", 21: "S21", 23: "S23", 17: "S17"}

    # Scheduled lookup
    scheduled_lookup = {}
    for record in st.session_state.schedule_log:
        d = datetime.strptime(record["Date"], '%B %d, %Y').date()
        start_time = datetime.strptime(record["Start"], '%I:%M %p').time()
        truck = f"S{record['Truck']}"
        scheduled_lookup[(d, start_time, truck)] = f"{record['Customer']} @ {record['Ramp']}"

    for truck_num, truck_label in truck_map.items():
        for d in days:
            bookings = st.session_state.truck_bookings.get(truck_num, {}).get(d, [])
            for start, end in bookings:
                for slot_time in timeslots:
                    slot_dt = datetime.combine(d, slot_time)
                    if start <= slot_dt < end:
                        label = scheduled_lookup.get((d, slot_time, truck_label), "Scheduled")
                        calendar.at[slot_time.strftime('%-I:%M %p'), (d.strftime('%a %b %d'), truck_label)] = label

    # Proposed available slots
    if st.session_state.proposed_slots:
        for d, t in st.session_state.proposed_slots:
            if d in days:
                for truck_label in trucks:
                    col = (d.strftime('%a %b %d'), truck_label)
                    row = t.strftime('%-I:%M %p')
                    if col in calendar.columns and (calendar.at[row, col] == '' or calendar.at[row, col] == 'None'):
                        calendar.at[row, col] = "🟢"
                        break

    return calendar.style.set_properties(
        **{
            'max-width': '150px',
            'white-space': 'wrap',
            'overflow-wrap': 'break-word',
            'text-align': 'center'
        }
    )

st.markdown("### 📅 Current Schedule Overview")
cal = build_calendar(st.session_state.current_day, st.session_state.view_mode)
st.dataframe(cal)

don't forget to stick it to the man, brother! 🚀
