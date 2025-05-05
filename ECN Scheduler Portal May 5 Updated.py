# ECM_Scheduler_Portal_May_5.py
# Now with sidebar AI toggle, smarter name parsing, and improved calendar display

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

# --- Draw calendar for week of a given date ---
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

# --- Highlighted grid calendar with tide overlays ---
render_calendar(scheduled, week_slots, parsed['StartDate'], parsed['Ramp'])
    import numpy as np

    # Time and day grid
    time_slots = [dt.time(hour=h, minute=m) for h in range(8, 17) for m in [0, 15, 30, 45]]
    days = [start_date + dt.timedelta(days=i) for i in range(5)]

    grid = pd.DataFrame(index=[t.strftime("%-I:%M %p") for t in time_slots],
                        columns=[d.strftime("%a\n%b %d") for d in days])

    # Fill scheduled jobs
    for _, row in scheduled_df.iterrows():
        d = pd.to_datetime(row["Date"])
        col = d.strftime("%a\n%b %d")
        t = pd.to_datetime(str(row["Time"]))
        row_label = t.strftime("%-I:%M %p")
        if col in grid.columns and row_label in grid.index:
            grid.at[row_label, col] = f"🛥 {row['Customer']}"

    # Add suggested green slots
    for t in suggestions:
        col = t.strftime("%a\n%b %d")
        row_label = t.strftime("%-I:%M %p")
        if col in grid.columns and row_label in grid.index:
            if pd.isna(grid.at[row_label, col]):
                grid.at[row_label, col] = "✅ AVAILABLE"

    # Load tide data
    tide_file = TIDE_FILES.get(ramp_name.strip(), TIDE_FILES["Scituate"])
    tide_df = pd.read_csv(tide_file)
    tide_df["DateTime"] = pd.to_datetime(tide_df["Date Time"])
    tide_df = tide_df[tide_df["DateTime"].dt.time.between(dt.time(7, 30), dt.time(16, 0))]

    tide_by_day = {}
    for d in days:
        key = d.strftime("%a\n%b %d")
        tide_by_day[key] = tide_df[tide_df["DateTime"].dt.date == d.date()]

    # Highlighter
    def style_func(val, row_idx, col_name):
        try:
            cell_time = dt.datetime.strptime(row_idx, "%I:%M %p").time()
        except:
            return ""

        # Check for tide match
        if col_name in tide_by_day:
            for _, tide_row in tide_by_day[col_name].iterrows():
                tide_time = tide_row["DateTime"].time()
                diff = abs((dt.datetime.combine(dt.date.today(), tide_time) -
                            dt.datetime.combine(dt.date.today(), cell_time)).total_seconds())
                if diff < 3600:  # within 1 hour
                    if tide_row["High/Low"] == "H":
                        return "background-color: yellow"
                    elif tide_row["High/Low"] == "L":
                        return "background-color: red"

        if isinstance(val, str) and "AVAILABLE" in val:
            return "background-color: lightgreen"
        elif isinstance(val, str) and "🛥" in val:
            return "color: gray"
        return ""

    styled = grid.style.apply(
        lambda row: [style_func(row[col], row.name, col) for col in row.index],
        axis=1
    )

    st.subheader("📊 Weekly Calendar Grid with Tides")
    st.dataframe(styled, use_container_width=True, height=800)y
