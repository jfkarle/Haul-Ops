import streamlit as st
import pandas as pd
from datetime import datetime, timedelta, time
import os

st.set_page_config(page_title="ECM Scheduler: Crane Priority", layout="wide")

# --- DARK BACKGROUND ---
st.markdown(...)

# --- INIT SESSION STATE ---
if "current_day" not in st.session_state: ...
if "view_mode" not in st.session_state: ...

# --- NAVIGATION BUTTONS ---
col1, col2, col3 = st.columns([1,2,1])
with col1: ...
with col2: ...
with col3: ...

# --- BUILD CALENDAR FUNCTION ---
def build_calendar(start_date, view_mode):
    ...

# --- RENDER CALENDAR ---
st.markdown("### 📅 Current Schedule Overview")
cal = build_calendar(st.session_state.current_day, st.session_state.view_mode)
st.dataframe(cal)
