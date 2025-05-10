# ECM Scheduler — NOAA + Ramp Buffers + Exportable Log
import streamlit as st
import requests
from datetime import datetime, timedelta
import pandas as pd
import io

RAMP_TO_STATION_ID = {
    "Sandwich": "8446493", "Plymouth": "8446493", "Cordage": "8446493",
    "Duxbury": "8446166", "Green Harbor": "8446009", "Taylor": "8446009",
    "Safe Harbor": "8446009", "Ferry Street": "8446009", "Marshfield": "8446009",
    "South River": "8446009", "Roht": "8446009", "Mary": "8446009",
    "Scituate": "8445138", "Cohasset": "8444762", "Hull": "8444762",
    "Hingham": "8444762", "Weymouth": "8444762"
}

RAMP_DISTANCE_FROM_PEMBROKE = {
    "Plymouth": 15, "Cordage": 14, "Duxbury": 12, "Green Harbor": 10, "Taylor": 10,
    "Safe Harbor": 10, "Ferry Street": 11, "Marshfield": 11, "South River": 12,
    "Roht": 11, "Mary": 11, "Scituate": 19, "Cohasset": 22, "Hull": 25,
    "Hingham": 23, "Weymouth": 24, "Sandwich": 35
}

RAMP_TO_RAMP_DISTANCE = {
    ("Scituate", "Cohasset"): 9, ("Scituate", "Plymouth"): 23,
    ("Green Harbor", "Duxbury"): 9, ("Marshfield", "Hull"): 18,
    ("Hull", "Weymouth"): 10, ("Scituate", "Green Harbor"): 14
}

TRUCK_LIMITS = {
    "S20": 60, "S21": 55, "S23": 30, "J17": 0
}

if "TRUCKS" not in st.session_state:
    st.session_state.TRUCKS = {"S20": [], "S21": [], "S23": []}
if "ALL_JOBS" not in st.session_state:
    st.session_state.ALL_JOBS = []
if "CRANE_JOBS" not in st.session_state:
    st.session_state.CRANE_JOBS = []

def get_station_for_ramp(ramp):
    for name, sid in RAMP_TO_STATION_ID.items():
        if name.lower() in ramp.lower():
            return sid
    return "8445138"

def is_busy_season(date):
    return date.month in [4, 5, 6, 9, 10]

def is_too_far_from_home(ramp, date):
    return is_busy_season(date) and RAMP_DISTANCE_FROM_PEMBROKE.get(ramp, 999) > 20

def is_too_far_between_ramps(r1, r2):
    if r1 == r2:
        return False
    return RAMP_TO_RAMP_DISTANCE.get((r1, r2), RAMP_TO_RAMP_DISTANCE.get((r2, r1), 999)) > 10

# Existing code continues below...

