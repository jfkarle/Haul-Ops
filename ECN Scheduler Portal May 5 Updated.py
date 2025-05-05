# ECM_Scheduler_Portal_May_5.py
# Name parser fix: Extracts 'Norma Jean' from input like "Hi this is Norma Jean - I'd like..."

import streamlit as st
import pandas as pd
import datetime as dt
import re
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from dateutil.parser import parse
import calendar

st.set_page_config("ECM Scheduler", layout="centered")
st.title("🚚 ECM Boat Transport Scheduler")

st.markdown("""
Enter a scheduling request like:
> *"Hi this is Wanda Sykes. I'd like to schedule a haul for the week of October 14. Pickup at 110 Ocean St, launching from Taylor Marine. 38' powerboat. Prefer truck S20."*
""")

user_input = st.text_area("Enter request here:")

try:
    scheduled = pd.read_csv("scheduled_jobs.csv")
except:
    scheduled = pd.DataFrame(columns=["Customer", "Service", "Date", "Time", "Ramp", "Truck"])

# Improved parser: now handles name before dash or comma

def parse_request(text):
    name_match = re.search(r"(?:this is|i'm|i am)\s+([A-Z][a-zA-Z']+\s[A-Z][a-zA-Z']+)(?=\s|[-,])", text, re.IGNORECASE)
    if not name_match:
        name_match = re.search(r"^([A-Z][a-zA-Z']+\s[A-Z][a-zA-Z']+)(?=\s|[-,])", text)

    service_match = re.search(r"launch|haul|land-?land", text, re.IGNORECASE)
    date_match = re.search(r"week of ([A-Za-z]+\s\d{1,2})", text)
    ramp_match = re.search(r"(at|from)\s+([A-Za-z\s]+)[.,]", text)
    boat_match = re.search(r"(\d+\'?\s?(foot|ft|\'))?\s*(powerboat|sailboat).*", text, re.IGNORECASE)
    truck_match = re.search(r"truck\s+(S\d+)", text)

    name = name_match.group(1).title() if name_match else "Unknown"
    service = service_match.group(0).capitalize() if service_match else "Haul"
    date_str = date_match.group(1) if date_match else "October 14"
    ramp = ramp_match.group(2).strip() if ramp_match else "Scituate"
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

def generate_weekly_slots(start_date):
    times = [dt.time(9), dt.time(11), dt.time(13)]
    slots = []
    for i in range(5):
        day = start_date + dt.timedelta(days=i)
        for t in times:
            slot_dt = dt.datetime.combine(day, t)
            slots.append(slot_dt)
    return slots

def draw_slot_grid(slots, selected_slot):
    fig, ax = plt.subplots(figsize=(7, 4))
    times = sorted(set([s.time() for s in slots]))
    days = [slots[0].date() + dt.timedelta(days=i) for i in range(5)]
    ax.set_xlim(0, 5)
    ax.set_ylim(0, len(times))
    ax.axis('off')

    for x, d in enumerate(days):
        for y, t in enumerate(times):
            slot = dt.datetime.combine(d, t)
            color = 'green' if slot != selected_slot else 'blue'
            circ = Circle((x + 0.5, y + 0.5), 0.3, color=color)
            ax.add_patch(circ)
            ax.text(x + 0.5, y + 0.5, t.strftime('%I:%M'), ha='center', va='center', fontsize=8, color='white')
        ax.text(x + 0.5, len(times) + 0.1, calendar.day_abbr[d.weekday()], ha='center', fontsize=9)
    st.pyplot(fig)

if st.button("Submit Request"):
    parsed = parse_request(user_input)
    st.subheader("🔍 Parsed Request")
    st.json(parsed)

    week_slots = generate_weekly_slots(parsed['StartDate'])
    readable = [s.strftime('%A %I:%M %p') for s in week_slots]
    selected_idx = st.selectbox("Select a time slot:", list(range(len(readable))), format_func=lambda i: readable[i])
    selected_slot = week_slots[selected_idx]

    st.subheader("📅 Weekly Grid")
    draw_slot_grid(week_slots, selected_slot)

    if st.button("✅ Confirm This Slot"):
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
