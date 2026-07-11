import streamlit as st
from supabase import create_client, Client

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="AI App Factory - Master Core", layout="wide")

# --- SUPABASE SETUP ---
SUPABASE_URL = st.secrets["SUPABASE_URL"]
SUPABASE_KEY = st.secrets["SUPABASE_KEY"]
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- SESSION STATE ---
if 'user' not in st.session_state:
    st.session_state.user = None
if 'role' not in st.session_state:
    st.session_state.role = None

# --- AUTHENTICATION FUNCTIONS ---
def login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user_id = res.user.id
        
        # Get User Role from our custom table
        user_data = supabase.table("users").select("role, status").eq("id", user_id).execute()
        
        if user_data.data:
            if user_data.data[0]['status'] == 'banned':
                st.error("ඔබේ ගිණුම තහනම් කර ඇත!")
                return
                
            st.session_state.user = res.user
            st.session_state.role = user_data.data[0]['role']
            st.success(f"සාර්ථකයි! {st.session_state.role.upper()} ලෙස ලොග් විය.")
            st.rerun()
    except Exception as e:
        st.error("Login අසාර්ථකයි. කරුණාකර නැවත උත්සාහ කරන්න.")

# --- UI LOGIC ---
if not st.session_state.user:
    st.title("⚡ AI App Factory - Login")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Login")
        if submitted:
            login(email, password)
else:
    st.sidebar.title(f"Welcome, {st.session_state.role.capitalize()}")
    if st.sidebar.button("Logout"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.role = None
        st.rerun()

    # --- ROLE BASED ROUTING ---
    if st.session_state.role == 'owner':
        st.title("👑 Owner Dashboard (Total Control)")
        st.info("පද්ධතියේ සම්පූර්ණ පාලනය මෙතැනින්.")
        # Owner features will go here
        
    elif st.session_state.role == 'admin':
        st.title("🛡️ Admin Dashboard")
        st.info("Payment Approvals සහ User Management මෙතැනින්.")
        
    elif st.session_state.role == 'moderator':
        st.title("👁️ Moderator Dashboard")
        st.info("Support Tickets සහ User Warnings මෙතැනින්.")
        
    elif st.session_state.role == 'user':
        st.title("🚀 App Generator Dashboard")
        st.info("Zip/Repo ලින්ක් එක ලබා දී ඇප් එක ජෙනරේට් කරන්න.")
