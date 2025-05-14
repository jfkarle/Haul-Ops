
import streamlit as st
from streamlit_calendar import calendar

# Title
st.title("ECM Boat Hauling Calendar View")

# Define calendar options
calendar_options = {
    "initialView": "timeGridWeek",
    "editable": False,
    "selectable": False,
    "headerToolbar": {
        "left": "prev,next today",
        "center": "title",
        "right": "dayGridMonth,timeGridWeek,timeGridDay"
    },
    "slotMinTime": "07:30:00",
    "slotMaxTime": "17:30:00"
}

# Convert st.session_state["schedule"] into calendar events
calendar_events = []
for job in st.session_state.get("schedule", []):
    start_dt = f"{job['date'].date()}T{job['time'].strftime('%H:%M:%S')}"
    end_dt = (job["date"].replace(hour=job["time"].hour, minute=job["time"].minute) +
              timedelta(hours=job["duration"]))
    end_str = end_dt.strftime("%Y-%m-%dT%H:%M:%S")
    calendar_events.append({
        "title": f"{job['customer']} ({job['truck']})",
        "start": start_dt,
        "end": end_str
    })

# Render the calendar
calendar(events=calendar_events, options=calendar_options)
