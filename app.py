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
if 'package' not in st.session_state:
    st.session_state.package = 'free'
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
        
        # මෙතනදි අපි 'package' එකත් අරගන්නවා
        user_data = supabase.table("users").select("role, status, package").eq("id", user_id).execute()
        
        if user_data.data:
            if user_data.data[0]['status'] == 'banned':
                st.error("🚫 ඔබේ ගිණුම තහනම් කර ඇත!")
                return
                
            st.session_state.user = res.user
            st.session_state.role = user_data.data[0]['role']
            st.session_state.package = user_data.data[0].get('package', 'free') # Default to free if null
            
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

# --- BACKGROUND TASK ENGINE ---
def generate_app_background(app_id, final_source_link):
    try:
        supabase.table("generated_apps").update({"status": "processing"}).eq("id", app_id).execute()
        time.sleep(30) 
        generated_code = f"""# AI Generated App
# Source Data: {final_source_link}
import streamlit as st

st.set_page_config(page_title="Generated App")
st.title("My Awesome Generated App")
st.write("This app was created by AI App Factory!")
st.success("Successfully built from source!")
"""
        supabase.table("generated_apps").update({"status": "completed", "app_code": generated_code}).eq("id", app_id).execute()
    except Exception as e:
        supabase.table("generated_apps").update({"status": "failed"}).eq("id", app_id).execute()

# --- UI: APP GENERATOR DASHBOARD ---
def render_generator_dashboard():
    st.markdown("### 🛠️ App Generation Engine")
    
    # --- Package Limit Check ---
    res_count = supabase.table("generated_apps").select("id", count="exact").eq("owner_id", st.session_state.user.id).execute()
    app_count = res_count.count if res_count.count else 0
    
    max_apps = 1 if st.session_state.package == 'free' else (10 if st.session_state.package == 'silver' else 9999)
    
    st.info(f"ඔබගේ පැකේජය: **{st.session_state.package.upper()}** | සාදා ඇති Apps: **{app_count}/{'Unlimited' if max_apps == 9999 else max_apps}**")
    
    if app_count >= max_apps:
        st.error("⚠️ ඔබගේ පැකේජයේ උපරිම සීමාවට පැමිණ ඇත. තවත් Apps සෑදීමට කරුණාකර ඔබගේ පැකේජය Upgrade කරන්න.")
        return # Form එක පෙන්වන්නේ නෑ
    # ---------------------------

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
            
            if upload_option == "📁 File එකක් Upload කිරීම" and uploaded_file:
                with st.spinner("☁️ File එක Cloud එකට Upload වෙමින් පවතී..."):
                    file_path = f"{st.session_state.user.id}/{int(time.time())}_{uploaded_file.name}"
                    file_bytes = uploaded_file.getvalue()
                    supabase.storage.from_("app_sources").upload(file_path, file_bytes)
                    final_source_link = supabase.storage.from_("app_sources").get_public_url(file_path)
            else:
                final_source_link = source_link

            res = supabase.table("generated_apps").insert({
                "owner_id": st.session_state.user.id,
                "app_name": app_name,
                "source_link": final_source_link,
                "is_visible": not is_private,
                "status": "pending"
            }).execute()
            
            if res.data:
                app_id = res.data[0]['id']
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

# --- UI: UPGRADE PACKAGE (USER) ---
def render_upgrade_section():
    st.markdown("### 💳 Upgrade Your Package")
    st.write("ඔබගේ ව්‍යාපාරය දියුණු කරගැනීම සඳහා වඩාත් සුදුසු පැකේජයක් තෝරන්න.")
    
    col1, col2 = st.columns(2)
    with col1:
        st.info("**🥈 Silver Package**\n\n- Apps 10ක් සෑදිය හැක.\n- Price: Rs. 2,500")
    with col2:
        st.warning("**🥇 Gold Package**\n\n- අසීමිත Apps (Unlimited).\n- Price: Rs. 5,000")
        
    st.markdown("---")
    with st.form("payment_form"):
        selected_pkg = st.selectbox("මිලදී ගැනීමට අවශ්‍ය පැකේජය තෝරන්න:", ["silver", "gold"])
        slip_file = st.file_uploader("ඔබ මුදල් ගෙවූ Slip එක Upload කරන්න (Image/PDF)", type=['jpg', 'jpeg', 'png', 'pdf'])
        
        submitted = st.form_submit_button("Submit Payment", use_container_width=True)
        if submitted:
            if slip_file:
                with st.spinner("Uploading Slip..."):
                    file_path = f"{st.session_state.user.id}/{int(time.time())}_{slip_file.name}"
                    file_bytes = slip_file.getvalue()
                    # Upload to payment_slips bucket
                    supabase.storage.from_("payment_slips").upload(file_path, file_bytes)
                    slip_url = supabase.storage.from_("payment_slips").get_public_url(file_path)
                    
                    # Insert to payments table
                    supabase.table("payments").insert({
                        "user_id": st.session_state.user.id,
                        "package_name": selected_pkg,
                        "slip_url": slip_url,
                        "status": "pending"
                    }).execute()
                    
                st.success("✅ ඔබගේ ගෙවීම සාර්ථකව ඉදිරිපත් කරන ලදී. Admin විසින් එය අනුමත කළ පසු පැකේජය යාවත්කාලීන වනු ඇත.")
            else:
                st.error("කරුණාකර Slip එක Upload කරන්න.")

# --- UI: PAYMENT APPROVALS (OWNER/ADMIN) ---
def render_payment_approvals():
    st.markdown("### 💰 Pending Payment Approvals")
    
    # Get pending payments with user emails
    # Since we can't easily join auth.users in standard supabase client query easily, we will fetch payments
    payments_res = supabase.table("payments").select("*").eq("status", "pending").execute()
    
    if not payments_res.data:
        st.info("දැනට අනුමත කිරීමට කිසිදු ගෙවීමක් නොමැත.")
        return
        
    for pay in payments_res.data:
        with st.expander(f"Payment ID: #{pay['id']} - Request: {pay['package_name'].upper()}"):
            st.write(f"**User ID:** {pay['user_id']}")
            st.write(f"**Requested Package:** {pay['package_name'].upper()}")
            st.markdown(f"**Slip:** [Click here to view Slip]({pay['slip_url']})")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve", key=f"app_{pay['id']}", type="primary", use_container_width=True):
                    # 1. Update payment status
                    supabase.table("payments").update({"status": "approved"}).eq("id", pay['id']).execute()
                    # 2. Upgrade the user's package!
                    supabase.table("users").update({"package": pay['package_name']}).eq("id", pay['user_id']).execute()
                    st.success("Approved successfully!")
                    time.sleep(1)
                    st.rerun()
            with col2:
                if st.button("❌ Reject", key=f"rej_{pay['id']}", use_container_width=True):
                    supabase.table("payments").update({"status": "rejected"}).eq("id", pay['id']).execute()
                    st.error("Payment Rejected.")
                    time.sleep(1)
                    st.rerun()

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
    st.sidebar.info(f"🔑 Role: **{st.session_state.role.upper()}**\n\n📦 Pkg: **{st.session_state.package.upper()}**")
    
    if st.sidebar.button("Logout", type="primary"):
        supabase.auth.sign_out()
        st.session_state.user = None
        st.session_state.role = None
        st.session_state.package = 'free'
        st.rerun()

    # --- ROUTING ---
    if st.session_state.role == 'owner':
        st.title("👑 Owner Dashboard (Total Control)")
        tab1, tab2, tab3 = st.tabs(["🚀 App Generator", "💰 Payment Approvals", "⚙️ System Settings"])
        with tab1:
            render_generator_dashboard()
        with tab2:
            render_payment_approvals()
        with tab3:
            st.info("System Settings පසුව එකතු කෙරේ.")
            
    elif st.session_state.role == 'admin':
        st.title("🛡️ Admin Dashboard")
        tab1, tab2 = st.tabs(["🚀 App Generator", "💰 Payment Approvals"])
        with tab1:
            render_generator_dashboard()
        with tab2:
            render_payment_approvals()
        
    elif st.session_state.role in ['user', 'moderator']:
        st.title("🚀 User Dashboard")
        tab1, tab2 = st.tabs(["🚀 App Generator", "💳 Upgrade Package"])
        with tab1:
            render_generator_dashboard()
        with tab2:
            render_upgrade_section()
