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
    return "8445138"  # Default fallback to Scituate

def get_colored_slots_for_day(harbor, date, valid_windows_df):
    slots = []
    start_time = datetime.combine(date, datetime.strptime("08:00", "%H:%M").time())
    end_time = datetime.combine(date, datetime.strptime("17:00", "%H:%M").time())

    while start_time < end_time:
        slot_color = "gray"
        matching_windows = valid_windows_df[
            (valid_windows_df['Harbor'] == harbor) &
            (valid_windows_df['Date'] == date)
        ]

        for _, row in matching_windows.iterrows():
            if row['Start'] <= start_time < row['End']:
                slot_color = "yellow"
                break

        slots.append({
            "time": start_time.strftime("%I:%M %p"),
            "color": slot_color
        })
        start_time += timedelta(minutes=30)

    return slots

import streamlit as st

def fetch_daytime_high_tides_2025_per_station(ramp_names):
    all_predictions = []
    base_url = "https://api.tidesandcurrents.noaa.gov/api/prod/datagetter"
    params_template = {
        "product": "predictions",
        "datum": "MLLW",
        "time_zone": "lst_ldt",
        "units": "english",
        "interval": "hilo",
        "format": "json",
        "begin_date": "20250101",
        "end_date": "20251231"
    }

    stations = {
        "Scituate": "8445138",
        "Plymouth": "8446493",
        "Duxbury": "8446166",
        "Cohasset": "8444762"
    }

    for harbor, station_id in stations.items():
        params = params_template.copy()
        params["station"] = station_id

        try:
            response = requests.get(base_url, params=params)
            response.raise_for_status()
            data = response.json().get("predictions", [])

            for entry in data:
                t = datetime.strptime(entry["t"], "%Y-%m-%d %H:%M")
                if entry["type"] == "H":
                    if datetime.strptime("07:30", "%H:%M").time() <= t.time() <= datetime.strptime("17:00", "%H:%M").time():
                        all_predictions.append({
                            "Harbor": harbor,
                            "Date": t.date(),
                            "Time": t.time(),
                            "DateTime": t,
                            "Tide Height (ft)": float(entry["v"]),
                            "Type": "H"
                        })
        except Exception as e:
            print(f"Error fetching {harbor}: {e}")

    return pd.DataFrame(all_predictions)

def tide_preview_table(daytime_high_tides):
    st.subheader("Tide Preview Debug Panel")
    for harbor in daytime_high_tides['Harbor'].unique():
        st.markdown(f"### {harbor}")
        st.dataframe(
            daytime_high_tides[daytime_high_tides['Harbor'] == harbor]
            .sort_values("Date")
            .reset_index(drop=True)
        )

import pandas as pd
import requests
from datetime import datetime, timedelta

def extract_daytime_high_tides_from_url(url, harbor_name):
    try:
        df = pd.read_csv(url)
        valid_times = []
        for _, row in df.iterrows():
            try:
                date = pd.to_datetime(row['Date']).date()
                tide_times = str(row['High Tide']).split('/')
                for tide_str in tide_times:
                    t = datetime.strptime(tide_str.strip(), "%I:%M %p").time()
                    if datetime.strptime("07:30", "%H:%M").time() <= t <= datetime.strptime("17:00", "%H:%M").time():
                        dt = datetime.combine(date, t)
                        valid_times.append({ 'DateTime': dt, 'Harbor': harbor_name })
                        break
            except:
                continue
        return pd.DataFrame(valid_times)
    except Exception as e:
        print(f"Failed to load {harbor_name} from URL: {url}")
        return pd.DataFrame(columns=['DateTime', 'Harbor'])

# Load each tide CSV from GitHub
tide_files = {
    "Scituate": "Scituate_2025_Tide_Times.csv",
    "Plymouth": "Plymouth_2025_Tide_Times.csv",
    "Duxbury": "Duxbury_2025_Tide_Times.csv",
    "Cohasset": "Cohasset_2025_Tide_Times.csv",
    "Brant Rock": "Brant_Rock_2025_Tide_Times.csv"
}

tide_frames = []
for harbor, filename in tide_files.items():
    url = f"https://raw.githubusercontent.com/Jfkarle/Haul-Ops/main/data/{filename}"
    tide_frames.append(extract_daytime_high_tides_from_url(url, harbor))

daytime_high_tides = pd.concat(tide_frames).sort_values("DateTime").reset_index(drop=True)

def get_valid_ramp_windows(daytime_high_tides, ramp_rules):
    """
    Apply ramp-specific tide buffer windows to verified daytime high tides.
    Returns a list of valid scheduling windows per harbor per day.
    """
    valid_windows = []

    for _, row in daytime_high_tides.iterrows():
        harbor = row['Harbor']
        tide_time = row['DateTime']

        if harbor not in ramp_rules:
            continue  # skip unknown ramps

        buffers = ramp_rules[harbor]
        before = timedelta(minutes=buffers['before_buffer_min'])
        after = timedelta(minutes=buffers['after_buffer_min'])

        start_time = tide_time - before
        end_time = tide_time + after

        # Clamp to operating hours (7:30 AM to 5:00 PM)
        business_start = tide_time.replace(hour=7, minute=30)
        business_end = tide_time.replace(hour=17, minute=0)

        start_time = max(start_time, business_start)
        end_time = min(end_time, business_end)

        if start_time < end_time:
            valid_windows.append({
                'Harbor': harbor,
                'Date': tide_time.date(),
                'Start': start_time,
                'End': end_time
            })

    return pd.DataFrame(valid_windows)

ramp_rules = {
    'Scituate': {'before_buffer_min': 180, 'after_buffer_min': 180},
    'Duxbury': {'before_buffer_min': 90, 'after_buffer_min': 120},
    'Plymouth': {'before_buffer_min': 120, 'after_buffer_min': 120},
    'Cohasset': {'before_buffer_min': 150, 'after_buffer_min': 150},
    'Brant Rock': {'before_buffer_min': 90, 'after_buffer_min': 90}
}

valid_windows_df = get_valid_ramp_windows(daytime_high_tides, ramp_rules)

from datetime import datetime, timedelta

# === TIDE WINDOW PREPROCESSING ===
# Load tide data and ramp rules (should be preloaded from file or memory in production)
import os


import requests

def extract_daytime_high_tides_from_url(url, harbor_name):
    try:
        df = pd.read_csv(url)
        valid_times = []
        for _, row in df.iterrows():
            try:
                date = pd.to_datetime(row['Date']).date()
                tide_times = str(row['High Tide']).split('/')
                for tide_str in tide_times:
                    t = datetime.strptime(tide_str.strip(), "%I:%M %p").time()
                    if datetime.strptime("07:30", "%H:%M").time() <= t <= datetime.strptime("17:00", "%H:%M").time():
                        dt = datetime.combine(date, t)
                        valid_times.append({ 'DateTime': dt, 'Harbor': harbor_name })
                        break
            except:
                continue
        return pd.DataFrame(valid_times)
    except Exception as e:
        print(f"Failed to load {harbor_name} from URL: {url}")
        return pd.DataFrame(columns=['DateTime', 'Harbor'])

# Load each tide CSV from GitHub
tide_files = {
    "Scituate": "Scituate_2025_Tide_Times.csv",
    "Plymouth": "Plymouth_2025_Tide_Times.csv",
    "Duxbury": "Duxbury_2025_Tide_Times.csv",
    "Cohasset": "Cohasset_2025_Tide_Times.csv",
    "Brant Rock": "Brant_Rock_2025_Tide_Times.csv"
}

tide_frames = []
for harbor, filename in tide_files.items():
    url = f"https://raw.githubusercontent.com/Jfkarle/Haul-Ops/main/data/{filename}"
    tide_frames.append(extract_daytime_high_tides_from_url(url, harbor))

ramp_rules = {
    'Scituate': {'before_buffer_min': 180, 'after_buffer_min': 180},
    'Duxbury': {'before_buffer_min': 90, 'after_buffer_min': 120},
    'Plymouth': {'before_buffer_min': 120, 'after_buffer_min': 120},
    'Cohasset': {'before_buffer_min': 150, 'after_buffer_min': 150},
    'Brant Rock': {'before_buffer_min': 90, 'after_buffer_min': 90}
}

# Example: During job loop, filter this table by harbor and date
# job_harbor = 'Scituate'
# job_date = datetime(2025, 10, 14).date()
# windows = valid_windows_df[(valid_windows_df['Harbor'] == job_harbor) & (valid_windows_df['Date'] == job_date)]
# Then check if job duration fits within any window in `windows`


from datetime import timedelta

def get_valid_ramp_windows(daytime_high_tides, ramp_rules):
    """
    Apply ramp-specific tide buffer windows to verified daytime high tides.
    Returns a list of valid scheduling windows per harbor per day.
    """
    valid_windows = []

    for _, row in daytime_high_tides.iterrows():
        harbor = row['Harbor']
        tide_time = row['DateTime']

        if harbor not in ramp_rules:
            continue  # skip unknown ramps

        buffers = ramp_rules[harbor]
        before = timedelta(minutes=buffers['before_buffer_min'])
        after = timedelta(minutes=buffers['after_buffer_min'])

        start_time = tide_time - before
        end_time = tide_time + after

        # Clamp to operating hours (7:30 AM to 5:00 PM)
        business_start = tide_time.replace(hour=7, minute=30)
        business_end = tide_time.replace(hour=17, minute=0)

        start_time = max(start_time, business_start)
        end_time = min(end_time, business_end)

        if start_time < end_time:
            valid_windows.append({
                'Harbor': harbor,
                'Date': tide_time.date(),
                'Start': start_time,
                'End': end_time
            })

    return pd.DataFrame(valid_windows)


import streamlit as st
import pandas as pd
import datetime as dt
import re
from dateutil.parser import parse

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
    name_match = re.search(r"(?:this is|i'm|i am)\s+([A-Z][a-zA-Z']+\s[A-Z][a-zA-Z']+)", text, re.IGNORECASE)
    if not name_match:
        name_match = re.search(r"^([A-Z][a-zA-Z']+\s[A-Z][a-zA-Z']+)", text)
    service_match = re.search(r"launch|haul|land-?land", text, re.IGNORECASE)
    date_match = re.search(r"week of ([A-Za-z]+\s\d{1,2})", text)
    ramp_match = re.search(r"(at|from)\s+([A-Za-z\s]+)[.,]", text)
    boat_match = re.search(r"(powerboat|sailboat)", text, re.IGNORECASE)
    truck_match = re.search(r"truck\s+(S\d+)", text)

    name = name_match.group(1).title() if name_match else "Unknown"
    service = service_match.group(0).capitalize() if service_match else "Haul"
    date_str = date_match.group(1) if date_match else "October 14"
    ramp = ramp_match.group(2).strip() if ramp_match else "Scituate"
    boat_type = boat_match.group(1).capitalize() if boat_match else "Powerboat"
    truck = truck_match.group(1) if truck_match else "S20"

    base_date = parse(f"{date_str} 2025")
    start_date = base_date - dt.timedelta(days=base_date.weekday())

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
            hours = [8, 11, 14]
        else:
            hours = [8, 9.5, 11, 12.5, 14, 15.5]
        for hour in hours:
            h = int(hour)
            m = int((hour - h) * 60)
            slots.append(dt.datetime.combine(day, dt.time(h, m)))
    return slots[:3]

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
    tide_df["Date"] = pd.to_datetime(tide_df["Date"], errors='coerce')
    tide_df["High Tide"] = pd.to_datetime(tide_df["High Tide"], format="%I:%M %p", errors='coerce').dt.time
    tide_by_day = {d.strftime("%a\n%b %d"): tide_df[tide_df["Date"].dt.date == d.date()] for d in days}

    def style_func(val, row_idx, col_name):
        try:
            cell_time = dt.datetime.strptime(row_idx, "%I:%M %p").time()
        except:
            return ""

        if col_name in tide_by_day:
            for _, tide_row in tide_by_day[col_name].iterrows():
                tide_time = tide_row["High Tide"]
                total_minutes = tide_time.hour * 60 + tide_time.minute
                rounded_minutes = int(15 * round(total_minutes / 15))
                tide_rounded = dt.time(hour=rounded_minutes // 60, minute=rounded_minutes % 60)
                if tide_rounded == cell_time:
                    return "background-color: yellow"
        if isinstance(val, str) and "AVAILABLE" in val:
            return "background-color: lightgreen"
        elif isinstance(val, str) and "🛥" in val:
            return "color: gray"
        return ""

    styled = grid.style.apply(lambda row: [style_func(row[col], row.name, col) for col in row.index], axis=1)
    st.subheader("📊 Weekly Calendar Grid with Tides")
    st.dataframe(styled, use_container_width=True, height=800)

if st.button("Submit Request"):
    parsed = parse_request(user_input)
    st.subheader("🔍 Parsed Request")
    station_id = get_station_for_ramp(parsed.get("Ramp", ""))
    parsed_display = dict(parsed)
    parsed_display["Station ID"] = station_id
    st.json(parsed_display)

    st.markdown(f"**Engine selected:** `{mode}`")
    if mode == "Local CSV Logic":
        week_slots = get_local_slots(parsed['StartDate'], parsed['BoatType'])
    else:
        week_slots = get_local_slots(parsed['StartDate'], parsed['BoatType'])

    readable = [s.strftime('%A %I:%M %p') for s in week_slots]
    selected_idx = st.selectbox("Pick a qualified time:", list(range(len(week_slots))), format_func=lambda i: readable[i])
    selected_slot = week_slots[selected_idx]

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