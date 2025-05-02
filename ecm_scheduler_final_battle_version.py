
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import os

# --- PAGE CONFIG ---
st.set_page_config(page_title="ECM Scheduler: Crane Priority", layout="wide")




# --- SESSION STATE INIT ---
if "current_day" not in st.session_state:
    st.session_state.current_day = datetime.today().date()
if "view_mode" not in st.session_state:
    st.session_state.view_mode = "Week"
if "schedule_log" not in st.session_state:
    st.session_state.schedule_log = []
if "truck_bookings" not in st.session_state:
    st.session_state.truck_bookings = {20: {}, 21: {}, 23: {}, 17: {}}
if "proposed_slots" not in st.session_state:
    st.session_state.proposed_slots = []
if "pending_customer" not in st.session_state:
    st.session_state.pending_customer = None

# --- FORM INPUTS ---
st.markdown("""
    <style>
        .stTextInput>div>div>input {
            padding: 8px;
            font-size: 16px;
        }
        .stDateInput>div>input {
            padding: 8px;
        }
        .stTextArea textarea {
            padding: 10px;
            font-size: 15px;
        }
        .form-header {
            font-size: 22px;
            font-weight: bold;
            color: #C0392B;
            margin-bottom: 10px;
        }
    </style>
""", unsafe_allow_html=True)

st.markdown('<div class="form-header">📋 Schedule New Delivery</div>', unsafe_allow_html=True)

with st.form("customer_form"):
    col1, col2 = st.columns(2)
    with col1:
        customer_first = st.text_input("First Name")
    with col2:
        customer_last = st.text_input("Last Name")

    col3, col4 = st.columns(2)
    with col3:
        boat_length = st.text_input("Boat Length")
    with col4:
        boat_type = st.text_input("Boat Type")

    origin = st.text_input("Origin Location")
    ramp = st.selectbox("Destination Ramp", [
        "Scituate", "Taylor", "Plymouth", "Duxbury", "Green Harbor", "Hingham", "Cohasset",
        "Sandwich", "Barnstable", "Dennis", "Chatham", "Harwich", "Hyannis", "Falmouth", "New Bedford"
    ])

    col5, col6 = st.columns(2)
    with col5:
        truck = st.selectbox("Select Truck", [20, 21, 23])
    with col6:
        requested_date = st.date_input("Requested Delivery Date", value=datetime.today())

    st.markdown("### ⭐ How satisfied are you with the project?")
    satisfaction = st.radio("",
        ["⭐", "⭐⭐", "⭐⭐⭐", "⭐⭐⭐⭐", "⭐⭐⭐⭐⭐"],
        index=4, horizontal=True)

    feedback = st.text_area("💬 Would you like to leave us some feedback?", placeholder="Your comments here...")

    submit = st.form_submit_button("Find Available Slots")


# --- SLOT FINDER FUNCTION ---
def find_available_slots(truck_num, requested_date):
    slots = []
    timeslots = [time(8,0), time(9,30), time(11,0), time(12,30), time(14,0)]
    for days_ahead in range(30):
        day = requested_date + timedelta(days=days_ahead)
        bookings = st.session_state.truck_bookings.get(truck_num, {}).get(day, [])
        for slot in timeslots:
            slot_start = datetime.combine(day, slot)
            slot_end = slot_start + timedelta(hours=1, minutes=30)
            overlaps = False
            for start, end in bookings:
                if start < slot_end and end > slot_start:
                    overlaps = True
                    break
            if not overlaps:
                slots.append((day, slot))
                if len(slots) == 3:
                    return slots
    return slots

# --- NAVIGATION BUTTONS ---
st.markdown("### 📅 Current Schedule Overview")

col1, col2, col3 = st.columns([1,2,1])
with col1:
    if st.button("⬅️ Previous"):
        if st.session_state.view_mode == "Day":
            st.session_state.current_day -= timedelta(days=1)
        elif st.session_state.view_mode == "Week":
            st.session_state.current_day -= timedelta(weeks=1)
        elif st.session_state.view_mode == "Month":
            st.session_state.current_day -= timedelta(days=30)
with col2:
    st.session_state.view_mode = st.selectbox("Select View Mode", ["Day", "Week", "Month"], index=["Day", "Week", "Month"].index(st.session_state.view_mode))
with col3:
    if st.button("Next ➡️"):
        if st.session_state.view_mode == "Day":
            st.session_state.current_day += timedelta(days=1)
        elif st.session_state.view_mode == "Week":
            st.session_state.current_day += timedelta(weeks=1)
        elif st.session_state.view_mode == "Month":
            st.session_state.current_day += timedelta(days=30)

# --- CALENDAR BUILDER ---
def build_calendar(start_date, view_mode):
    timeslots = [time(8,0), time(9,30), time(11,0), time(12,30), time(14,0)]
    trucks = ["S20", "S21", "S23", "S17"]
    days = []

    if view_mode == "Day":
        days = [start_date]
    elif view_mode == "Week":
        days = [start_date + timedelta(days=i) for i in range(7)]
    elif view_mode == "Month":
        days = [start_date + timedelta(days=i) for i in range(30)]

    columns = pd.MultiIndex.from_tuples(
        [(d.strftime('%a %b %d'), truck) for d in days for truck in trucks],
        names=["Day", "Truck"]
    )

    calendar = pd.DataFrame(index=[t.strftime('%-I:%M %p') for t in timeslots], columns=columns)

    scheduled_lookup = {}
    for entry in st.session_state.schedule_log:
        scheduled_lookup[(entry['Date'], entry['Start Time'], entry['Truck'])] = f"{entry['Customer']}\n{entry['Boat Length']} {entry['Boat Type']}\n{entry['Origin']} → {entry['Ramp']}"

    for truck_num, truck_label in zip([20, 21, 23, 17], trucks):
        for d in days:
            bookings = st.session_state.truck_bookings.get(truck_num, {}).get(d, [])
            for start, end in bookings:
                for slot_time in timeslots:
                    slot_dt = datetime.combine(d, slot_time)
                    if start <= slot_dt < end:
                        label = scheduled_lookup.get((d, slot_time, truck_label), "Scheduled")
                        calendar.at[slot_time.strftime('%-I:%M %p'), (d.strftime('%a %b %d'), truck_label)] = label

    if st.session_state.proposed_slots:
        for d, t in st.session_state.proposed_slots:
            for truck in trucks:
                col = (d.strftime('%a %b %d'), truck)
                row = t.strftime('%-I:%M %p')
                if col in calendar.columns and row in calendar.index:
                    if pd.isna(calendar.at[row, col]) or calendar.at[row, col] == '':
                        calendar.at[row, col] = "🟢"

    return calendar

# --- SLOT CONFIRMATION ---
if submit and customer_first and customer_last and boat_length and boat_type and origin and ramp:
    available_slots = find_available_slots(truck, requested_date)
    if available_slots:
        st.session_state.current_day = available_slots[0][0]  # <= put this first
        st.session_state.proposed_slots = available_slots
        st.session_state.pending_customer = {
            "Customer": f"{customer_first} {customer_last}",
            "Boat Length": boat_length,
            "Boat Type": boat_type,
            "Origin": origin,
            "Ramp": ramp,
            "Truck": truck
        }
        st.session_state.view_mode = "Week"  # or "Day"

    else:
        st.error("No available slots found!")

if st.session_state.proposed_slots and st.session_state.pending_customer:
    selected = st.radio("Select a slot to confirm:", [f"{d.strftime('%B %d, %Y')} at {t.strftime('%-I:%M %p')}" for d, t in st.session_state.proposed_slots])
    if st.button("✅ Confirm Selection"):
        idx = [f"{d.strftime('%B %d, %Y')} at {t.strftime('%-I:%M %p')}" for d, t in st.session_state.proposed_slots].index(selected)
        selected_slot = st.session_state.proposed_slots[idx]
        day, slot = selected_slot
        slot_start = datetime.combine(day, slot)
        slot_end = slot_start + timedelta(hours=1, minutes=30)

        truck = st.session_state.pending_customer["Truck"]
        if truck not in st.session_state.truck_bookings:
            st.session_state.truck_bookings[truck] = {}
        if day not in st.session_state.truck_bookings[truck]:
            st.session_state.truck_bookings[truck][day] = []
        st.session_state.truck_bookings[truck][day].append((slot_start, slot_end))

        st.session_state.schedule_log.append({
            "Customer": st.session_state.pending_customer["Customer"],
            "Boat Length": st.session_state.pending_customer["Boat Length"],
            "Boat Type": st.session_state.pending_customer["Boat Type"],
            "Origin": st.session_state.pending_customer["Origin"],
            "Ramp": st.session_state.pending_customer["Ramp"],
            "Truck": f"S{truck}",
            "Date": day,
            "Start Time": slot,
        })

        st.session_state.proposed_slots = []
        st.session_state.pending_customer = None
        st.success("Scheduled successfully!")

# --- CALENDAR RENDER ---
cal = build_calendar(st.session_state.current_day, st.session_state.view_mode)
st.dataframe(cal)
