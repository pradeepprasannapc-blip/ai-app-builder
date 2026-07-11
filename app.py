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
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            st.success("🎉 ලියාපදිංචිය සාර්ථකයි! කරුණාකර ඔබගේ Email එකට ගොස් ගිණුම Verify කරන්න.")
            supabase.table("device_logs").insert({
                "user_id": res.user.id,
                "device_id": st.session_state.device_id,
                "ip_address": get_user_ip(),
                "country": "Sri Lanka"
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
        
        user_data = supabase.table("users").select("role, status").eq("id", user_id).execute()
        
        if user_data.data:
            if user_data.data[0]['status'] == 'banned':
                st.error("🚫 ඔබේ ගිණුම තහනම් කර ඇත!")
                return
                
            st.session_state.user = res.user
            st.session_state.role = user_data.data[0]['role']
            st.success(f"සාර්ථකයි! {st.session_state.role.upper()} ලෙස ලොග් විය.")
            
            supabase.table("device_logs").insert({
                "user_id": user_id,
                "device_id": st.session_state.device_id,
                "ip_address": get_user_ip(),
                "country": "Sri Lanka"
            }).execute()
            
            st.rerun()
    except Exception as e:
        error_msg = str(e)
        if "Email not confirmed" in error_msg:
            st.warning("⚠️ කරුණාකර ඔබේ Email ගිණුමට ගොස් අපි එවූ ලින්ක් එක Click කර ගිණුම Verify කරන්න.")
        elif "Invalid login credentials" in error_msg:
            st.error("⚠️ Email හෝ Password වැරදියි.")
        else:
            st.error(f"⚠️ දෝෂයකි: {error_msg}")

# --- BACKGROUND TASK ENGINE (AI GENERATOR) ---
def generate_app_background(app_id, final_source_link):
    """Timeout නොවී පසුබිමෙන් දුවන AI මොළය"""
    try:
        # 1. Processing
        supabase.table("generated_apps").update({"status": "processing"}).eq("id", app_id).execute()
        
        # 2. AI Thinking time
        time.sleep(30) 
        
        # 3. Dummy Code Generation
        generated_code = f"""# AI Generated App
# Source Data: {final_source_link}
import streamlit as st

st.set_page_config(page_title="Generated App")
st.title("My Awesome Generated App")
st.write("This app was created by AI App Factory!")
st.success("Successfully built from source!")
"""
        
        # 4. Completed
        supabase.table("generated_apps").update({
            "status": "completed", 
            "app_code": generated_code
        }).eq("id", app_id).execute()
        
    except Exception as e:
        supabase.table("generated_apps").update({"status": "failed"}).eq("id", app_id).execute()

# --- UI: APP GENERATOR DASHBOARD ---
def render_generator_dashboard():
    st.markdown("### 🛠️ App Generation Engine")
    
    app_name = st.text_input("App එකේ නම", placeholder="Ex: My E-commerce App")
    upload_option = st.radio("Source එක ලබා දෙන ආකාරය තෝරන්න:", ["🔗 Link එකක් ලබා දීම", "📁 File එකක් Upload කිරීම"], horizontal=True)
    
    source_link = ""
    uploaded_file = None
    
    if upload_option == "🔗 Link එකක් ලබා දීම":
        source_link = st.text_input("Zip File එකේ හෝ Repo එකේ ලින්ක් එක", placeholder="https://github.com/... හෝ GDrive Link")
    else:
        uploaded_file = st.file_uploader("ඔබගේ File එක තෝරන්න (Zip, Py, Txt)", type=['zip', 'txt', 'py'])
        
    is_private = st.checkbox("මේ ඇප් එක හංගලා තියන්න (Private)", value=False)
    
    if st.button("🚀 Generate App", use_container_width=True, type="primary"):
        if app_name and (source_link or uploaded_file):
            
            final_source_link = ""
            
            # --- CLOUD UPLOAD LOGIC ---
            if upload_option == "📁 File එකක් Upload කිරීම" and uploaded_file:
                with st.spinner("☁️ File එක Cloud එකට Upload වෙමින් පවතී..."):
                    # ෆයිල් එකේ නමට වෙලාව එකතු කරනවා (එකම නම තියෙන ෆයිල් ගැටෙන්නේ නැති වෙන්න)
                    file_path = f"{st.session_state.user.id}/{int(time.time())}_{uploaded_file.name}"
                    file_bytes = uploaded_file.getvalue()
                    
                    # Supabase Storage එකට අප්ලෝඩ් කිරීම
                    supabase.storage.from_("app_sources").upload(file_path, file_bytes)
                    
                    # අප්ලෝඩ් කරපු ෆයිල් එකේ Public Link එක ලබා ගැනීම
                    final_source_link = supabase.storage.from_("app_sources").get_public_url(file_path)
            else:
                final_source_link = source_link
            # --------------------------

            # 1. Database එකේ 'pending' විදිහට සේව් කරනවා
            res = supabase.table("generated_apps").insert({
                "owner_id": st.session_state.user.id,
                "app_name": app_name,
                "source_link": final_source_link,
                "is_visible": not is_private,
                "status": "pending"
            }).execute()
            
            if res.data:
                app_id = res.data[0]['id']
                
                # 2. Background Thread එක පටන් ගන්නවා
                thread = threading.Thread(target=generate_app_background, args=(app_id, final_source_link))
                thread.start()
                
                st.success("✅ ඔබගේ ඇප් එක සාදමින් පවතී! පහත ලැයිස්තුවෙන් තත්ත්වය බලාගන්න.")
            else:
                st.error("Database Error: පද්ධතියේ දෝෂයක් ඇති විය.")
        else:
            st.error("කරුණාකර නම සහ ලින්ක් එක / File එක ලබා දෙන්න.")

    st.markdown("---")
    st.markdown("### 📂 ඔබගේ Apps")
    
    apps_data = supabase.table("generated_apps").select("*").eq("owner_id", st.session_state.user.id).order("created_at", desc=True).execute()
    
    if apps_data.data:
        for app in apps_data.data:
            with st.expander(f"📦 {app['app_name']} - Status: {app['status'].upper()}"):
                st.write(f"**Source:** {app['source_link']}")
                st.write(f"**Visibility:** {'Public' if app['is_visible'] else 'Private'}")
                
                if app['status'] == 'pending':
                    st.info("⏳ පෝලිමේ ඇත...")
                elif app['status'] == 'processing':
                    st.warning("⚙️ AI එක මගින් කේතය ලියමින් පවතී... (කරුණාකර මඳ වේලාවකින් Refresh කරන්න)")
                elif app['status'] == 'completed':
                    st.success("✅ සාර්ථකයි! පහතින් කේතය බලාගන්න.")
                    st.code(app['app_code'], language='python')
                elif app['status'] == 'failed':
                    st.error("❌ දෝෂයකි. කරුණාකර නැවත උත්සාහ කරන්න.")
                
                if st.button("🔄 Refresh Status", key=f"ref_{app['id']}"):
                    st.rerun()
    else:
        st.info("ඔබ තවම කිසිදු ඇප් එකක් සාදා නැත.")

# ==========================================
#               MAIN UI LOGIC
# ==========================================

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

else:
    st.sidebar.title(f"Hi, {st.session_state.user.email}")
    st.sidebar.info(f"🔑 Role: **{st.session_state.role.upper()}**")
    
    if st.sidebar.button("Logout", type="primary"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.role = None
        st.rerun()

    if st.session_state.role == 'owner':
        st.title("👑 Owner Dashboard (Total Control)")
        tab1, tab2, tab3 = st.tabs(["🚀 App Generator", "👥 User Management", "⚙️ System Settings"])
        with tab1:
            render_generator_dashboard()
        with tab2:
            st.info("User Management (Payment/Logs) පසුව එකතු කෙරේ.")
        with tab3:
            st.info("System Settings පසුව එකතු කෙරේ.")
            
    elif st.session_state.role == 'admin':
        st.title("🛡️ Admin Dashboard")
        render_generator_dashboard()
        
    elif st.session_state.role == 'moderator':
        st.title("👁️ Moderator Dashboard")
        st.info("Support Tickets සහ User Warnings මෙතැනින්.")
        
    elif st.session_state.role == 'user':
        st.title("🚀 App Generator Dashboard")
        render_generator_dashboard()
