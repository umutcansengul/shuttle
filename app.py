import streamlit as st
import pandas as pd
from datetime import date

# --- CONFIGURATION ---
ADMIN_PASSWORD = "secret_password"

# --- LOGIN SYSTEM (Simple) ---
# In a real app, you'd use Streamlit-Authenticator for secure Google Login
if 'role' not in st.session_state:
    st.session_state.role = None

def login():
    st.title("Shuttle App Login")
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if username == "admin" and password == ADMIN_PASSWORD:
            st.session_state.role = "admin"
            st.rerun()
        else:
            # Assume everyone else is a standard user
            st.session_state.role = "user"
            st.session_state.username = username
            st.rerun()

# --- INTERFACE 1: ADMIN PANEL ---
def admin_interface():
    st.sidebar.success("Logged in as Admin")
    st.title("Admin Dashboard 🚌")
    
    # 1. Manage Schedule
    st.subheader("Manage Weekly Schedule")
    # Here you would load the Google Sheet and let the admin edit it directly
    # st.data_editor(schedule_dataframe) would let you edit like Excel!
    
    # 2. View Passengers
    st.subheader("Passenger Manifest")
    # st.dataframe(passenger_list)

# --- INTERFACE 2: USER PANEL ---
def user_interface():
    st.sidebar.info(f"Welcome, {st.session_state.username}")
    st.title("Book Your Shuttle")

    # 1. Select Date
    selected_date = st.date_input("Date of Trip", min_value=date.today())
    
    # 2. Select Direction
    direction = st.radio("Direction", ["Venlo -> Office", "Office -> Venlo"])
    
    # 3. DYNAMIC LOGIC (The part Google Forms couldn't do!)
    # fetch_valid_times is a custom function that reads your Sheet
    valid_times = fetch_valid_times(selected_date, direction) 
    
    if not valid_times:
        st.error("No shuttle scheduled for this specific date/direction.")
    else:
        time = st.selectbox("Select Time", valid_times)
        
        if st.button("Confirm Booking"):
            # save_to_sheet(st.session_state.username, selected_date, time)
            st.success(f"Booked! {direction} at {time}")

# --- MAIN APP LOGIC ---
if st.session_state.role == "admin":
    admin_interface()
elif st.session_state.role == "user":
    user_interface()
else:
    login()
