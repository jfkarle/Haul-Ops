# ECM_Scheduler_Portal_May_5.py
# Streamlit app to schedule boat transport jobs based on tide, ramp, truck, and customer input constraints

import streamlit as st
import pandas as pd
import datetime as dt
import re
from dateutil.parser import parse
import calendar

# --- Load pre-saved tide files (per harbor) ---
TIDE_FILES = {
    'Scituate': 'Scituate_2025_Tide_Times.csv',
    'Plymouth': 'Plymouth_2025_Tide_Times.csv',
    'Cohasset': 'Cohasset_2025_Tide_Times.csv',
    'Duxbury': 'Duxbury_2025_Tide_Times.csv',
    'Brant Rock': 'Brant_Rock_2025_Tide_Times.csv'
}

# --- Configuration ---
st.set_page_config("ECM Scheduler", layout="centered")
st.title("🚚 ECM Boat Transport Scheduler")

st.markdown("""
Enter a natural language scheduling request below. Example:
> *"Hi this is Larry David. I’d like to schedule a haul for the week of October 14. Pickup is 110 Ocean St, Marshfield, launching from Taylor Marine, 38' powerboat, prefer truck S20."*
""")

user_input = st.text_area("Enter request here:")

# --- Load scheduled jobs ---
try:
    scheduled = pd.read_csv("scheduled_jobs.csv")
except:
    scheduled = pd.DataFrame(columns=["Customer", "Service", "Date", "Time", "Ramp", "Truck"])

# --- Helper functions ---
def parse_request(text):
    name_match = re.search(r"(?:this is|i'm|i am)\s+([A-Z][a-zA-Z']+\s[A-Z][a-zA-Z']+)", text, re.IGNORECASE)
    service_match = re.search(r"launch|haul|land-?land", text, re.IGNORECASE)
    date_match = re.search(r"week of ([A-Za-z]+ \d{1,2})", text)
    ramp_match = re.search(r"from ([A-Za-z\s]+)[.,]", text)
    boat_match = re.search(r"(\d+\'?\s?(foot|ft|\'))?\s*(powerboat|sailboat).*", text, re.IGNORECASE)
    truck_match = re.search(r"truck (S\d+)", text)

    name = name_match.group(1).title() if name_match else "Unknown"
    service = service_match.group(0).capitalize() if service_match else "Haul"
    date_str = date_match.group(1) if date_match else "October 14"
    ramp = ramp_match.group(1).strip() if ramp_match else "Scituate"
    boat_type = "Powerboat"
    if boat_match:
        if "sail" in boat_match.group(0).lower():
            boat_type = "Sailboat"

    truck = truck_match.group(1) if truck_match else "S20"
    
    try:
        year = 2025
        base_date = parse(f"{date_str} {year}")
        start_date = base_date - dt.timedelta(days=base_date.weekday())
    except:
        start_date = dt.date(2025, 10, 14)

    return {
        "Customer": name,
        "Service": service,
        "StartDate": start_date,
        "Ramp": ramp,
        "BoatType": boat_type,
        "Truck": truck
    }

# --- Simulate available slots (replace with real tide logic) ---
def get_available_slots(start_date):
    slots = []
    for i in range(5):
        day = start_date + dt.timedelta(days=i)
        for hr in [9, 11, 1]:
            t = dt.datetime.combine(day, dt.time(hour=hr))
            slots.append(t)
    return slots[:3]

# --- Main Execution ---
if st.button("Submit Request"):
    parsed = parse_request(user_input)
    st.subheader("🔍 Parsed Request")
    st.json(parsed)

    st.subheader("📅 Earliest Available Options")
    available_slots = get_available_slots(parsed["StartDate"])

    selected_slot = None
    cols = st.columns(len(available_slots))
    for i, t in enumerate(available_slots):
        with cols[i]:
            if st.button(f"{t.strftime('%b %d')}\n{t.strftime('%I:%M %p')}"):
                selected_slot = t

    if selected_slot:
        st.success(f"✅ {parsed['Customer']} scheduled on {selected_slot.strftime('%A, %B %d at %I:%M %p')} at {parsed['Ramp']}.")
        new_job = pd.DataFrame([{
            "Customer": parsed['Customer'],
            "Service": parsed['Service'],
            "Date": selected_slot.date(),
            "Time": selected_slot.time(),
            "Ramp": parsed['Ramp'],
            "Truck": parsed['Truck']
        }])
        scheduled = pd.concat([scheduled, new_job], ignore_index=True)
        scheduled.to_csv("scheduled_jobs.csv", index=False)

st.subheader("🗂️ Scheduled Jobs")
st.dataframe(scheduled.sort_values(by=["Date", "Time"]))
