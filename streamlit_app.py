import streamlit as st
import requests
import pandas as pd
from datetime import datetime, timedelta

# Ramp to Station ID mapping
RAMP_TO_STATION_ID = {
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
