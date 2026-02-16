import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta, date

# --- CONFIGURATION ---
st.set_page_config(page_title="Shuttle App", page_icon="🚌", layout="wide")

# Connect to Google Sheets
# This looks for [connections.gsheets] in your .streamlit/secrets.toml
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("❌ Connection Error: Could not connect to Google Sheets. Please check your Secrets configuration.")
    st.stop()

# --- HELPER FUNCTIONS ---

def get_data(worksheet_name):
    """Fetches data from a specific worksheet."""
    try:
        # ttl=0 ensures we don't serve old cached data
        df = conn.read(worksheet=worksheet_name, ttl=0)
        return df
    except Exception as e:
        st.error(f"Error reading {worksheet_name}: {e}")
        return pd.DataFrame()

def update_data(df, worksheet_name):
    """Updates the worksheet with the provided DataFrame."""
    try:
        conn.update(worksheet=worksheet_name, data=df)
        st.cache_data.clear() # Clear cache to force reload next time
    except Exception as e:
        st.error(f"Error updating {worksheet_name}: {e}")

def login_user(username, password):
    """Verifies username and password against the Users sheet."""
    users = get_data("Users")
    if users.empty:
        return None
    
    # Ensure columns are strings to avoid type mismatch
    users['Username'] = users['Username'].astype(str)
    users['Password'] = users['Password'].astype(str)
    
    user_row = users[(users['Username'] == username) & (users['Password'] == password)]
    
    if not user_row.empty:
        return user_row.iloc[0]['Role']
    return None

def change_password(username, old_pass, new_pass):
    """Updates the password for a user."""
    users_df = get_data("Users")
    
    # Find user
    mask = (users_df['Username'] == username) & (users_df['Password'] == old_pass)
    
    if not users_df[mask].empty:
        # Update the password
        users_df.loc[mask, 'Password'] = new_pass
        update_data(users_df, "Users")
        return True, "✅ Password changed successfully!"
    else:
        return False, "❌ Old password is incorrect."

# --- UI SECTIONS ---

def login_screen():
    st.title("🚌 Shuttle App Login")
    
    with st.form("login_form"):
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
                st.error("Invalid username or password.")

def admin_dashboard():
    st.title("Admin Dashboard 🛠️")
    st.sidebar.write(f"Logged in as: **{st.session_state['username']}**")
    if st.sidebar.button("Logout"):
        st.session_state.clear()
        st.rerun()
    
    tab1, tab2, tab3 = st.tabs(["Manage Schedule", "All Bookings", "Manage Users"])
    
    # TAB 1: SCHEDULE
    with tab1:
        st.subheader("Add New Shuttle Time")
        with st.form("add_schedule"):
            col1, col2 = st.columns(2)
            with col1:
                d = st.date_input("Date", min_value=date.today())
                t = st.time_input("Time")
            with col2:
                direction = st.selectbox("Direction", ["Venlo -> Office", "Office -> Venlo"])
                cap = st.number_input("Capacity", value=20, step=1)
            
            if st.form_submit_button("Add to Schedule"):
                schedule_df = get_data("Schedule")
                new_row = pd.DataFrame([{
                    "Date": str(d),
                    "Direction": direction,
                    "Time": str(t),
                    "Capacity": cap
                }])
                updated_df = pd.concat([schedule_df, new_row], ignore_index=True)
                update_data(updated_df, "Schedule")
                st.success(f"Added shuttle for {d} at {t}")
        
        st.divider()
        st.subheader("Current Schedule")
        st.dataframe(get_data("Schedule"))

    # TAB 2: BOOKINGS
    with tab2:
        st.subheader("Master Passenger List")
        bookings = get_data("Bookings")
        st.dataframe(bookings)

    # TAB 3: USERS (Optional - just to view)
    with tab3:
        st.subheader("User List")
        st.dataframe(get_data("Users"))

def user_dashboard():
    st.title(f"Welcome, {st.session_state['username']} 👋")
    st.sidebar.button("Logout", on_click=lambda: st.session_state.clear())
    
    tab1, tab2, tab3 = st.tabs(["📅 Book a Ride", "🎟️ My Bookings", "🔒 Settings"])
    
    # TAB 1: BOOKING
    with tab1:
        st.subheader("Book a Seat")
        
        col1, col2 = st.columns(2)
        with col1:
            date_sel = st.date_input("Select Date", min_value=date.today())
        with col2:
            dir_sel = st.selectbox("Select Direction", ["Venlo -> Office", "Office -> Venlo"])
            
        # FETCH AND FILTER SCHEDULE
        schedule_df = get_data("Schedule")
        
        if not schedule_df.empty:
            # Convert date column to string for comparison
            schedule_df['Date'] = schedule_df['Date'].astype(str)
            
            # Filter logic
            valid_slots = schedule_df[
                (schedule_df['Date'] == str(date_sel)) & 
                (schedule_df['Direction'] == dir_sel)
            ]
            
            if valid_slots.empty:
                st.warning("⚠️ No shuttles found for this specific date and direction.")
            else:
                time_choice = st.selectbox("Select Time", valid_slots['Time'].unique())
                
                # 2 PM LOCKOUT LOGIC
                is_late = False
                # If booking for tomorrow...
                if date_sel == date.today() + timedelta(days=1):
                    # ...and it's after 14:00 (2 PM)
                    if datetime.now().hour >= 14:
                        is_late = True
                
                if st.button("Confirm Booking"):
                    if is_late:
                        st.error("❌ Booking for tomorrow is closed (Deadline: 14:00).")
                    else:
                        bookings_df = get_data("Bookings")
                        
                        # Check if already booked (Optional duplicate check)
                        # ... (Simple version skips this)
                        
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
                        st.balloons()
                        st.success("✅ Seat Confirmed! check 'My Bookings' tab.")
        else:
            st.error("Schedule database is empty.")

    # TAB 2: MY BOOKINGS
    with tab2:
        st.subheader("My Upcoming Rides")
        all_bookings = get_data("Bookings")
        
        if not all_bookings.empty:
            # Filter for logged-in user
            my_rides = all_bookings[all_bookings['Username'] == st.session_state['username']]
            
            if not my_rides.empty:
                st.dataframe(my_rides)
                st.info("To cancel, please contact admin (Cancellation feature coming soon).")
            else:
                st.info("You have no active bookings.")
        else:
            st.info("No bookings in system.")

    # TAB 3: SETTINGS
    with tab3:
        st.subheader("Change Password")
        with st.form("pass_change"):
            curr_pass = st.text_input("Current Password", type="password")
            new_pass1 = st.text_input("New Password", type="password")
            new_pass2 = st.text_input("Confirm New Password", type="password")
            
            if st.form_submit_button("Update Password"):
                if new_pass1 != new_pass2:
                    st.error("New passwords do not match.")
                elif len(new_pass1) < 4:
                    st.error("Password is too short.")
                else:
                    success, msg = change_password(st.session_state['username'], curr_pass, new_pass1)
                    if success:
                        st.success(msg)
                    else:
                        st.error(msg)

# --- MAIN APP ROUTER ---

if 'role' not in st.session_state:
    st.session_state['role'] = None

if st.session_state['role'] == 'admin':
    admin_dashboard()
elif st.session_state['role'] == 'user':
    user_dashboard()
else:
    login_screen()
