
import streamlit as st
from datetime import datetime, timedelta, date, time
import pandas as pd
import os
import json
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

st.set_page_config(page_title="ECM Boat Scheduler", layout="centered")
st.title("🛥️ ECM Boat Scheduler Portal")

# ---------- CONFIG -----------
SCOPES = ['https://www.googleapis.com/auth/calendar.events']
CALENDAR_TIMEZONE = 'America/New_York'
TRUCKS = ['20', '21', '23']
CRANE_TRUCK = '17'
WORK_START = time(8, 0)
WORK_END = time(14, 30)
WEEKEND_ALLOWED_MONTHS = [5, 9]  # May, September
DURATION = {
    'Powerboat': timedelta(hours=1.5),
    'Sailboat': timedelta(hours=3)
}
TIDE_DATA_FILES = {
    'Scituate': 'Scituate_2025_Tide_Times.csv',
    'Cohasset': 'Cohasset_2025_Tide_Times.csv',
    'Plymouth': 'Plymouth_2025_Tide_Times.csv',
    'Duxbury': 'Duxbury_2025_Tide_Times.csv',
    'Hingham': 'Hingham_2025_Tide_Times.csv'
}

# ---------- STATE -----------
if "schedule_log" not in st.session_state:
    st.session_state.schedule_log = []
if "crane_assignments" not in st.session_state:
    st.session_state.crane_assignments = {}
if "truck_schedules" not in st.session_state:
    st.session_state.truck_schedules = {truck: {} for truck in TRUCKS}

# ---------- FUNCTIONS -----------
def get_high_tide(ramp, d):
    date_str = d.strftime("%B %d, %Y")
    harbor = ramp.strip().title()
    filename = TIDE_DATA_FILES.get(harbor, TIDE_DATA_FILES['Scituate'])
    if not os.path.exists(filename):
        return None
    df = pd.read_csv(filename)
    row = df[df['Date'] == date_str]
    if row.empty:
        return None
    return datetime.strptime(row.iloc[0]['High Tide'], '%I:%M %p').time()

def is_overlap(truck, d, start_time, end_time):
    day_str = d.strftime('%Y-%m-%d')
    if day_str not in st.session_state.truck_schedules[truck]:
        return False
    for (s, e) in st.session_state.truck_schedules[truck][day_str]:
        if max(s, start_time) < min(e, end_time):
            return True
    return False

def add_to_calendar(summary, description, start_dt, end_dt):
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    else:
        flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
        creds = flow.run_console()
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    service = build('calendar', 'v3', credentials=creds)
    event = {
        'summary': summary,
        'description': description,
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': CALENDAR_TIMEZONE},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': CALENDAR_TIMEZONE},
    }
    event = service.events().insert(calendarId='primary', body=event).execute()
    return f"📅 Event created: {event.get('htmlLink')}"

def schedule_customer(data):
    d = pd.to_datetime(data['Requested Date']).date()
    ramp = data['Destination'].strip()
    truck = data['Truck']
    boat_type = data['Boat Type']
    duration = DURATION[boat_type]
    high_tide = get_high_tide(ramp, d)
    if high_tide is None:
        return "❌ No tide data found for this destination and date."
    start_window = datetime.combine(d, WORK_START)
    end_window = datetime.combine(d, WORK_END) - duration
    tide_time = datetime.combine(d, high_tide)
    cursor = max(start_window, tide_time - duration / 2)
    while cursor <= end_window:
        end_time = cursor + duration
        if not is_overlap(truck, d, cursor.time(), end_time.time()):
            if boat_type == 'Sailboat':
                if ramp in st.session_state.crane_assignments and st.session_state.crane_assignments[ramp] != d:
                    cursor += timedelta(minutes=15)
                    continue
                if any(day == d and r != ramp for r, day in st.session_state.crane_assignments.items()):
                    cursor += timedelta(minutes=15)
                    continue
                st.session_state.crane_assignments[ramp] = d
            day_str = d.strftime('%Y-%m-%d')
            st.session_state.truck_schedules[truck].setdefault(day_str, []).append((cursor.time(), end_time.time()))
            st.session_state.schedule_log.append({
                "Customer": data["Customer Name"],
                "Date": d.strftime('%B %d, %Y'),
                "Start": cursor.strftime('%-I:%M %p'),
                "End": end_time.strftime('%-I:%M %p'),
                "Truck": truck,
                "Crane": "Yes" if boat_type == 'Sailboat' else "No",
                "Ramp": ramp,
                "High Tide": tide_time.strftime('%-I:%M %p')
            })
            calendar_msg = add_to_calendar(
                summary=f"Hauling: {data['Customer Name']} → {data['Destination']}",
                description=f"Truck {truck}, Crane: {'Yes' if boat_type == 'Sailboat' else 'No'}",
                start_dt=cursor,
                end_dt=end_time
            )
            st.info(calendar_msg)
            return f"✅ Scheduled for {d.strftime('%B %d, %Y')} from {cursor.strftime('%-I:%M %p')} to {end_time.strftime('%-I:%M %p')}\nHigh Tide: {tide_time.strftime('%-I:%M %p')}, Truck: {truck}, Crane: {'Yes' if boat_type == 'Sailboat' else 'No'}"
        cursor += timedelta(minutes=15)
    return "❌ No valid time block available"

# ---------- UI -----------
st.header("📋 Enter New Boat")
with st.form("boat_form"):
    col1, col2 = st.columns(2)
    with col1:
        name = st.text_input("Customer Name")
        customer_type = st.selectbox("Customer Type", ["New", "Existing"])
        boat_type = st.selectbox("Boat Type", ["Powerboat", "Sailboat"])
        length = st.number_input("Length (ft)", 10, 100)
        draft = st.text_input("Keel Draft (ft)", "N/A")
        truck = st.selectbox("Truck", TRUCKS)
    with col2:
        origin = st.text_input("Origin Address")
        destination = st.selectbox("Destination Ramp", list(TIDE_DATA_FILES.keys()))
        request_date = st.date_input("Requested Date", value=date.today())
    submitted = st.form_submit_button("📆 Schedule Now")
    if submitted:
        data = {
            "Customer Name": name,
            "Customer Type": customer_type,
            "Boat Type": boat_type,
            "Length": length,
            "Draft": draft,
            "Truck": truck,
            "Origin": origin,
            "Destination": destination,
            "Requested Date": request_date
        }
        result = schedule_customer(data)
        st.success(result) if result.startswith("✅") else st.error(result)

# ---------- REPORT -----------
st.sidebar.title("📜 Scheduled Boats")
if st.sidebar.button("Refresh Report") or st.sidebar.checkbox("Show schedule"):
    df = pd.DataFrame(st.session_state.schedule_log)
    if not df.empty:
        st.sidebar.dataframe(df)
    else:
        st.sidebar.info("No boats scheduled yet.")
