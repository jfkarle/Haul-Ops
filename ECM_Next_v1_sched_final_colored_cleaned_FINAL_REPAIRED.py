
import streamlit as st
from datetime import datetime, timedelta

# Streamlit Calendar placeholder
st.title("ECM Scheduler – Calendar Options Test")

# Define truck colors
truck_colors = {
    "S20": "#1f77b4",  # blue
    "S21": "#ff7f0e",  # orange
    "S23": "#2ca02c",  # green
    "J17": "#d62728"   # red
}

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

# Display confirmation
st.success("Calendar options and truck colors loaded without syntax errors.")
