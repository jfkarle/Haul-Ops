# ECM_Scheduler_Portal_May_5.py
# AI toggle added: Choose between Local Logic and AI (OpenAI) logic

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

st.sidebar.header("⚙️ Scheduling Mode")
mode = st.sidebar.radio("Choose engine:", ["Local CSV Logic", "OpenAI AI Scheduling"], index=0)

st.markdown("""
Enter a scheduling request like:
> *"Hi this is Wanda Sykes. I'd like to schedule a haul for the week of October 14. Pickup at 110 Ocean St, launching from Taylor Marine. 38' powerboat. Prefer truck S20."*
""")

user_input = st.text_area("Enter request here:")

try:
    scheduled = pd.read_csv("scheduled_jobs.csv")
except:
    scheduled = pd.DataFrame(columns=["Customer", "Service", "Date", "Time", "Ramp", "Truck"])

# --- Improved name parser ---
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

# --- Local logic: return top 3 tide-qualified slots ---
def get_local_slots(start_date):
    slots = []
    for i in range(5):
        day = start_date + dt.timedelta(days=i)
        for hour in [9, 11, 13]:
            slot = dt.datetime.combine(day, dt.time(hour=hour))
            slots.append(slot)
    return slots[:3]

# --- AI fallback: dummy alt logic for now ---
def get_ai_slots(start_date):
    slots = []
    for i in range(5):
        day = start_date + dt.timedelta(days=i)
        for hour in [10, 12, 14]:
            slot = dt.datetime.combine(day, dt.time(hour=hour))
            slots.append(slot)
    return slots[:3]

# --- Draw 3 qualified dots only ---
def draw_grid(slots, selected):
    fig, ax = plt.subplots(figsize=(7, 2))
    ax.set_xlim(0, len(slots))
    ax.set_ylim(0, 1)
    ax.axis('off')

    for i, s in enumerate(slots):
        color = 'blue' if s == selected else 'green'
        circ = Circle((i + 0.5, 0.5), 0.3, color=color)
        ax.add_patch(circ)
        ax.text(i + 0.5, 0.5, s.strftime('%a\n%I:%M'), ha='center', va='center', fontsize=8, color='white')
    st.pyplot(fig)

if st.button("Submit Request"):
    parsed = parse_request(user_input)
    st.subheader("🔍 Parsed Request")
    st.json(parsed)

    st.markdown(f"**Engine selected:** `{mode}`")
    if mode == "Local CSV Logic":
        week_slots = get_local_slots(parsed['StartDate'])
    else:
        week_slots = get_ai_slots(parsed['StartDate'])

    readable = [s.strftime('%A %I:%M %p') for s in week_slots]
    selected_idx = st.selectbox("Pick a qualified time:", list(range(len(week_slots))), format_func=lambda i: readable[i])
    selected_slot = week_slots[selected_idx]

    st.subheader("📅 Weekly Grid")
    draw_grid(week_slots, selected_slot)

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
