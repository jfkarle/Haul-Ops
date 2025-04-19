
# ✅ Hardened ECM Scheduler: Full features + strict non-overlapping booking for truck and crane
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import os

st.set_page_config(page_title="ECM Boat Scheduler", layout="centered")

ramp_options = [
    "Sandwich Basin",
    "Plymouth Harbor",
    "Cordage Park (Ply)",
    "Duxbury Harbor",
    "Green Harbor (Taylors)",
    "Safe Harbor (Green Harbor)",
    "Ferry Street (Marshfield Yacht Club)",
    "South River Yacht Yard",
    "Roht (A to Z / Mary's)",
    "Scituate Harbor (Jericho Road)",
    "Cohasset Harbor (Parker Ave)",
    "Hull (A St, Sunset, Steamboat)",
    "Hull (X Y Z St) (Goodwin V St)",
    "Hingham Harbor",
    "Weymouth Harbor (Wessagusset)"
]

if "show_form" not in st.session_state:
    st.session_state.show_form = True
if "last_result" not in st.session_state:
    st.session_state.last_result = ""
if "schedule_log" not in st.session_state:
    st.session_state.schedule_log = []

truck_bookings = {20: {}, 21: {}, 23: {}, 17: {}}
crane_schedule = {}
tide_data = {}
loaded_files = []
for filename in os.listdir():
    if filename.endswith('_2025_Tide_Times.csv'):
        df = pd.read_csv(filename)
        for _, row in df.iterrows():
            key = (row['Harbor'], row['Date'])
            tide_data[key] = row['High Tide']
        loaded_files.append(filename)
st.sidebar.success("📂 Tide files loaded: " + ", ".join(loaded_files))

def normalize_ramp_name(ramp):
    cleaned = ramp.strip().lower()
    ramp_aliases = {
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
    return ramp_aliases.get(cleaned, cleaned.title())

def get_high_tide(harbor, date):
    harbor = normalize_ramp_name(harbor)
    date_str = date.strftime("%B %#d, %Y") if os.name == "nt" else date.strftime("%B %-d, %Y")
    key = (harbor, date_str)
    if key in tide_data:
        return tide_data[key]
    elif ("Scituate", date_str) in tide_data:
        return tide_data[("Scituate", date_str)]
    else:
        return None

def has_conflict(existing, start, end):
    return any(s < end and e > start for s, e in existing)

def schedule_customer(data):
    name = data['Customer Name']
    boat_type = data['Boat Type']
    truck = data['Truck']
    date = pd.to_datetime(data['Requested Date'])
    ramp = data['Destination']
    high_tide_str = get_high_tide(ramp, date)
    if high_tide_str is None:
        return "❌ No tide data found for this destination and date."

    try:
        high_tide_time = datetime.strptime(high_tide_str, "%I:%M %p").time()
    except Exception as e:
        return f"❌ Tide time format error: {e}"

    duration = timedelta(hours=1.5) if boat_type.lower() == "powerboat" else timedelta(hours=3)
    requires_crane = boat_type.lower() == "sailboat"
    truck_start = datetime.strptime("08:00 AM", "%I:%M %p").time()
    truck_end = datetime.strptime("02:30 PM", "%I:%M %p").time()
    tide_start = (datetime.combine(date.date(), high_tide_time) - timedelta(hours=3)).time()
    tide_end = (datetime.combine(date.date(), high_tide_time) + timedelta(hours=3)).time()
    valid_start = max(truck_start, tide_start)
    valid_end = min(truck_end, tide_end)
    start_dt = datetime.combine(date.date(), valid_start)
    end_dt = datetime.combine(date.date(), valid_end)

    if end_dt - start_dt < duration:
        return f"❌ Not enough overlap between tide and truck window (Tide: {high_tide_str})"

    crane_ramp = crane_schedule.get(date.date())
    if requires_crane and crane_ramp and crane_ramp != ramp:
        return f"❌ Crane already locked to {crane_ramp} on {date.strftime('%B %d, %Y')}"

    cursor = start_dt
    while cursor + duration <= end_dt:
        truck_day_bookings = truck_bookings[truck].get(date.date(), [])
        if has_conflict(truck_day_bookings, cursor, cursor + duration):
            cursor += timedelta(minutes=15)
            continue

        if requires_crane:
            crane_day_bookings = truck_bookings[17].get(date.date(), [])
            if has_conflict(crane_day_bookings, cursor, cursor + duration):
                cursor += timedelta(minutes=15)
                continue

        end_time = cursor + duration
        truck_bookings[truck].setdefault(date.date(), []).append((cursor, end_time))
        if requires_crane:
            truck_bookings[17].setdefault(date.date(), []).append((cursor, end_time))
            crane_schedule[date.date()] = ramp

        st.session_state.schedule_log.append({
            "Customer": name,
            "Date": date.strftime('%B %d, %Y'),
            "Start": cursor.strftime('%-I:%M %p'),
            "End": end_time.strftime('%-I:%M %p'),
            "Truck": truck,
            "Crane": "Yes" if requires_crane else "No",
            "Ramp": ramp,
            "High Tide": high_tide_str
        })

        return (f"✅ Scheduled for {date.strftime('%B %d, %Y')} from "
                f"{cursor.strftime('%-I:%M %p')} to {end_time.strftime('%-I:%M %p')}\n"
                f"High Tide: {high_tide_str}, Truck: {truck}, Crane: {'Yes' if requires_crane else 'No'}")
    return "❌ No valid time block available"

if st.sidebar.checkbox("📋 View Scheduled Boats"):
    if st.session_state.schedule_log:
        df = pd.DataFrame(st.session_state.schedule_log)
        st.sidebar.dataframe(df)
    else:
        st.sidebar.info("No scheduled boats yet.")

st.title("🛥️ ECM Boat Hauling Scheduler")
st.markdown("#### Schedule a boat for pickup using live tide windows:")

with st.container():
    if st.session_state.show_form:
        with st.form("schedule_form"):
            st.markdown("### 🚤 Customer Delivery Form")
            name = st.text_input("Customer Name")
            col1, col2 = st.columns(2)
            with col1:
                cust_type = st.selectbox("Customer Type", ["New", "Existing"])
                boat_type = st.selectbox("Boat Type", ["Powerboat", "Sailboat"])
                truck = st.selectbox("Assigned Truck", [20, 21, 23])
            with col2:
                length = st.number_input("Boat Length (ft)", min_value=20, max_value=60)
                draft = st.text_input("Keel Draft (ft)", value="N/A") if boat_type == "Sailboat" else "N/A"
                requested_date = st.date_input("Requested Date", value=datetime.today().date())
            origin = st.text_input("Origin Address")
            destination = st.selectbox("Destination Ramp", ramp_options, format_func=lambda x: x)

            submitted = st.form_submit_button("📦 Schedule Now")

            if submitted:
                data = {
                    "Customer Name": name,
                    "Customer Type": cust_type,
                    "Boat Type": boat_type,
                    "Length": length,
                    "Draft": draft,
                    "Truck": truck,
                    "Origin": origin,
                    "Destination": destination,
                    "Requested Date": requested_date
                }
                result = schedule_customer(data)
                st.session_state.last_result = result
                st.session_state.show_form = False
    else:
        st.success(st.session_state.last_result)
        if st.button("📋 Schedule Another"):
            st.session_state.last_result = ""
            st.session_state.show_form = True
