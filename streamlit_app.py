
import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# Ramp to Station ID mapping
RAMP_TO_STATION_ID = {
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

def get_station_for_ramp(ramp_name):
    for key, station_id in RAMP_TO_STATION_ID.items():
        if key.lower() in ramp_name.lower():
            return station_id
    return "8445138"

def fetch_noaa_tides(station_id, date):
    base_url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    params = {
        "product": "predictions",
        "datum": "MLLW",
        "station": station_id,
        "time_zone": "lst_ldt",
        "units": "english",
        "interval": "hilo",
        "format": "json",
        "begin_date": date.strftime("%Y%m%d"),
        "end_date": date.strftime("%Y%m%d")
    }
    try:
        response = requests.get(base_url, params=params)
        response.raise_for_status()
        data = response.json().get("predictions", [])
        high_tides = [
            datetime.strptime(item["t"], "%Y-%m-%d %H:%M")
            for item in data if item["type"] == "H"
        ]
        return high_tides, response.url
    except Exception as e:
        return [], f"ERROR: {e}"

# Streamlit app config
st.set_page_config(page_title="ECM Scheduler with NOAA Tides", layout="centered")
st.title("🚚 ECM Boat Scheduler + NOAA Tide Integration")

# Input section
ramp_name = st.text_input("Enter Ramp Name", "Duxbury")
selected_date = st.date_input("Select Date", datetime.today())
debug_mode = st.sidebar.checkbox("Enable Tide Debug Mode")

station_id = get_station_for_ramp(ramp_name)
tides, url = fetch_noaa_tides(station_id, selected_date)

# Display debug info
if debug_mode:
    st.markdown(f"🛰️ Fetching tides for **{ramp_name}** (Station ID: `{station_id}`) on {selected_date.strftime('%Y-%m-%d')}")
    st.code(f"NOAA Request URL: {url}")
    if tides:
        st.success(f"✅ {len(tides)} high tides returned: " + ', '.join([t.strftime('%I:%M %p') for t in tides]))
    else:
        st.error("❌ No high tides returned.")

# Display calendar grid with yellow markers (single 15-min block only)
st.markdown("### ⏱ Tide-Aware Time Grid")
start_time = datetime.combine(selected_date, datetime.strptime("07:30", "%H:%M").time())
end_time = datetime.combine(selected_date, datetime.strptime("17:00", "%H:%M").time())

while start_time < end_time:
    color = "gray"
    for ht in tides:
        if abs((start_time - ht).total_seconds()) < 15 * 60:
            color = "yellow"
            break
    label = f"{start_time.strftime('%I:%M %p')} - {color}"
    st.markdown(
        f"<div style='background-color:{'gold' if color == 'yellow' else '#eee'}; padding:4px; border-radius:5px'>{label}</div>",
        unsafe_allow_html=True
    )
    start_time += timedelta(minutes=15)
