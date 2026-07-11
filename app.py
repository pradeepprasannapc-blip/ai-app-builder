import streamlit as st
from supabase import create_client, Client
import socket
import uuid

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
if 'device_id' not in st.session_state:
    # A simple device fingerprint placeholder
    st.session_state.device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, socket.gethostname()))

# --- AUTHENTICATION FUNCTIONS ---
def get_user_ip():
    try:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return ip_address
    except:
        return "Unknown IP"

def register(email, password):
    try:
        # Supabase Auth Sign Up
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            st.success("🎉 ලියාපදිංචිය සාර්ථකයි! දැන් Login වන්න.")
            
            # Log Device on Registration
            supabase.table("device_logs").insert({
                "user_id": res.user.id,
                "device_id": st.session_state.device_id,
                "ip_address": get_user_ip(),
                "country": "Sri Lanka" # Placeholder for Geolocation
            }).execute()
        else:
            st.error("ලියාපදිංචි වීමේ දෝෂයකි.")
    except Exception as e:
        if "User already registered" in str(e):
            st.warning("මෙම Email ලිපිනය දැනටමත් ලියාපදිංචි කර ඇත.")
        else:
            st.error(f"Error: {e}")

def login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user_id = res.user.id
        
        # Get User Role from our custom table
        user_data = supabase.table("users").select("role, status").eq("id", user_id).execute()
        
        if user_data.data:
            if user_data.data[0]['status'] == 'banned':
                st.error("🚫 ඔබේ ගිණුම තහනම් කර ඇත!")
                return
                
            st.session_state.user = res.user
            st.session_state.role = user_data.data[0]['role']
            st.success(f"සාර්ථකයි! {st.session_state.role.upper()} ලෙස ලොග් විය.")
            
            # Log Device on Login
            supabase.table("device_logs").insert({
                "user_id": user_id,
                "device_id": st.session_state.device_id,
                "ip_address": get_user_ip(),
                "country": "Sri Lanka"
            }).execute()
            
            st.rerun()
    except Exception as e:
        st.error("⚠️ Login අසාර්ථකයි. Email හෝ Password වැරදියි.")

# --- UI LOGIC (NOT LOGGED IN) ---
if not st.session_state.user:
    st.markdown("<h1 style='text-align: center; color: #4B4B4B;'>⚡ AI App Factory</h1>", unsafe_allow_html=True)
    st.markdown("<p style='text-align: center;'>Welcome to the Master App Generation Engine</p>", unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        
        with tab1:
            with st.form("login_form"):
                email = st.text_input("Email Address")
                password = st.text_input("Password", type="password")
                submitted = st.form_submit_button("Login to Dashboard", use_container_width=True)
                if submitted:
                    login(email, password)
                    
        with tab2:
            with st.form("register_form"):
                reg_email = st.text_input("Email Address")
                reg_password = st.text_input("Password", type="password")
                reg_confirm = st.text_input("Confirm Password", type="password")
                reg_submitted = st.form_submit_button("Create Account", use_container_width=True)
                if reg_submitted:
                    if reg_password == reg_confirm and len(reg_password) >= 6:
                        register(reg_email, reg_password)
                    elif len(reg_password) < 6:
                        st.error("Password එක අකුරු 6කට වඩා දිග විය යුතුය.")
                    else:
                        st.error("Passwords සමාන නොවේ.")

# --- UI LOGIC (LOGGED IN) ---
else:
    st.sidebar.title(f"Hi, {st.session_state.user.email}")
    st.sidebar.info(f"🔑 Role: **{st.session_state.role.upper()}**")
    
    if st.sidebar.button("Logout", type="primary"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.role = None
        st.rerun()

    # --- ROLE BASED ROUTING ---
    if st.session_state.role == 'owner':
        st.title("👑 Owner Dashboard (Total Control)")
        st.write("පද්ධතියේ සම්පූර්ණ පාලනය මෙතැනින්.")
        # We will add the App Generation and Admin panels here in the next steps
        
    elif st.session_state.role == 'admin':
        st.title("🛡️ Admin Dashboard")
        st.write("Payment Approvals සහ User Management මෙතැනින්.")
        
    elif st.session_state.role == 'moderator':
        st.title("👁️ Moderator Dashboard")
        st.write("Support Tickets සහ User Warnings මෙතැනින්.")
        
    elif st.session_state.role == 'user':
        st.title("🚀 App Generator Dashboard")
        st.write("Zip/Repo ලින්ක් එක ලබා දී ඇප් එක ජෙනරේට් කරන්න.")
