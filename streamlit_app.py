# ECM Scheduler — With 45-Day Rolling NOAA-Tide Scheduling
# Launch/Haul scheduling + tide-aware slot matching + 45-day retry loop

import streamlit as st
import pandas as pd
import requests
from datetime import datetime, timedelta

# NOAA Station ID Map
RAMP_TO_STATION_ID = {
    "Sandwich": "8446493", "Plymouth": "8446493", "Cordage": "8446493",
    "Duxbury": "8446166", "Green Harbor": "8447001", "Taylor": "8447001",
    "Safe Harbor": "8447001", "Ferry Street": "8447001", "Marshfield": "8447001",
    "South River": "8447001", "Roht": "8447001", "Mary": "8447001",
    "Scituate": "8445138", "Cohasset": "8444762", "Hull": "8444762",
    "Hingham": "8444762", "Weymouth": "8444762"
}
TRUCKS = {"S20": [], "S21": [], "S23": []}
DURATION = {"Powerboat": timedelta(hours=1.5), "Sailboat": timedelta(hours=3)}

@st.cache_data(show_spinner=False)
def get_station_for_ramp(ramp_name):
    for key, station_id in RAMP_TO_STATION_ID.items():
        if key.lower() in ramp_name.lower():
            return station_id
    return "8445138"

def fetch_noaa_tides(station_id, date):
    base_url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    params = {
        "product": "predictions", "datum": "MLLW", "station": station_id,
        "time_zone": "lst_ldt", "units": "english", "interval": "hilo",
        "format": "json", "begin_date": date.strftime("%Y%m%d"), "end_date": date.strftime("%Y%m%d")
    }
    try:
        r = requests.get(base_url, params=params)
        r.raise_for_status()
        data = r.json().get("predictions", [])
        return [datetime.strptime(d["t"], "%Y-%m-%d %H:%M") for d in data if d["type"] == "H"], r.url
    except:
        return [], "error"

def get_valid_slots(tides, start_day):
    valid = []
    start = datetime.combine(start_day, datetime.strptime("07:30", "%H:%M").time())
    end = datetime.combine(start_day, datetime.strptime("17:00", "%H:%M").time())
    while start < end:
        for tide in tides:
            if abs((start - tide).total_seconds()) < 15 * 60:
                valid.append(start)
        start += timedelta(minutes=15)
    return valid

st.set_page_config("ECM Scheduler NOAA", layout="wide")
st.title("🚛 ECM Launch/Haul Scheduler — NOAA Tide Edition")

col1, col2 = st.columns(2)
with col1:
    customer = st.text_input("Customer Name", "Matt Cooper")
    boat_type = st.selectbox("Boat Type", ["Powerboat", "Sailboat"])
    service = st.selectbox("Service Type", ["Launch", "Haul"])
with col2:
    ramp = st.selectbox("Ramp", list(RAMP_TO_STATION_ID.keys()))
    date = st.date_input("Requested Date", datetime.today())
    debug = st.checkbox("Enable Tide Debug Logs")

station_id = get_station_for_ramp(ramp)
assigned = False
fallback_logs = []

# Try today and up to 45 days out
for day_offset in range(0, 45):
    current_day = date + timedelta(days=day_offset)
    if current_day.weekday() >= 5:
        continue  # skip weekends
    tides, url = fetch_noaa_tides(station_id, current_day)
    available_slots = get_valid_slots(tides, current_day)
    for truck, jobs in TRUCKS.items():
        for slot in available_slots:
            conflict = any(slot < j[1] and slot + DURATION[boat_type] > j[0] for j in jobs)
            if not conflict:
                TRUCKS[truck].append((slot, slot + DURATION[boat_type], customer))
                st.success(f"✅ Scheduled: {customer} on {current_day.strftime('%b %d')} at {slot.strftime('%I:%M %p')} — Truck {truck}")
                assigned = True
                break
        if assigned:
            break
    if assigned:
        break
    else:
        fallback_logs.append(f"Tried {current_day.strftime('%a %b %d')} — no availability")

if not assigned:
    st.error("❌ No available dates with valid tide + truck slots in next 45 days")
    if debug:
        st.warning("Retry Attempts:")
        for log in fallback_logs:
            st.write(log)

# Show truck assignments
for truck, jobs in TRUCKS.items():
    st.markdown(f"### 🛻 Truck {truck} Schedule")
    for j in sorted(jobs):
        st.markdown(f"- {j[0].strftime('%a %b %d')} — {j[0].strftime('%I:%M %p')} → {j[1].strftime('%I:%M %p')} — {j[2]}")

    }
  ]
}
