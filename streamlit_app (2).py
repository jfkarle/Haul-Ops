
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import requests

# Define mapping of ramps to station IDs
def get_station_for_ramp(ramp_name):
    ramp_station_map = {
        "Sandwich": "8446493",
        "Plymouth": "8446493",
        "Cordage": "8446493",
        "Duxbury": "8446166",
        "Green Harbor": "8447001",
        "Taylor": "8447001",
        "Safe Harbor": "8447001",
        "Ferry Street": "8447001",
        "Marshfield": "8447001",
        "South River": "8447001",
        "Roht": "8447001",
        "Mary": "8447001",
        "Scituate": "8445138",
        "Cohasset": "8444762",
        "Hull": "8444762",
        "Hingham": "8444762",
        "Weymouth": "8444762"
    }
    for key, station_id in ramp_station_map.items():
        if key.lower() in ramp_name.lower():
            return station_id
    return "8445138"  # default to Scituate

# Debug header to confirm deployment
st.warning("⚠️ DEBUG VERSION ACTIVE — NOAA LIVE TIDE PULL ENABLED")
st.title("Tide Scheduler Debug")

# Input ramp name and date
ramp_name = st.text_input("Enter ramp name (e.g. Duxbury, Scituate):", "Duxbury")
input_date = st.date_input("Choose date to check tide", datetime(2025, 5, 26))

def get_noaa_tides(ramp_name, date):
    station_id = get_station_for_ramp(ramp_name)
    st.markdown(f"🛰️ Fetching tides for **{ramp_name}** (Station ID: `{station_id}`) on {date.strftime('%B %d, %Y')}")

    base_url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    params = {
        "product": "predictions",
        "datum": "MLLW",
        "time_zone": "lst_ldt",
        "units": "english",
        "interval": "hilo",
        "format": "json",
        "station": station_id,
        "begin_date": date.strftime("%Y%m%d"),
        "end_date": date.strftime("%Y%m%d")
    }

    try:
        response = requests.get(base_url, params=params)
        st.code(f"NOAA Request URL: {response.url}")
        response.raise_for_status()
        tide_data = response.json().get("predictions", [])

        high_tides = [
            datetime.strptime(t['t'], "%Y-%m-%d %H:%M")
            for t in tide_data if t['type'] == 'H'
        ]
        if not high_tides:
            st.error("❌ No high tides returned from NOAA.")
        else:
            for t in high_tides:
                st.success(f"✅ High tide at: {t.strftime('%I:%M %p')}")
        return high_tides
    except Exception as e:
        st.error(f"🚨 NOAA tide fetch failed: {e}")
        return []

def display_yellow_blocks(high_tides, date):
    st.markdown("### 🟨 Tide Window Grid")
    start_time = datetime.combine(date, datetime.strptime("07:30", "%H:%M").time())
    end_time = datetime.combine(date, datetime.strptime("17:00", "%H:%M").time())

    while start_time < end_time:
        slot_center = start_time + timedelta(minutes=30)
        color = "gray"
        for ht in high_tides:
            if ht - timedelta(minutes=15) <= slot_center < ht + timedelta(minutes=45):
                color = "yellow"
                break
        label = f"{start_time.strftime('%I:%M %p')} - {color}"
        st.markdown(f"<div style='background-color:{'gold' if color=='yellow' else '#eee'};padding:4px;border-radius:5px'>{label}</div>", unsafe_allow_html=True)
        start_time += timedelta(minutes=15)

# Run it
high_tides = get_noaa_tides(ramp_name, input_date)
if high_tides:
    display_yellow_blocks(high_tides, input_date)
