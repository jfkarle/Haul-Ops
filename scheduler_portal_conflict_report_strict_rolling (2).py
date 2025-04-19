
# ECM Scheduler with Rolling Retry Logic (Truck + Tide + Crane + Ramp)
# Automatically scans next 30 valid days if requested date is blocked

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
import os

st.set_page_config(page_title="ECM Boat Scheduler", layout="centered")

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

# Load tides
tide_data = {}
for filename in os.listdir():
    if filename.endswith('_2025_Tide_Times.csv'):
        df = pd.read_csv(filename)
        for _, row in df.iterrows():
            tide_data[(row['Harbor'], row['Date'])] = row['High Tide']

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
    date_str = date.strftime("%B %-d, %Y")
    if (harbor, date_str) in tide_data:
        return tide_data[(harbor, date_str)]
    elif ("Scituate", date_str) in tide_data:
        return tide_data[("Scituate", date_str)]
    return None

def has_conflict(existing, start, end):
    return any(s < end and e > start for s, e in existing)

def valid_delivery_day(d):
    return d.weekday() < 5 or (d.weekday() == 5 and d.month in [5, 9])  # Monday–Friday, or Saturday in May/Sept

def try_schedule(date, data, tide_time, duration, requires_crane):
    truck = data["Truck"]
    ramp = data["Destination"]
    cursor = datetime.combine(date, max(datetime.strptime("08:00 AM", "%I:%M %p").time(),
                                        (datetime.combine(date, tide_time) - timedelta(hours=3)).time()))
    end_limit = datetime.combine(date, min(datetime.strptime("2:30 PM", "%I:%M %p").time(),
                                           (datetime.combine(date, tide_time) + timedelta(hours=3)).time()))

    while cursor + duration <= end_limit:
        truck_day = st.session_state.truck_bookings[truck].get(date, [])
        if has_conflict(truck_day, cursor, cursor + duration):
            cursor += timedelta(minutes=15)
            continue
        if requires_crane:
            crane_day = st.session_state.truck_bookings[17].get(date, [])
            if has_conflict(crane_day, cursor, cursor + duration):
                cursor += timedelta(minutes=15)
                continue

        end_time = cursor + duration
        st.session_state.truck_bookings[truck].setdefault(date, []).append((cursor, end_time))
        if requires_crane:
            st.session_state.truck_bookings[17].setdefault(date, []).append((cursor, end_time))
            st.session_state.crane_schedule[date] = ramp

        st.session_state.schedule_log.append({
            "Customer": data["Customer Name"],
            "Date": date.strftime('%B %d, %Y'),
            "Start": cursor.strftime('%-I:%M %p'),
            "End": end_time.strftime('%-I:%M %p'),
            "Truck": truck,
            "Crane": "Yes" if requires_crane else "No",
            "Ramp": ramp,
            "High Tide": tide_time.strftime('%-I:%M %p')
        })

        return f"✅ Scheduled for {date.strftime('%B %d, %Y')} from {cursor.strftime('%-I:%M %p')} to {end_time.strftime('%-I:%M %p')}\nHigh Tide: {tide_time.strftime('%-I:%M %p')}, Truck: {truck}, Crane: {'Yes' if requires_crane else 'No'}"
        break

    return None  # no slot found on that day

def schedule_customer(data):
    orig_date = pd.to_datetime(data['Requested Date']).date()
    duration = timedelta(hours=1.5) if data["Boat Type"].lower() == "powerboat" else timedelta(hours=3)
    requires_crane = data["Boat Type"].lower() == "sailboat"

    for offset in range(0, 31):  # try up to 30 days ahead
        d = orig_date + timedelta(days=offset)
        if not valid_delivery_day(d):
            continue
        tide_str = get_high_tide(data["Destination"], d)
        if tide_str is None:
            continue
        try:
            tide_time = datetime.strptime(tide_str, "%I:%M %p").time()
        except Exception:
            continue

        result = try_schedule(d, data, tide_time, duration, requires_crane)
        if result:
            return result

    return "❌ No valid time slot found in next 30 days."

if st.sidebar.checkbox("📋 View Scheduled Boats"):
    if st.session_state.schedule_log:
        st.sidebar.dataframe(pd.DataFrame(st.session_state.schedule_log))
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
            destination = st.selectbox("Destination Ramp", ramp_options)

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
                st.session_state.last_result = schedule_customer(data)
                st.session_state.show_form = False
    else:
        st.success(st.session_state.last_result)
        if st.button("📋 Schedule Another"):
            st.session_state.last_result = ""
            st.session_state.show_form = True
