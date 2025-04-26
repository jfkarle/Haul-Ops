# ECM Scheduler Patch: Manual Slot Selection Mode + Calendar View + Snap to Standard Time Blocks

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date, time
import os

st.set_page_config(page_title="ECM Scheduler: Crane Priority", layout="centered")

ramp_options = [
    "Sandwich Basin", "Plymouth Harbor", "Cordage Park (Ply)", "Duxbury Harbor",
    "Green Harbor (Taylors)", "Safe Harbor (Green Harbor)", "Ferry Street (Marshfield Yacht Club)",
    "South River Yacht Yard", "Roht (A to Z / Mary's)", "Scituate Harbor (Jericho Road)",
    "Cohasset Harbor (Parker Ave)", "Hull (A St, Sunset, Steamboat)", "Hull (X Y Z St) (Goodwin V St)",
    "Hingham Harbor", "Weymouth Harbor (Wessagusset)"
]

if "show_form" not in st.session_state:
    st.session_state.show_form = True
if "last_result" not in st.session_state:
    st.session_state.last_result = ""
if "schedule_log" not in st.session_state:
    st.session_state.schedule_log = []
if "truck_bookings" not in st.session_state:
    st.session_state.truck_bookings = {20: {}, 21: {}, 23: {}, 17: {}}
if "crane_schedule" not in st.session_state:
    st.session_state.crane_schedule = {}
if "proposed_slots" not in st.session_state:
    st.session_state.proposed_slots = []
if "pending_data" not in st.session_state:
    st.session_state.pending_data = None

tide_data = {}
for file in os.listdir():
    if file.endswith("_2025_Tide_Times.csv"):
        df = pd.read_csv(file)
        for _, row in df.iterrows():
            tide_data[(row['Harbor'], row['Date'])] = row['High Tide']

def normalize_ramp_name(ramp):
    aliases = {
        "jericho": "Scituate",
        "scituate harbor (jericho road)": "Scituate",
        "cohasset harbor (parker ave)": "Cohasset",
        "hull (a st, sunset, steamboat)": "Hull",
        "hull (x y z st) (goodwin v st)": "Hull",
        "green harbor (taylors)": "Brant Rock",
        "safe harbor (green harbor)": "Brant Rock",
        "duxbury harbor": "Duxbury",
        "cordage park (ply)": "Plymouth",
        "plymouth harbor": "Plymouth",
        "weymouth harbor (wessagusset)": "Weymouth"
    }
    return aliases.get(ramp.strip().lower(), ramp.title())

def get_high_tide(ramp, dt):
    ramp = normalize_ramp_name(ramp)
    date_str = dt.strftime("%B %-d, %Y")
    if (ramp, date_str) in tide_data:
        return tide_data[(ramp, date_str)]
    elif ("Scituate", date_str) in tide_data:
        return tide_data[("Scituate", date_str)]
    return None

def has_conflict(blocks, start, end):
    return any(s < end and e > start for s, e in blocks)

def valid_day(d):
    return d.weekday() < 5 or (d.weekday() == 5 and d.month in [5, 9])

def find_available_slots(data, max_slots=3):
    orig = pd.to_datetime(data["Requested Date"]).date()
    duration = timedelta(hours=1.5 if data["Boat Type"].lower() == "powerboat" else 3)
    requires_crane = data["Boat Type"].lower() == "sailboat"
    found_slots = []

    timeslots = [time(8,0), time(9,30), time(11,0), time(12,30), time(14,0)]

    for i in range(0, 31):
        d = orig + timedelta(days=i)
        if not valid_day(d):
            continue
        tide_str = get_high_tide(data["Destination"], d)
        if not tide_str:
            continue
        try:
            tide_time = datetime.strptime(tide_str, "%I:%M %p").time()
        except:
            continue

        truck = data["Truck"]
        ramp = data["Destination"]
        crane_locked_ramp = st.session_state.crane_schedule.get(d)

        if requires_crane and crane_locked_ramp and crane_locked_ramp != ramp:
            continue

        for slot_time in timeslots:
            cursor = datetime.combine(d, slot_time)
            tide_window_start = max(datetime.combine(d, datetime.strptime("08:00 AM", "%I:%M %p").time()),
                                    datetime.combine(d, (datetime.combine(d, tide_time) - timedelta(hours=3)).time()))
            tide_window_end = min(datetime.combine(d, datetime.strptime("2:30 PM", "%I:%M %p").time()),
                                  datetime.combine(d, (datetime.combine(d, tide_time) + timedelta(hours=3)).time()))
            
            if not (tide_window_start <= cursor <= tide_window_end - duration):
                continue

            truck_day = st.session_state.truck_bookings[truck].get(d, [])
            if has_conflict(truck_day, cursor, cursor + duration):
                continue

            if requires_crane:
                crane_day = st.session_state.truck_bookings[17].get(d, [])
                if has_conflict(crane_day, cursor, cursor + duration):
                    continue

            found_slots.append((d, cursor))
            if len(found_slots) >= max_slots:
                return found_slots

    return found_slots

# [rest of your existing code remains the same]
