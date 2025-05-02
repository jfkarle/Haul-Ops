# ECM Scheduler - Capacity-Aware Version with Visual Truck Feedback
import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import os

# --- TRUCK CAPACITY RULES ---
def get_allowed_trucks(length_ft, boat_type):
    length = float(length_ft)
    if boat_type == "Sail":
        return [20, 21, 17]  # include crane truck for sails
    elif length > 40:
        return [20, 21]  # truck 23 is too small
    else:
        return [20, 21, 23]


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
if "allowed_trucks" not in st.session_state:
    st.session_state.allowed_trucks = [20, 21, 23]

# --- FORM INPUTS ---
st.markdown("""
    <style>
        .stTextInput>div>div>input,
        .stDateInput>div>input,
        .stSelectbox>div>div {
            width: 250px !important;
            padding: 8px;
            font-size: 16px;
        }
        .stTextArea textarea {
            width: 500px !important;
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

st.markdown('<div class="form-header">Schedule New Delivery</div>', unsafe_allow_html=True)

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
        bboat_type = st.selectbox("Boat Type", ["Select...", "Power", "Sail"])
        if boat_type == "Select...":
            st.warning("Please select a boat type.")


    origin = st.text_input("Origin Location")
    ramp = st.selectbox("Destination Ramp", [
        "Scituate", "Taylor", "Plymouth", "Duxbury", "Green Harbor", "Hingham", "Cohasset",
        "Sandwich", "Barnstable", "Dennis", "Chatham", "Harwich", "Hyannis", "Falmouth", "New Bedford"
    ])

    col5, col6 = st.columns(2)
    with col5:
        allowed_trucks = get_allowed_trucks(boat_length, boat_type) if boat_length and boat_type else []
        st.session_state.allowed_trucks = allowed_trucks
        if allowed_trucks:
            truck = st.selectbox("Select Truck", allowed_trucks)
        else:
            st.warning("Please enter Boat Length and Type first.")
            truck = None

    with col6:
        requested_date = st.date_input("Requested Delivery Date", value=datetime.today())

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
            overlaps = any(start < slot_end and end > slot_start for start, end in bookings)
            if not overlaps:
                slots.append((day, slot, truck_num))
                if len(slots) == 3:
                    return slots
    return slots

# --- CALENDAR BUILDER ---
def build_calendar(start_date, view_mode):
    timeslots = [time(8,0), time(9,30), time(11,0), time(12,30), time(14,0)]
    all_trucks = {20: "S20", 21: "S21", 23: "S23", 17: "S17"}
    trucks = [all_trucks[t] for t in all_trucks]
    allowed_truck_nums = st.session_state.get("allowed_trucks")
    if not allowed_truck_nums:
        allowed_truck_nums = [20, 21, 23, 17]  # safe default for powerboats

    
    if view_mode == "Day":
        days = [start_date]
    elif view_mode == "Week":
        days = [start_date + timedelta(days=i) for i in range(7)]
    else:
        days = [start_date + timedelta(days=i) for i in range(30)]

    columns = pd.MultiIndex.from_tuples(
        [(d.strftime('%a %b %d'), truck) for d in days for truck in trucks],
        names=["Day", "Truck"]
    )
    calendar = pd.DataFrame(index=[t.strftime('%-I:%M %p') for t in timeslots], columns=columns)

    # Show confirmed jobs
    for entry in st.session_state.schedule_log:
        label = f"{entry['Customer']}\n{entry['Boat Length']} {entry['Boat Type']}\n{entry['Origin']} → {entry['Ramp']}"
        col = (entry['Date'].strftime('%a %b %d'), entry['Truck'])
        row = entry['Start Time'].strftime('%-I:%M %p')
        calendar.at[row, col] = label

    # Mark proposed slots
    if st.session_state.proposed_slots:
        for d, t, tr_num in st.session_state.proposed_slots:
            col = (d.strftime('%a %b %d'), f"S{tr_num}")
            row = t.strftime('%-I:%M %p')
            calendar.at[row, col] = "🟢"

    # Mark invalid trucks
    for d in days:
        for t in timeslots:
            row = t.strftime('%-I:%M %p')
            for tr_num, label in all_trucks.items():
                col = (d.strftime('%a %b %d'), label)
                if col not in calendar.columns or pd.notna(calendar.at[row, col]):
                    continue
                if tr_num not in allowed_truck_nums:
                    if tr_num == 17:
                        calendar.at[row, col] = "❌ RED T"
                    else:
                        calendar.at[row, col] = "❌"

    return calendar

# --- SLOT HANDLING ---
if submit and customer_first and customer_last and boat_length and boat_type and origin and ramp:
    available_slots = []
    for t in allowed_trucks:
        available_slots += find_available_slots(t, requested_date)
    available_slots = sorted(available_slots)[:3]

    if available_slots:
        st.session_state.current_day = available_slots[0][0]
        st.session_state.view_mode = "Week"
        st.session_state.proposed_slots = available_slots
        st.session_state.pending_customer = {
            "Customer": f"{customer_first} {customer_last}",
            "Boat Length": boat_length,
            "Boat Type": boat_type,
            "Origin": origin,
            "Ramp": ramp,
            "Truck": truck
        }
    else:
        st.error("No available slots found!")

# --- SLOT CONFIRMATION ---
if st.session_state.proposed_slots and st.session_state.pending_customer:
    selected = st.radio(
        "Select a slot to confirm:",
        [f"{d.strftime('%B %d, %Y')} at {t.strftime('%-I:%M %p')} on S{tr}" for d, t, tr in st.session_state.proposed_slots]
    )
    if st.button("\u2705 Confirm Selection"):
        idx = [f"{d.strftime('%B %d, %Y')} at {t.strftime('%-I:%M %p')} on S{tr}" for d, t, tr in st.session_state.proposed_slots].index(selected)
        day, slot, truck = st.session_state.proposed_slots[idx]
        slot_start = datetime.combine(day, slot)
        slot_end = slot_start + timedelta(hours=1, minutes=30)

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
