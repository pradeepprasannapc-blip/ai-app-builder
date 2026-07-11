import streamlit as st
from supabase import create_client, Client
import socket
import uuid
import threading
import time

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

# --- HELPER FUNCTIONS ---
def get_user_ip():
    try:
        hostname = socket.gethostname()
        ip_address = socket.gethostbyname(hostname)
        return ip_address
    except:
        return "Unknown IP"

# --- AUTHENTICATION FUNCTIONS ---
def register(email, password):
    try:
        # Supabase Auth Sign Up
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            st.success("🎉 ලියාපදිංචිය සාර්ථකයි! කරුණාකර ඔබගේ Email එකට ගොස් ගිණුම Verify කරන්න.")
            
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
        error_msg = str(e)
        # Email verify කරලා නැති නම් එන පණිවිඩය අල්ලගමු
        if "Email not confirmed" in error_msg:
            st.warning("⚠️ කරුණාකර ඔබේ Email ගිණුමට ගොස් අපි එවූ ලින්ක් එක Click කර ගිණුම Verify කරන්න.")
        elif "Invalid login credentials" in error_msg:
            st.error("⚠️ Email හෝ Password වැරදියි.")
        else:
            st.error(f"⚠️ දෝෂයකි: {error_msg}")

# --- BACKGROUND TASK ENGINE (AI GENERATOR) ---
def generate_app_background(app_id, source_link):
    """මේක තමයි Timeout නොවී පසුබිමෙන් දුවන AI මොළය"""
    try:
        # 1. Status එක 'processing' කරන්න
        supabase.table("generated_apps").update({"status": "processing"}).eq("id", app_id).execute()
        
        # 2. මෙතන තමයි ඔයාගේ අනාගත AI Logic එක එන්නේ (Gemini/OpenAI API Call)
        # දැනට අපි මේක තත්පර 30ක් යන වැඩක් විදිහට හිතමු (Sleep)
        time.sleep(30) # AI එක හිතන වෙලාව
        
        # 3. AI එකෙන් ජෙනරේට් කරපු කේතය (Dummy Code for now)
        generated_code = f"""# AI Generated App from: {source_link}
import streamlit as st

st.set_page_config(page_title="Generated App")
st.title("My Awesome Generated App")
st.write("This app was created by AI App Factory!")
st.success("Successfully built from source!")
"""
        
        # 4. වැඩේ ඉවර වුණාම Database එකේ සේව් කිරීම (Completed)
        supabase.table("generated_apps").update({
            "status": "completed", 
            "app_code": generated_code
        }).eq("id", app_id).execute()
        
    except Exception as e:
        # මොනවා හරි අවුලක් ගියොත් Status එක 'failed' වෙනවා
        supabase.table("generated_apps").update({"status": "failed"}).eq("id", app_id).execute()

# --- UI: APP GENERATOR DASHBOARD ---
def render_generator_dashboard():
    st.markdown("### 🛠️ App Generation Engine")
    
    with st.form("app_gen_form"):
        app_name = st.text_input("App එකේ නම", placeholder="Ex: My E-commerce App")
        source_link = st.text_input("Zip File එකේ හෝ Repo එකේ ලින්ක් එක", placeholder="https://github.com/... හෝ GDrive Link")
        is_private = st.checkbox("මේ ඇප් එක හංගලා තියන්න (Private)", value=False)
        
        submitted = st.form_submit_button("🚀 Generate App", use_container_width=True)
        
        if submitted:
            if app_name and source_link:
                # 1. මුලින්ම Database එකේ 'pending' විදිහට සේව් කරනවා
                res = supabase.table("generated_apps").insert({
                    "owner_id": st.session_state.user.id,
                    "app_name": app_name,
                    "source_link": source_link,
                    "is_visible": not is_private,
                    "status": "pending"
                }).execute()
                
                if res.data:
                    app_id = res.data[0]['id']
                    
                    # 2. Background Thread එක පටන් ගන්නවා (UI එක හිරවෙන්නේ නෑ)
                    thread = threading.Thread(target=generate_app_background, args=(app_id, source_link))
                    thread.start()
                    
                    st.success("✅ ඔබගේ ඇප් එක සාදමින් පවතී! පහත ලැයිස්තුවෙන් තත්ත්වය බලාගන්න.")
                else:
                    st.error("Database Error: පද්ධතියේ දෝෂයක් ඇති විය.")
            else:
                st.error("කරුණාකර නම සහ ලින්ක් එක ලබා දෙන්න.")

    st.markdown("---")
    st.markdown("### 📂 ඔබගේ Apps")
    
    # Database එකෙන් යූසර්ගේ ඇප්ස් ටික අරගෙන පෙන්නනවා
    apps_data = supabase.table("generated_apps").select("*").eq("owner_id", st.session_state.user.id).order("created_at", desc=True).execute()
    
    if apps_data.data:
        for app in apps_data.data:
            with st.expander(f"📦 {app['app_name']} - Status: {app['status'].upper()}"):
                st.write(f"**Link:** {app['source_link']}")
                st.write(f"**Visibility:** {'Public' if app['is_visible'] else 'Private'}")
                
                if app['status'] == 'pending':
                    st.info("⏳ පෝලිමේ ඇත...")
                elif app['status'] == 'processing':
                    st.warning("⚙️ AI එක මගින් කේතය ලියමින් පවතී...")
                elif app['status'] == 'completed':
                    st.success("✅ සාර්ථකයි! පහතින් කේතය බලාගන්න.")
                    st.code(app['app_code'], language='python')
                elif app['status'] == 'failed':
                    st.error("❌ දෝෂයකි. කරුණාකර නැවත උත්සාහ කරන්න.")
                
                # Refresh බොත්තම
                if st.button("🔄 Refresh Status", key=f"ref_{app['id']}"):
                    st.rerun()
    else:
        st.info("ඔබ තවම කිසිදු ඇප් එකක් සාදා නැත.")


# ==========================================
#               MAIN UI LOGIC
# ==========================================

# --- NOT LOGGED IN ---
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

# --- LOGGED IN ---
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
        tab1, tab2, tab3 = st.tabs(["🚀 App Generator", "👥 User Management", "⚙️ System Settings"])
        with tab1:
            render_generator_dashboard()
        with tab2:
            st.info("User Management (Payment/Logs) පසුව එකතු කෙරේ.")
        with tab3:
            st.info("System Settings පසුව එකතු කෙරේ.")
            
    elif st.session_state.role == 'admin':
        st.title("🛡️ Admin Dashboard")
        st.write("Payment Approvals සහ යූසර් කළමනාකරණය.")
        render_generator_dashboard()
        
    elif st.session_state.role == 'moderator':
        st.title("👁️ Moderator Dashboard")
        st.write("Support Tickets සහ User Warnings මෙතැනින්.")
        
    elif st.session_state.role == 'user':
        st.title("🚀 App Generator Dashboard")
        render_generator_dashboard()
