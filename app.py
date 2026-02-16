import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta, date

# --- CONFIGURATION ---
st.set_page_config(page_title="Shuttle App", layout="wide")

# Connect to Google Sheets
conn = st.connection("gsheets", type=GSheetsConnection)

# --- HELPER FUNCTIONS ---
def change_password(username, old_pass, new_pass):
    # 1. Get all users
    users_df = get_data("Users")
    
    # 2. Find the specific user row
    # We verify the OLD password matches before changing anything
    user_idx = users_df.index[
        (users_df['Username'] == username) & 
        (users_df['Password'] == old_pass)
    ].tolist()
    
    if not user_idx:
        return False, "❌ Old password is incorrect."
    
    # 3. Update the password
    # We use .at to update a specific cell (Row Index, Column Name)
    users_df.at[user_idx[0], 'Password'] = new_pass
    
    # 4. Save back to Google Sheets
    update_data(users_df, "Users")
    return True, "✅ Password changed successfully!"

def get_data(worksheet_name):
    # Reads data and ensures it's fresh (ttl=0)
    return conn.read(worksheet=worksheet_name, ttl=0)

def update_data(df, worksheet_name):
    conn.update(worksheet=worksheet_name, data=df)
    st.cache_data.clear() # Clear cache to show updates immediately

def login_user(username, password):
    users = get_data("Users")
    # Simple check
    user_row = users[(users['Username'] == username) & (users['Password'] == password)]
    if not user_row.empty:
        return user_row.iloc[0]['Role']
    return None

# --- UI SECTIONS ---

def login_screen():
    st.header("🚌 Shuttle Login")
    with st.form("login"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In")
        
        if submitted:
            role = login_user(username, password)
            if role:
                st.session_state['role'] = role
                st.session_state['username'] = username
                st.rerun()
            else:
                st.error("Invalid username or password")

def admin_dashboard():
    st.title("Admin Dashboard 🛠️")
    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())
    
    tab1, tab2 = st.tabs(["Manage Schedule", "View Bookings"])
    
    with tab1:
        st.subheader("Add New Shuttle Time")
        with st.form("add_schedule"):
            d = st.date_input("Date")
            direction = st.selectbox("Direction", ["Venlo -> Office", "Office -> Venlo"])
            t = st.time_input("Time")
            cap = st.number_input("Capacity", value=20)
            
            if st.form_submit_button("Add Slot"):
                schedule_df = get_data("Schedule")
                new_row = pd.DataFrame([{
                    "Date": str(d),
                    "Direction": direction,
                    "Time": str(t),
                    "Capacity": cap
                }])
                updated_df = pd.concat([schedule_df, new_row], ignore_index=True)
                update_data(updated_df, "Schedule")
                st.success("Schedule Updated!")
                
    with tab2:
        st.subheader("All Bookings")
        bookings = get_data("Bookings")
        st.dataframe(bookings)

def user_dashboard():
    st.title(f"Welcome, {st.session_state['username']} 👋")
    
    # Create Tabs for cleaner UI
    tab1, tab2, tab3 = st.tabs(["🚌 Book a Ride", "📅 My Rides", "🔒 Settings"])
    
    # --- TAB 1: BOOKING (Existing Code) ---
    with tab1:
        st.subheader("Book a Ride")
        col1, col2 = st.columns(2)
        with col1:
            date_sel = st.date_input("Date of Trip", min_value=date.today())
        with col2:
            dir_sel = st.selectbox("Direction", ["Venlo -> Office", "Office -> Venlo"])
            
        schedule_df = get_data("Schedule")
        
        # Ensure 'Date' column is string for comparison
        schedule_df['Date'] = schedule_df['Date'].astype(str)
        
        valid_slots = schedule_df[
            (schedule_df['Date'] == str(date_sel)) & 
            (schedule_df['Direction'] == dir_sel)
        ]
        
        if valid_slots.empty:
            st.warning("No shuttles scheduled for this selection.")
        else:
            time_choice = st.selectbox("Select Time", valid_slots['Time'].unique())
            
            # 2 PM Check
            is_late = False
            # Check if booking is for tomorrow AND current time is past 14:00
            if date_sel == date.today() + timedelta(days=1):
                if datetime.now().hour >= 14:
                    is_late = True
            
            if st.button("Confirm Booking"):
                if is_late:
                    st.error("❌ It is past 14:00. Booking for tomorrow is closed.")
                else:
                    bookings_df = get_data("Bookings")
                    new_booking = pd.DataFrame([{
                        "Username": st.session_state['username'],
                        "Date": str(date_sel),
                        "Direction": dir_sel,
                        "Time": str(time_choice),
                        "Status": "Confirmed",
                        "Timestamp": str(datetime.now())
                    }])
                    updated_bookings = pd.concat([bookings_df, new_booking], ignore_index=True)
                    update_data(updated_bookings, "Bookings")
                    st.success("✅ Seat Confirmed!")

    # --- TAB 2: MY RIDES (Existing Code) ---
    with tab2:
        st.subheader("My Upcoming Rides")
        my_bookings = get_data("Bookings")
        if not my_bookings.empty:
            my_rides = my_bookings[my_bookings['Username'] == st.session_state['username']]
            st.dataframe(my_rides)
        else:
            st.info("No bookings found.")

    # --- TAB 3: SETTINGS (New Feature!) ---
    with tab3:
        st.subheader("Change Password")
        with st.form("pass_change_form"):
            current_pass = st.text_input("Current Password", type="password")
            new_pass_1 = st.text_input("New Password", type="password")
            new_pass_2 = st.text_input("Confirm New Password", type="password")
            
            if st.form_submit_button("Update Password"):
                if new_pass_1 != new_pass_2:
                    st.error("❌ New passwords do not match.")
                elif len(new_pass_1) < 4:
                    st.error("❌ Password must be at least 4 characters.")
                else:
                    # Call the function we wrote in Step 1
                    success, message = change_password(st.session_state['username'], current_pass, new_pass_1)
                    if success:
                        st.success(message)
                    else:
                        st.error(message)

    # Logout Button in Sidebar
    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())
# --- MAIN APP ROUTER ---
if 'role' not in st.session_state:
    login_screen()
elif st.session_state['role'] == 'admin':
    admin_dashboard()
else:
    user_dashboard()
