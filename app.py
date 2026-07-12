import streamlit as st
from supabase import create_client, Client
import socket
import uuid
import threading
import time
import random
from datetime import datetime, timedelta, timezone
import groq
from google import genai 

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="AI App Factory - Master Core", layout="wide")

# --- SUPABASE SETUP (FRONTEND) ---
SUPABASE_URL = st.secrets["SUPABASE_URL"].strip()
SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- SESSION STATE ---
if 'user' not in st.session_state:
    st.session_state.user = None
if 'role' not in st.session_state:
    st.session_state.role = None
if 'package' not in st.session_state:
    st.session_state.package = 'free'
if 'expires_at' not in st.session_state:
    st.session_state.expires_at = None
if 'device_id' not in st.session_state:
    st.session_state.device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, socket.gethostname()))
if 'show_toast' not in st.session_state:
    st.session_state.show_toast = True
if 'worker_started' not in st.session_state:
    st.session_state.worker_started = False

# --- HELPER FUNCTIONS ---
def get_user_ip():
    try:
        return socket.gethostbyname(socket.gethostname())
    except:
        return "Unknown IP"

def trigger_social_proof():
    if st.session_state.show_toast:
        messages = [
            "🔥 අද දින 50+ දෙනෙක් සාර්ථකව Apps සාදා ඇත!",
            "🎉 කොළඹින් අලුත් පරිශීලකයෙක් Gold පැකේජය ලබා ගත්තා!",
            "🚀 මේ මොහොතේත් සිස්ටම් එකේ Apps 12ක් හැදෙමින් පවතී...",
            "💡 Silver පැකේජයේ අද දවසේ විශේෂ 20% ක වට්ටමක්!"
        ]
        st.toast(random.choice(messages), icon="🔔")
        st.session_state.show_toast = False 

# --- AI GENERATOR ENGINE (BULLETPROOF WORKER WITH MEMORY) ---
def process_single_app(app_data, groq_key, gemini_key, supa_url, supa_service_key):
    db = create_client(supa_url, supa_service_key)
    app_id = app_data['id']
    
    try:
        db.table("generated_apps").update({"status": "processing"}).eq("id", app_id).execute()
        
        full_prompt = f"""
        You are an expert Python Streamlit developer. 
        App Name: {app_data['app_name']}
        Reference: {app_data['source_link']}
        
        REQUIREMENTS:
        1. Use visually appealing Streamlit UI components (columns, expanders, etc.).
        2. Output ONLY the raw Python code. Do not include markdown formatting like ```python.
        3. Do not explain the code. Just output the python script.
        4. IMPORTANT: Do NOT use non-existent Streamlit commands like `st.footer()`. Stick only to standard, valid Streamlit API methods.
        """
        
        if app_data.get('app_code'):
            full_prompt += f"\n\n--- CURRENT CODE ---\n{app_data['app_code']}\n"
            
        chat_hist = app_data.get('chat_history') or []
        if chat_hist:
            full_prompt += "\n--- REQUESTED CHANGES (APPLY THESE TO CURRENT CODE) ---\n"
            for msg in chat_hist:
                if msg['role'] == 'user':
                    full_prompt += f"User: {msg['content']}\n"
            full_prompt += "\nPlease rewrite the entire code applying these requested changes perfectly."
        else:
            full_prompt += "\nWrite the complete initial code."
            
        generated_code = ""

        if app_data.get('selected_model') == 'gemini':
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=full_prompt,
            )
            generated_code = response.text
        else:
            client = groq.Groq(api_key=groq_key)
            chat_completion = client.chat.completions.create(
                messages=[{"role": "user", "content": full_prompt}],
                model="llama-3.3-70b-versatile", 
            )
            generated_code = chat_completion.choices[0].message.content
            
        generated_code = generated_code.replace("```python", "").replace("```", "").strip()
        db.table("generated_apps").update({"status": "completed", "app_code": generated_code}).eq("id", app_id).execute()
        
    except Exception as e:
        error_msg = f"API Error: {str(e)}"
        db.table("generated_apps").update({"status": "failed", "app_code": error_msg}).eq("id", app_id).execute()
        print(f"Worker Error on {app_id}: {e}")

def background_recovery_worker():
    try:
        groq_key = st.secrets.get("GROQ_API_KEY", "").strip()
        gemini_key = st.secrets.get("GEMINI_KEY", "").strip() 
        
        supa_url = st.secrets["SUPABASE_URL"].strip()
        supa_service_key = st.secrets.get("SUPABASE_SERVICE_KEY", st.secrets["SUPABASE_KEY"]).strip()
        
        db = create_client(supa_url, supa_service_key)
        
        pending_apps = db.table("generated_apps").select("*").eq("status", "pending").execute()
        
        for app in pending_apps.data:
            process_single_app(app, groq_key, gemini_key, supa_url, supa_service_key)
    except Exception as e:
        print(f"Recovery Worker Failed: {e}")

if not st.session_state.worker_started:
    threading.Thread(target=background_recovery_worker, daemon=True).start()
    st.session_state.worker_started = True

# --- AUTH & AUTO-EXPIRE ENGINE ---
def login(email, password):
    try:
        res = supabase.auth.sign_in_with_password({"email": email, "password": password})
        user_id = res.user.id
        
        user_data = supabase.table("users").select("role, status, package, expires_at").eq("id", user_id).execute()
        
        if user_data.data:
            if user_data.data[0]['status'] == 'banned':
                st.error("🚫 ඔබේ ගිණුම තහනම් කර ඇත!")
                return
                
            current_pkg = user_data.data[0].get('package', 'free')
            expires_str = user_data.data[0].get('expires_at')
            
            if current_pkg != 'free' and expires_str:
                expire_date = datetime.fromisoformat(expires_str.replace('Z', '+00:00'))
                current_date = datetime.now(timezone.utc)
                if current_date > expire_date:
                    supabase.table("users").update({"package": "free", "expires_at": None}).eq("id", user_id).execute()
                    current_pkg = 'free'
                    expires_str = None
                    st.warning("⚠️ ඔබගේ පැකේජයේ කාල සීමාව අවසන් වී ඇති බැවින්, ගිණුම FREE පැකේජයට මාරු කර ඇත.")
                    time.sleep(2)

            st.session_state.user = res.user
            st.session_state.role = user_data.data[0]['role']
            st.session_state.package = current_pkg
            st.session_state.expires_at = expires_str
            st.session_state.show_toast = True 
            
            if current_pkg != 'free':
                st.success(f"සාර්ථකයි! {st.session_state.role.upper()} ලෙස ලොග් විය.")
            
            supabase.table("device_logs").insert({
                "user_id": user_id,
                "device_id": st.session_state.device_id,
                "ip_address": get_user_ip(),
                "country": "Sri Lanka"
            }).execute()
            
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
        else:
            st.error("ලියාපදිංචි වීමේ දෝෂයකි.")
    except Exception as e:
        st.error(f"Error: {e}")

# --- UI: APP GENERATOR DASHBOARD ---
def render_generator_dashboard():
    trigger_social_proof()
    
    st.markdown("### 🛠️ App Generation Engine")
    
    res_count = supabase.table("generated_apps").select("id", count="exact").eq("owner_id", st.session_state.user.id).execute()
    app_count = res_count.count if res_count.count else 0
    max_apps = 1 if st.session_state.package == 'free' else (10 if st.session_state.package == 'silver' else 9999)
    
    expiry_text = ""
    if st.session_state.package != 'free' and st.session_state.expires_at:
        exp_dt = datetime.fromisoformat(st.session_state.expires_at.replace('Z', '+00:00'))
        expiry_text = f" | ⏳ වලංගු දිනය: {exp_dt.strftime('%Y-%m-%d')}"
        
    st.info(f"📦 පැකේජය: **{st.session_state.package.upper()}**{expiry_text} | Apps: **{app_count}/{'Unlimited' if max_apps == 9999 else max_apps}**")
    
    if app_count >= max_apps:
        st.error("⚠️ උපරිම සීමාවට පැමිණ ඇත. තවත් Apps සෑදීමට කරුණාකර Upgrade කරන්න.")
        return 

    app_name = st.text_input("App එකේ නම", placeholder="Ex: My E-commerce App")
    
    col1, col2 = st.columns(2)
    with col1:
        upload_option = st.radio("Source එක ලබා දෙන ආකාරය:", ["🔗 Link එකක් ලබා දීම", "📁 File එකක් Upload කිරීම"], horizontal=True)
    with col2:
        ai_model_choice = st.radio("AI එන්ජිම තෝරන්න:", ["⚡ Groq (Fast)", "🧠 Gemini (Pro)"], horizontal=True)
        selected_model = "gemini" if "Gemini" in ai_model_choice else "groq"
    
    source_link = ""
    uploaded_file = None
    if upload_option == "🔗 Link එකක් ලබා දීම":
        source_link = st.text_input("ලින්ක් එක")
    else:
        uploaded_file = st.file_uploader("File එක තෝරන්න", type=['zip', 'txt', 'py'])
        
    is_private = st.checkbox("මේ ඇප් එක හංගලා තියන්න (Private)", value=False)
        
    if st.button("🚀 Generate App", use_container_width=True, type="primary"):
        if app_name and (source_link or uploaded_file):
            final_source_link = source_link
            if upload_option == "📁 File එකක් Upload කිරීම" and uploaded_file:
                with st.spinner("☁️ Uploading..."):
                    file_path = f"{st.session_state.user.id}/{int(time.time())}_{uploaded_file.name}"
                    supabase.storage.from_("app_sources").upload(file_path, uploaded_file.getvalue())
                    final_source_link = supabase.storage.from_("app_sources").get_public_url(file_path)

            res = supabase.table("generated_apps").insert({
                "owner_id": st.session_state.user.id, 
                "app_name": app_name, 
                "source_link": final_source_link, 
                "is_visible": not is_private, 
                "status": "pending",
                "selected_model": selected_model,
                "chat_history": [] 
            }).execute()
            
            if res.data:
                groq_key = st.secrets.get("GROQ_API_KEY", "").strip()
                gemini_key = st.secrets.get("GEMINI_KEY", "").strip()
                supa_url = st.secrets["SUPABASE_URL"].strip()
                supa_service_key = st.secrets.get("SUPABASE_SERVICE_KEY", st.secrets["SUPABASE_KEY"]).strip()
                
                threading.Thread(target=process_single_app, args=(res.data[0], groq_key, gemini_key, supa_url, supa_service_key), daemon=True).start()
                st.success(f"✅ ඔබගේ ඇප් එක {selected_model.upper()} AI මගින් පෝලිමට එක් කරන ලදී! පසුව පැමිණ තත්ත්වය පරීක්ෂා කරන්න.")
                time.sleep(2)
                st.rerun()
        else:
            st.error("කරුණාකර නම සහ ලින්ක් එක / File එක ලබා දෙන්න.")

    st.markdown("---")
    st.markdown("### 📂 ඔබගේ Apps")
    apps_data = supabase.table("generated_apps").select("*").eq("owner_id", st.session_state.user.id).order("created_at", desc=True).execute()
    if apps_data.data:
        for app in apps_data.data:
            with st.expander(f"📦 {app['app_name']} - Status: {app['status'].upper()}"):
                st.write(f"**Source:** {app['source_link']}")
                
                if app['status'] == 'pending':
                    st.info("⏳ පෝලිමේ ඇත...")
                elif app['status'] == 'processing':
                    st.warning("⚙️ AI එක මගින් කේතය ලියමින් පවතී... (කරුණාකර මඳ වේලාවකින් Refresh කරන්න)")
                elif app['status'] == 'completed':
                    st.success("✅ සාර්ථකයි! පහතින් කේතය වෙනස් කරන්න, Preview බලන්න හෝ AI එකෙන් උදව් ඉල්ලන්න.")
                    
                    current_code = app.get('app_code', '')
                    
                    tab_code, tab_preview = st.tabs(["🧑‍💻 Code Editor", "👁️ Live Preview"])
                    
                    with tab_code:
                        edited_code = st.text_area("මෙහි කේතය අතින් වෙනස් කළ හැක:", value=current_code, height=350, key=f"edit_{app['id']}")
                        if st.button("💾 Save Manual Changes", key=f"save_{app['id']}"):
                            if edited_code != current_code:
                                supabase.table("generated_apps").update({"app_code": edited_code}).eq("id", app['id']).execute()
                                st.success("වෙනස්කම් සාර්ථකව Save කළා!")
                                time.sleep(1)
                                st.rerun()
                                
                    with tab_preview:
                        st.info("💡 පහත බොත්තම ඔබා ඔබගේ ඇප් එකේ පෙරදසුනක් (Live Preview) මෙතනම බලාගන්න.")
                        if st.button("▶️ Run Preview", key=f"run_{app['id']}", type="primary"):
                            try:
                                safe_code = "\n".join([line for line in current_code.split('\n') if 'st.set_page_config' not in line and 'st.footer' not in line])
                                
                                st.markdown("### 📱 Live App Demo")
                                with st.container(border=True):
                                    exec(safe_code, globals(), {})
                            except Exception as e:
                                st.error(f"Preview එක Run කිරීමේදී දෝෂයක්: {e}")
                                
                    st.markdown("---")
                    
                    # --- CHAT TO BUILD INTERFACE ---
                    st.markdown("💬 **AI එකට කියලා තව කෑලි එකතු කරගන්න**")
                    chat_hist = app.get('chat_history') or []
                    for msg in chat_hist:
                        st.info(f"🧑‍💻 **ඔබ:** {msg['content']}")
                        
                    new_prompt = st.text_input("ඔබට අලුතින් එකතු කරගන්න/වෙනස් කරගන්න ඕන දේ මෙතන කියන්න...", placeholder="Ex: මට මේකට Login Page එකක් දාලා දෙන්න", key=f"prompt_{app['id']}")
                    
                    colA, colB = st.columns([1, 4])
                    with colA:
                        if st.button("🚀 Update with AI", key=f"ai_upd_{app['id']}", type="primary"):
                            if new_prompt:
                                new_hist = chat_hist + [{"role": "user", "content": new_prompt}]
                                res_update = supabase.table("generated_apps").update({
                                    "status": "pending",
                                    "chat_history": new_hist,
                                    "app_code": edited_code 
                                }).eq("id", app['id']).execute()
                                
                                # --- මෙන්න අර මට අමතක වෙච්ච MAGIC කෑල්ල (AI එක අවදි කිරීම)! ---
                                if res_update.data:
                                    groq_key = st.secrets.get("GROQ_API_KEY", "").strip()
                                    gemini_key = st.secrets.get("GEMINI_KEY", "").strip()
                                    supa_url = st.secrets["SUPABASE_URL"].strip()
                                    supa_service_key = st.secrets.get("SUPABASE_SERVICE_KEY", st.secrets["SUPABASE_KEY"]).strip()
                                    
                                    threading.Thread(target=process_single_app, args=(res_update.data[0], groq_key, gemini_key, supa_url, supa_service_key), daemon=True).start()
                                # -------------------------------------------------------------
                                
                                st.success("AI එක ඔබේ අලුත් ඉල්ලීම කියවමින් පවතී! Refresh කර බලන්න.")
                                time.sleep(2)
                                st.rerun()
                            else:
                                st.warning("කරුණාකර වෙනස්කම ටයිප් කරන්න.")
                                
                elif app['status'] == 'failed':
                    st.error(f"❌ {app.get('app_code', 'නැවත උත්සාහ කරන්න.')}")
                
                if st.button("🔄 Refresh Status", key=f"ref_{app['id']}"):
                    st.rerun()
    else:
        st.info("ඔබ තවම කිසිදු ඇප් එකක් සාදා නැත.")

# --- UI: UPGRADE PACKAGE (SMART OFFERS) ---
def render_upgrade_section():
    trigger_social_proof()
    st.markdown("### 💳 Upgrade Your Package")
    
    if st.session_state.package != 'free' and st.session_state.expires_at:
        exp_dt = datetime.fromisoformat(st.session_state.expires_at.replace('Z', '+00:00'))
        st.info(f"ℹ️ ඔබගේ වර්තමාන **{st.session_state.package.upper()}** පැකේජය **{exp_dt.strftime('%Y-%m-%d')}** දිනෙන් අවසන් වේ.")
        
    st.write("පහත පැකේජයන් සියල්ලම **දින 30ක (මාස 1ක)** වලංගු කාලයක් සඳහා ලබා දේ.")
    
    settings_res = supabase.table("system_settings").select("setting_value").eq("setting_key", "pricing").execute()
    pricing = settings_res.data[0]['setting_value'] if settings_res.data else {"silver_price": 2500, "silver_discount_pct": 20, "gold_price": 5000, "gold_discount_pct": 30}
    
    silver_orig = int(pricing['silver_price'] / (1 - (pricing['silver_discount_pct']/100)))
    silver_save = silver_orig - pricing['silver_price']
    
    gold_orig = int(pricing['gold_price'] / (1 - (pricing['gold_discount_pct']/100)))
    gold_save = gold_orig - pricing['gold_price']
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**🥈 Silver Package**\n\n- Apps 10ක් සෑදිය හැක.\n- ⏳ **වලංගු කාලය: දින 30යි**\n- Price: ~~Rs. {silver_orig}~~ **Rs. {pricing['silver_price']}**\n- 💸 ඔබ රු. {silver_save} ක් ඉතිරි කරයි! ({pricing['silver_discount_pct']}% OFF)")
    with col2:
        st.warning(f"**🥇 Gold Package**\n\n- අසීමිත Apps.\n- ⏳ **වලංගු කාලය: දින 30යි**\n- Price: ~~Rs. {gold_orig}~~ **Rs. {pricing['gold_price']}**\n- 💸 ඔබ රු. {gold_save} ක් ඉතිරි කරයි! ({pricing['gold_discount_pct']}% OFF)")
        
    st.markdown("---")
    with st.form("payment_form"):
        selected_pkg = st.selectbox("පැකේජය තෝරන්න (මාස 1ක වලංගු කාලයක් සහිතයි):", ["silver", "gold"])
        slip_file = st.file_uploader("Slip එක Upload කරන්න (Image/PDF)", type=['jpg', 'jpeg', 'png', 'pdf'])
        
        if st.form_submit_button("Submit Payment", use_container_width=True):
            if slip_file:
                with st.spinner("Uploading..."):
                    file_path = f"{st.session_state.user.id}/{int(time.time())}_{slip_file.name}"
                    supabase.storage.from_("payment_slips").upload(file_path, slip_file.getvalue())
                    slip_url = supabase.storage.from_("payment_slips").get_public_url(file_path)
                    
                    supabase.table("payments").insert({
                        "user_id": st.session_state.user.id, 
                        "package_name": selected_pkg, 
                        "slip_url": slip_url, 
                        "duration_days": 30, 
                        "status": "pending"
                    }).execute()
                st.success("✅ ඔබගේ ගෙවීම සාර්ථකව යවන ලදී. Admin විසින් අනුමත කළ පසු යාවත්කාලීන වනු ඇත.")
            else:
                st.error("කරුණාකර Slip එක Upload කරන්න.")

# --- UI: GOD MODE (OWNER ONLY) ---
def render_god_mode():
    st.markdown("### ⚡ God Mode (User Management)")
    st.write("ඕනෑම යූසර් කෙනෙකුගේ පැකේජය වෙනස් කිරීමට සහ Bonus දවස් ලබා දීමට මෙතැනින් හැක.")
    
    users_res = supabase.table("users").select("id, role, package, expires_at").execute()
    if users_res.data:
        for u in users_res.data:
            with st.expander(f"👤 User ID: {u['id'][:8]}... | Role: {u['role'].upper()} | Pkg: {u['package'].upper()}"):
                st.write(f"**Current Expiry:** {u['expires_at'] if u['expires_at'] else 'N/A'}")
                
                col1, col2 = st.columns(2)
                with col1:
                    pkg_options = ["free", "silver", "gold"]
                    current_index = pkg_options.index(u['package']) if u['package'] in pkg_options else 0
                    
                    new_pkg = st.selectbox(
                        "Change Package:", 
                        pkg_options, 
                        index=current_index,
                        key=f"pkg_{u['id']}"
                    )
                    
                    if st.button("Update Package", key=f"btn_pkg_{u['id']}"):
                        supabase.table("users").update({"package": new_pkg}).eq("id", u['id']).execute()
                        st.success(f"Package Updated to {new_pkg.upper()}!")
                        st.rerun()
                
                with col2:
                    bonus_days = st.number_input("Add Bonus Days:", min_value=1, max_value=365, value=7, key=f"days_{u['id']}")
                    if st.button("🎁 Give Bonus Days", key=f"btn_bns_{u['id']}"):
                        if u['expires_at']:
                            base_date = datetime.fromisoformat(u['expires_at'].replace('Z', '+00:00'))
                        else:
                            base_date = datetime.now(timezone.utc)
                            
                        new_expiry = (base_date + timedelta(days=bonus_days)).isoformat()
                        supabase.table("users").update({"expires_at": new_expiry}).eq("id", u['id']).execute()
                        st.success(f"Added {bonus_days} bonus days!")
                        st.rerun()
    else:
        st.info("Users හමු නොවීය.")

# --- UI: PAYMENT APPROVALS ---
def render_payment_approvals():
    st.markdown("### 💰 Pending Approvals")
    payments_res = supabase.table("payments").select("*").eq("status", "pending").execute()
    if not payments_res.data:
        st.info("අනුමත කිරීමට ගෙවීම් නොමැත.")
        return
    for pay in payments_res.data:
        duration = pay.get('duration_days', 30)
        with st.expander(f"Payment ID: #{pay['id']} - Pkg: {pay['package_name'].upper()} ({duration} Days)"):
            st.markdown(f"**Slip:** [Click here to view Slip]({pay['slip_url']})")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve", key=f"app_{pay['id']}", use_container_width=True, type="primary"):
                    supabase.table("payments").update({"status": "approved"}).eq("id", pay['id']).execute()
                    new_expiry_date = (datetime.now(timezone.utc) + timedelta(days=duration)).isoformat()
                    supabase.table("users").update({"package": pay['package_name'], "expires_at": new_expiry_date}).eq("id", pay['user_id']).execute()
                    st.success("Approved!")
                    time.sleep(1)
                    st.rerun()
            with col2:
                if st.button("❌ Reject", key=f"rej_{pay['id']}", use_container_width=True):
                    supabase.table("payments").update({"status": "rejected"}).eq("id", pay['id']).execute()
                    st.error("Rejected.")
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
        st.session_state.expires_at = None
        st.rerun()

    if st.session_state.role == 'owner':
        st.title("👑 Owner Dashboard")
        tab1, tab2, tab3 = st.tabs(["🚀 Generator", "💰 Approvals", "⚡ God Mode (Users)"])
        with tab1:
            render_generator_dashboard()
        with tab2:
            render_payment_approvals()
        with tab3:
            render_god_mode()
            
    elif st.session_state.role == 'admin':
        st.title("🛡️ Admin Dashboard")
        tab1, tab2 = st.tabs(["🚀 Generator", "💰 Approvals"])
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
