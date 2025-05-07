# ECM Scheduler — Fresh Start with NOAA Tide Matching & Truck Assignment
import streamlit as st
import requests
from datetime import datetime, timedelta

# Ramp to Station ID map
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

def get_station_for_ramp(ramp):
    for name, sid in RAMP_TO_STATION_ID.items():
        if name.lower() in ramp.lower():
            return sid
    return "8445138"  # fallback

def fetch_noaa_high_tides(station_id, date):
    url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    params = {
        "product": "predictions", "datum": "MLLW", "station": station_id,
        "time_zone": "lst_ldt", "units": "english", "interval": "hilo",
        "format": "json", "begin_date": date.strftime("%Y%m%d"), "end_date": date.strftime("%Y%m%d")
    }
    try:
        r = requests.get(url, params=params)
        r.raise_for_status()
        data = r.json().get("predictions", [])
        return [datetime.strptime(d["t"], "%Y-%m-%d %H:%M") for d in data if d["type"] == "H"]
    except:
        return []

def find_matching_slot(tides, truck_jobs, job_length, job_date):
    base = datetime.combine(job_date, datetime.strptime("07:30", "%H:%M").time())
    end = datetime.combine(job_date, datetime.strptime("17:00", "%H:%M").time())
    while base < end:
        for tide in tides:
            if abs((base - tide).total_seconds()) < 15 * 60:
                conflict = any(base < j[1] and base + job_length > j[0] for j in truck_jobs)
                if not conflict:
                    return base
        base += timedelta(minutes=15)
    return None

st.set_page_config("ECM Scheduler", layout="wide")
st.title("🚛 ECM Scheduler — NOAA Verified")

# User form
with st.form("schedule_form"):
    col1, col2 = st.columns(2)
    with col1:
        customer = st.text_input("Customer Name")
        boat_type = st.selectbox("Boat Type", ["Powerboat", "Sailboat"])
        service = st.selectbox("Service Type", ["Launch", "Haul"])
    with col2:
        ramp = st.selectbox("Ramp", list(RAMP_TO_STATION_ID.keys()))
        start_date = st.date_input("Requested Start Date", datetime.today())
        debug = st.checkbox("Enable Tide Debug Info")
    submitted = st.form_submit_button("Schedule This Job")

if submitted:
    job_length = DURATION[boat_type]
    station_id = get_station_for_ramp(ramp)
    assigned = False
    fallback_days = []

    for offset in range(0, 45):
        day = start_date + timedelta(days=offset)
        if day.weekday() >= 5:
            continue
        tides = fetch_noaa_high_tides(station_id, day)
        for truck, jobs in TRUCKS.items():
            slot = find_matching_slot(tides, jobs, job_length, day)
            if slot:
                TRUCKS[truck].append((slot, slot + job_length, customer))
                st.success(f"✅ Scheduled for {customer} on {day.strftime('%a %b %d')} at {slot.strftime('%I:%M %p')} — Truck {truck}")
                assigned = True
                break
        if assigned:
            break
        fallback_days.append(day.strftime("%a %b %d"))

    if not assigned:
        st.error("❌ No available slot in 45-day window")
        if debug:
            st.warning("Tried the following days with no match:")
            for d in fallback_days:
                st.text(d)

# Final truck schedules
for truck, jobs in TRUCKS.items():
    st.markdown(f"### 🛻 Truck {truck} Schedule")
    for j in sorted(jobs):
        st.markdown(
            f"- {j[0].strftime('%a %b %d')} — {j[0].strftime('%I:%M %p')} → {j[1].strftime('%I:%M %p')} — {j[2]}"
        )

