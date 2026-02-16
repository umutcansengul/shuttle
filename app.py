import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime, timedelta, date

# 1. SETUP THE PAGE
st.set_page_config(page_title="Shuttle App", page_icon="🚌", layout="wide")

# 2. CONNECT TO GOOGLE SHEETS (Crucial Step!)
# This MUST happen before we try to use 'conn' anywhere else
try:
    conn = st.connection("gsheets", type=GSheetsConnection)
except Exception as e:
    st.error("🚨 CRITICAL ERROR: Could not connect to Google Sheets.")
    st.error(f"Details: {e}")
    st.info("Did you add your secrets to the Streamlit Dashboard correctly?")
    st.stop() # Stop the app here if connection fails

# --- DEBUG MODE: READ ANYTHING ---
st.write("--- DIAGNOSTIC MODE ---")
try:
    # This reads the very first tab, no matter what it is named
    df = conn.read(ttl=0)
    st.success(f"✅ I successfully read the first tab!")
    st.write("Here are the columns I found:")
    st.write(df.columns.tolist())
    st.write("Here is the data:")
    st.dataframe(df)
except Exception as e:
    st.error(f"❌ Still failing. Detailed Error: {e}")
st.write("-----------------------")

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
    tab1, tab2, tab3 = st.tabs(["📅 Book a Ride", "🎟️ My Bookings", "🔒 Settings"])
    
    # 1. FETCH DATA
    schedule_df = get_data("Schedule")
    bookings_df = get_data("Bookings")
    
    # Clean up dates to ensure they match (YYYY-MM-DD)
    schedule_df['Date'] = pd.to_datetime(schedule_df['Date']).dt.strftime('%Y-%m-%d')
    if not bookings_df.empty:
        bookings_df['Date'] = pd.to_datetime(bookings_df['Date']).dt.strftime('%Y-%m-%d')

    with tab1:
        st.subheader("Shuttle Booking")
        
        # OFFICE SELECTION (Now the primary filter)
        office_sel = st.selectbox("Select Office", ["MMC", "MKI"])
        
        # DATE SELECTION
        # We start with a normal date picker
        date_sel = st.date_input("Select Date", min_value=date.today())
        date_str = date_sel.strftime('%Y-%m-%d')

        # --- THE RESTRICTION ENGINE ---
        # Find what the user has ALREADY booked for this specific day
        user_day_bookings = pd.DataFrame()
        if not bookings_df.empty:
            user_day_bookings = bookings_df[
                (bookings_df['Username'] == st.session_state['username']) & 
                (bookings_df['Date'] == date_str) &
                (bookings_df['Status'] != "Cancelled")
            ]

        # Check existing directions
        has_booked_to_office = not user_day_bookings[user_day_bookings['Direction'].str.contains("to Office")].empty
        has_booked_to_venlo = not user_day_bookings[user_day_bookings['Direction'].str.contains("to Venlo")].empty

        if has_booked_to_office and has_booked_to_venlo:
            st.error(f"🚫 You are fully booked for {date_str}. Both directions are reserved.")
        else:
            # Filter schedule for this office and date
            available_slots = schedule_df[
                (schedule_df['Date'] == date_str) & 
                (schedule_df['Office'] == office_sel) # Ensure your Schedule sheet has an 'Office' column!
            ]

            # Remove the directions the user has already booked
            if has_booked_to_office:
                available_slots = available_slots[~available_slots['Direction'].str.contains("to Office")]
                st.info("ℹ️ You already have a morning booking. Only return trips are shown.")
            if has_booked_to_venlo:
                available_slots = available_slots[~available_slots['Direction'].str.contains("to Venlo")]
                st.info("ℹ️ You already have a return booking. Only morning trips are shown.")

            if available_slots.empty:
                st.warning("No shuttles available for this selection.")
            else:
                # Combine Direction and Time for easy selection
                available_slots['Display'] = available_slots['Direction'] + " @ " + available_slots['Time']
                selection = st.selectbox("Available Shuttles", available_slots['Display'].unique())
                
                # Extract chosen row
                chosen_row = available_slots[available_slots['Display'] == selection].iloc[0]

                # 2 PM LOCKOUT
                is_late = (date_sel == date.today() + timedelta(days=1)) and (datetime.now().hour >= 14)

                if st.button("Book Seat"):
                    if is_late:
                        st.error("❌ Past 14:00 deadline for tomorrow's booking.")
                    else:
                        new_booking = pd.DataFrame([{
                            "Username": st.session_state['username'],
                            "Date": date_str,
                            "Office": office_sel,
                            "Direction": chosen_row['Direction'],
                            "Time": chosen_row['Time'],
                            "Status": "Confirmed",
                            "Timestamp": str(datetime.now())
                        }])
                        update_data(pd.concat([bookings_df, new_booking]), "Bookings")
                        st.success("✅ Seat Reserved!")
                        st.rerun()

    # (TAB 2 and TAB 3 remain the same as previous steps)
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
