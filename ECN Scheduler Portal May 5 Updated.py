
# ECM_Scheduler_Portal_May_5.py
# Streamlit app with tide overlay calendar logic

import streamlit as st
import pandas as pd
import datetime as dt
import re
import matplotlib.pyplot as plt
from matplotlib.patches import Circle
from dateutil.parser import parse
import calendar
import numpy as np

# NOAA tide data files
TIDE_FILES = {
    'Scituate': 'Scituate_2025_Tide_Times.csv',
    'Plymouth': 'Plymouth_2025_Tide_Times.csv',
    'Cohasset': 'Cohasset_2025_Tide_Times.csv',
    'Duxbury': 'Duxbury_2025_Tide_Times.csv',
    'Brant Rock': 'Brant_Rock_2025_Tide_Times.csv'
}

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

def parse_request(text):
    name_match = re.search(r"(?:this is|i'm|i am)\s+([A-Z][a-zA-Z']+\s[A-Z][a-zA-Z']+)(?=\s|[-,])", text, re.IGNORECASE)
    if not name_match:
        name_match = re.search(r"^([A-Z][a-zA-Z']+\s[A-Z][a-zA-Z']+)(?=\s|[-,])", text)

    service_match = re.search(r"launch|haul|land-?land", text, re.IGNORECASE)
    date_match = re.search(r"week of ([A-Za-z]+\s\d{1,2})", text)
    ramp_match = re.search(r"(at|from)\s+([A-Za-z\s]+)[.,]", text)
    boat_match = re.search(r"(\d+'?\s?(foot|ft|'))?\s*(powerboat|sailboat).*", text, re.IGNORECASE)
    truck_match = re.search(r"truck\s+(S\d+)", text)

    name = name_match.group(1).title() if name_match else "Unknown"
    service = service_match.group(0).capitalize() if service_match else "Haul"
    date_str = date_match.group(1) if date_match else "October 14"
    ramp = ramp_match.group(2).strip() if ramp_match else "Scituate"
    boat_type = "Powerboat"
    if boat_match and "sail" in boat_match.group(0).lower():
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

def get_local_slots(start_date, boat_type):
    slots = []
    for i in range(5):
        day = start_date + dt.timedelta(days=i)
        if boat_type.lower() == "sailboat":
            hours = [8, 11, 14]  # 3-hour spacing
        else:
            hours = [8, 9, 10.5, 12, 1.5, 3]  # 90-min spacing for powerboats
        for hour in hours:
            h = int(hour)
            m = int((hour - h) * 60)
            slot = dt.datetime.combine(day, dt.time(hour=h, minute=m))
            slots.append(slot)
    return slots[:3]

def get_ai_slots(start_date):
    slots = []
    for i in range(5):
        day = start_date + dt.timedelta(days=i)
        for hour in [10, 12, 14]:
            slot = dt.datetime.combine(day, dt.time(hour=hour))
            slots.append(slot)
    return slots[:3]

def draw_calendar_week(start_date):
    week_start = start_date - dt.timedelta(days=start_date.weekday())
    week_dates = [week_start + dt.timedelta(days=i) for i in range(5)]

    fig, ax = plt.subplots(figsize=(10, 2))
    ax.set_xlim(0, 5)
    ax.set_ylim(0, 1)
    ax.axis('off')

    for i, d in enumerate(week_dates):
        jobs = scheduled[scheduled['Date'] == d.date()]
        label = d.strftime('%a %b %d')
        text = f"{label}\n{len(jobs)} job(s)"
        ax.text(i + 0.5, 0.5, text, ha='center', va='center', fontsize=10)
        ax.add_patch(Circle((i + 0.5, 0.5), 0.35, fill=False))
    st.pyplot(fig)

def render_calendar(scheduled_df, suggestions, start_date, ramp_name):
    time_slots = [dt.time(hour=h, minute=m) for h in range(8, 17) for m in [0, 15, 30, 45]]
    days = [start_date + dt.timedelta(days=i) for i in range(5)]
    grid = pd.DataFrame(index=[t.strftime("%-I:%M %p") for t in time_slots],
                        columns=[d.strftime("%a\n%b %d") for d in days])

    for _, row in scheduled_df.iterrows():
        d = pd.to_datetime(row["Date"])
        col = d.strftime("%a\n%b %d")
        t = pd.to_datetime(str(row["Time"]))
        row_label = t.strftime("%-I:%M %p")
        if col in grid.columns and row_label in grid.index:
            grid.at[row_label, col] = f"🛥 {row['Customer']}"

    for t in suggestions:
        col = t.strftime("%a\n%b %d")
        row_label = t.strftime("%-I:%M %p")
        if col in grid.columns and row_label in grid.index:
            if pd.isna(grid.at[row_label, col]):
                grid.at[row_label, col] = "✅ AVAILABLE"

    tide_file = TIDE_FILES.get(ramp_name.strip(), TIDE_FILES["Scituate"])
    tide_df = pd.read_csv(tide_file)
    tide_df.columns = tide_df.columns.str.strip()
    tide_df["DateTime"] = pd.to_datetime(tide_df.iloc[:, 0], errors='coerce')
    tide_df = tide_df.dropna(subset=["DateTime"])
    tide_df = tide_df[tide_df["DateTime"].dt.time.between(dt.time(7, 30), dt.time(16, 0))]

    tide_by_day = {}
    for d in days:
        key = d.strftime("%a\n%b %d")
        tide_by_day[key] = tide_df[tide_df["DateTime"].dt.date == d.date()]

    def style_func(val, row_idx, col_name):
        try:
            cell_time = dt.datetime.strptime(row_idx, "%I:%M %p").time()
        except:
            return ""

        if col_name in tide_by_day:
            for _, tide_row in tide_by_day[col_name].iterrows():
                tide_time = tide_row["DateTime"].time()
                diff = abs((dt.datetime.combine(dt.date.today(), tide_time) -
                            dt.datetime.combine(dt.date.today(), cell_time)).total_seconds())
                if diff < 3600:
                    if tide_row["High/Low"] == "H":
                        return "background-color: yellow"
                    elif tide_row["High/Low"] == "L":
                        return "background-color: red"

        if isinstance(val, str) and "AVAILABLE" in val:
            return "background-color: lightgreen"
        elif isinstance(val, str) and "🛥" in val:
            return "color: gray"
        return ""

    styled = grid.style.apply(lambda row: [style_func(row[col], row.name, col) for col in row.index], axis=1)
    st.subheader("📊 Weekly Calendar Grid with Tides")
    st.dataframe(styled, use_container_width=True, height=800)

# --- Main interaction ---
if st.button("Submit Request"):
    parsed = parse_request(user_input)
    st.subheader("🔍 Parsed Request")
    st.json(parsed)

    st.markdown(f"**Engine selected:** `{mode}`")
    if mode == "Local CSV Logic":
        week_slots = get_local_slots(parsed['StartDate'], parsed['BoatType'])
    else:
        week_slots = get_ai_slots(parsed['StartDate'])

    readable = [s.strftime('%A %I:%M %p') for s in week_slots]
    selected_idx = st.selectbox("Pick a qualified time:", list(range(len(week_slots))), format_func=lambda i: readable[i])
    selected_slot = week_slots[selected_idx]

    st.subheader("📅 Weekly Grid")
    render_calendar(scheduled, week_slots, parsed['StartDate'], parsed['Ramp'])

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

    st.subheader("📆 Calendar")
    draw_calendar_week(week_slots[0])
    render_calendar(scheduled, week_slots, parsed['StartDate'], parsed['Ramp'])
