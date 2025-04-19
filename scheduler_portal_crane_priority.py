
# ECM Scheduler Patch: Enforce Crane at One Ramp per Day + Prioritize Same-Ramp Sailboats

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, date
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

def try_e(d, data, tide_time, duration, requires_crane):
    truck = data["Truck"]
    ramp = data["Destination"]
    crane_locked_ramp = st.session_state.crane_e.get(d)

    if requires_crane and crane_locked_ramp and crane_locked_ramp != ramp:
        return None  # crane is at a different ramp already

    tide_window_start = max(datetime.combine(d, datetime.strptime("08:00 AM", "%I:%M %p").time()),
                            datetime.combine(d, (datetime.combine(d, tide_time) - timedelta(hours=3)).time()))
    tide_window_end = min(datetime.combine(d, datetime.strptime("2:30 PM", "%I:%M %p").time()),
                          datetime.combine(d, (datetime.combine(d, tide_time) + timedelta(hours=3)).time()))

    cursor = tide_window_start
    while cursor + duration <= tide_window_end:
        truck_day = st.session_state.truck_bookings[truck].get(d, [])
        if has_conflict(truck_day, cursor, cursor + duration):
            cursor += timedelta(minutes=15)
            continue

        if requires_crane:
            crane_day = st.session_state.truck_bookings[17].get(d, [])
            if has_conflict(crane_day, cursor, cursor + duration):
                cursor += timedelta(minutes=15)
                continue

        end_time = cursor + duration
        st.session_state.truck_bookings[truck].setdefault(d, []).append((cursor, end_time))
        if requires_crane:
            st.session_state.truck_bookings[17].setdefault(d, []).append((cursor, end_time))
            st.session_state.crane_e[d] = ramp

        st.session_state.e_log.append({
            "Customer": data["Customer Name"],
            "Date": d.strftime('%B %d, %Y'),
            "Start": cursor.strftime('%-I:%M %p'),
            "End": end_time.strftime('%-I:%M %p'),
            "Truck": truck,
            "Crane": "Yes" if requires_crane else "No",
            "Ramp": ramp,
            "High Tide": tide_time.strftime('%-I:%M %p')
        })

        calendar_msg = add_to_calendar(
            summary=f"Hauling: {data['Customer Name']} → {data['Destination']}",
            description=f"Truck {data['Truck']}, Crane: {'Yes' if requires_crane else 'No'}",
            start_dt=cursor,
            end_dt=end_time
        )
        st.info(calendar_msg)

        
        return f"✅ Scheduled for {d.strftime('%B %d, %Y')} from {cursor.strftime('%-I:%M %p')} to {end_time.strftime('%-I:%M %p')}\nHigh Tide: {tide_time.strftime('%-I:%M %p')}, Truck: {truck}, Crane: {'Yes' if requires_crane else 'No'}"

        cursor += timedelta(minutes=15)
    return None

def schedule_customer(data):
    orig = pd.to_datetime(data["Requested Date"]).date()
    duration = timedelta(hours=1.5 if data["Boat Type"].lower() == "powerboat" else 3)
    requires_crane = data["Boat Type"].lower() == "sailboat"

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

        result = try_schedule(d, data, tide_time, duration, requires_crane)
        if result:
            return result

    return "❌ No valid time block found in next 30 days."

if st.sidebar.checkbox("📋 View Scheduled Boats"):
    if st.session_state.schedule_log:
        st.sidebar.dataframe(pd.DataFrame(st.session_state.schedule_log))
    else:
        st.sidebar.info("No scheduled boats yet.")

st.title("🛥️ ECM Scheduler (Crane Priority)")
with st.container():
    if st.session_state.show_form:
        with st.form("schedule_form"):
            st.markdown("### 🚤 Boat Delivery Form")
            name = st.text_input("Customer Name")
            col1, col2 = st.columns(2)
            with col1:
                cust_type = st.selectbox("Customer Type", ["New", "Existing"])
                boat_type = st.selectbox("Boat Type", ["Powerboat", "Sailboat"])
                truck = st.selectbox("Assigned Truck", [20, 21, 23])
            with col2:
                length = st.number_input("Boat Length", min_value=20, max_value=60)
                draft = st.text_input("Keel Draft", value="N/A") if boat_type == "Sailboat" else "N/A"
                req_date = st.date_input("Requested Date", value=datetime.today().date())
            origin = st.text_input("Origin Address")
            dest = st.selectbox("Destination Ramp", ramp_options)

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
                    "Destination": dest,
                    "Requested Date": req_date
                }
                st.session_state.last_result = schedule_customer(data)
                st.session_state.show_form = False
    else:
        st.success(st.session_state.last_result)
        if st.button("📋 Schedule Another"):
            st.session_state.last_result = ""
            st.session_state.show_form = True

    from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
import os

def add_to_calendar(summary, description, start_dt, end_dt):
    SCOPES = ['https://www.googleapis.com/auth/calendar.events']
    creds = None

    # Load token or authenticate
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())

    service = build('calendar', 'v3', credentials=creds)

    event = {
        'summary': summary,
        'description': description,
        'start': {
            'dateTime': start_dt.isoformat(),
            'timeZone': 'America/New_York',
        },
        'end': {
            'dateTime': end_dt.isoformat(),
            'timeZone': 'America/New_York',
        },
    }

    event = service.events().insert(calendarId='primary', body=event).execute()
    return f"📅 Google Calendar event created: {event.get('htmlLink')}"
    
