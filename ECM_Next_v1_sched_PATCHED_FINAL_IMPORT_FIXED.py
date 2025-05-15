import streamlit as st
import pandas as pd

CUSTOMER_CSV = "customers.csv"

try:
    customers_df = pd.read_csv(CUSTOMER_CSV)
    st.write("CSV Loaded Successfully")  # Add this line for confirmation
    st.dataframe(customers_df.head())  # Display the first few rows
except FileNotFoundError:
    st.error(f"Error: Could not find CSV file at '{CUSTOMER_CSV}'")
except pd.errors.EmptyDataError:
    st.error(f"Error: CSV file at '{CUSTOMER_CSV}' is empty")
except Exception as e:
    st.error(f"An unexpected error occurred while loading the CSV: {e}")
