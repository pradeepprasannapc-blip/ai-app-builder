import streamlit as st
from supabase import create_client
import time
import threading
import random
import re
import urllib.parse
import pg8000.native
import io
import zipfile
import requests
import textwrap
import base64
from datetime import datetime, timezone
import groq
from google import genai

import admin

def get_db(is_admin=False):
    if is_admin:
        return admin.get_admin_db()
    return create_client(st.secrets["SUPABASE_URL"].strip(), st.secrets["SUPABASE_KEY"].strip())

def trigger_social_proof():
    if st.session_state.get('show_toast', False):
        messages = [
            "🔥 අද දින 50+ දෙනෙක් සාර්ථකව Apps සාදා ඇත!",
            "🎉 කොළඹින් අලුත් පරිශීලකයෙක් Gold පැකේජය ලබා ගත්තා!",
            "🚀 මේ මොහොතේත් සිස්ටම් එකේ Apps 12ක් හැදෙමින් පවතී..."
        ]
        st.toast(random.choice(messages), icon="🔔")
        st.session_state.show_toast = False 

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
        # 🚨 Ultimate Dummy Data & Library Remover
        if 'supabase_url' in lower_line and '=' in lower_line: continue 
        if 'supabase_key' in lower_line and '=' in lower_line: continue 
        if 'supabase_secret' in lower_line and '=' in lower_line: continue 
        if 'your-supabase' in lower_line or 'your_supabase' in lower_line: continue
        if 'client =' in lower_line and 'supabase' in lower_line: continue
        if 'import bs4' in lower_line or 'from bs4' in lower_line or 'beautifulsoup' in lower_line: continue
        final_lines.append(line)
    return '\n'.join(final_lines).strip()

def fetch_github_context(url, github_token):
    if not github_token: 
        return ""
    match = re.search(r"github\.com/([^/]+)/([^/]+)", url)
    if not match: 
        return ""
    
    owner, repo = match.group(1), match.group(2).replace(".git", "")
    headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
    context = f"\n\n--- GITHUB REPOSITORY CONTEXT ({owner}/{repo}) ---\n"
    
    try:
        api_url = f"https://api.github.com/repos/{owner}/{repo}/git/trees/main?recursive=1"
        resp = requests.get(api_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            tree = resp.json().get("tree", [])
            allowed_extensions = ('.py', '.js', '.html', '.css', '.md', '.txt')
            relevant_files = [f for f in tree if f["type"] == "blob" and f["path"].endswith(allowed_extensions)]
            
            for file_info in relevant_files[:5]:
                file_url = f"https://api.github.com/repos/{owner}/{repo}/contents/{file_info['path']}"
                f_resp = requests.get(file_url, headers=headers, timeout=10)
                if f_resp.status_code == 200:
                    content_data = f_resp.json()
                    if "content" in content_data:
                        decoded_content = base64.b64decode(content_data["content"]).decode('utf-8', errors='ignore')
                        context += f"\nFile: {file_info['path']}\nCode:\n{decoded_content[:1500]}\n"
            context += "--- END OF GITHUB CONTEXT ---\n"
            return context
    except Exception as e:
        print(f"GitHub Fetch Error: {e}")
    return ""

def process_single_app(app_data, groq_key, gemini_key, supa_url, supa_service_key):
    db = create_client(supa_url, supa_service_key)
    app_id = app_data['id']
    
    try:
        db.table("generated_apps").update({"status": "processing"}).eq("id", app_id).execute()
        
        chat_hist = app_data.get('chat_history') or []
        last_user_prompt = app_data['source_link'] if app_data.get('source_link') else app_data['app_name']
        if chat_hist:
            for msg in chat_hist:
                if msg['role'] == 'user': 
                    last_user_prompt = msg['content']
                    
        safe_prefix = re.sub(r'[^a-zA-Z0-9]', '', str(app_data.get('app_name', 'app'))).lower()
        if not safe_prefix: safe_prefix = "custom_app"
        
        # 🪄 SUPER MAGIC: Ultimate Constraint Handling
        auth_instruction = ""
        user_prompt_lower = last_user_prompt.lower()
        if any(word in user_prompt_lower for word in ["ඕනි නෑ", "ඕනෙ නෑ", "එපා", "නොමැතිව", "no login", "no auth", "without login"]):
            auth_instruction = """
            ⛔⛔⛔ FATAL RULE: ZERO AUTHENTICATION ⛔⛔⛔
            THE USER STRICTLY COMMANDED: NO LOGIN AND NO REGISTRATION!
            - DO NOT CREATE 'Login' or 'Register' tabs.
            - DO NOT prompt for passwords.
            - DO NOT create user management functions.
            - DO NOT use `st.session_state.logged_in`.
            - START THE MAIN APP FEATURES IMMEDIATELY ON THE HOME SCREEN.
            - IF YOU GENERATE LOGIN CODE, THE SYSTEM WILL CRASH.
            """

        db_prompt = f"""
        You are an expert PostgreSQL Database Architect.
        The user wants an app based on this request: "{last_user_prompt}"
        
        {auth_instruction}
        
        Does this app need a database to store dynamic data (e.g., users, products, posts, tasks)?
        If YES: Write ONLY the PostgreSQL 'CREATE TABLE IF NOT EXISTS' statements required. 
        
        CRITICAL RULES FOR DB SCHEMA:
        1. NEVER name any table exactly 'users', 'payments', 'system_settings', 'device_logs', 'generated_apps', or 'app_versions'.
        2. You MUST prefix ALL tables for this app with '{safe_prefix}_' (e.g., '{safe_prefix}_videos').
        3. Ensure every table has an 'id' (UUID PRIMARY KEY DEFAULT gen_random_uuid()) and a 'created_at' column.
        4. If the user explicitly requested NO LOGIN, DO NOT create any user or auth tables.
        5. SECURITY BYPASS (CRITICAL): You MUST append these two lines for EVERY table you create:
           ALTER TABLE {safe_prefix}_<table_name> DISABLE ROW LEVEL SECURITY;
           GRANT ALL ON TABLE {safe_prefix}_<table_name> TO anon, authenticated, service_role;
        6. NO MARKDOWN. NO ```sql tags. Output purely raw SQL text separated by semicolons.
        
        If NO: Output EXACTLY the word: NO_DB
        """
        
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
                conn = pg8000.native.Connection(
                    user=parsed.username, password=db_pass, host=parsed.hostname, 
                    port=parsed.port or 5432, database=parsed.path.lstrip('/')
                )
                clean_sql = db_schema_sql.replace("```sql", "").replace("```", "").strip()
                sql_statements = [s.strip() for s in clean_sql.split(';') if s.strip()]
                for stmt in sql_statements:
                    conn.run(stmt)
                
                conn.run("NOTIFY pgrst, 'reload schema'")
                conn.close()
            except Exception as dbe: 
                print("DB Schema Execution Error:", dbe)
                pass
        
        # 🌟 RATE LIMIT PROTECTION MAGIC: Groq 429 Error Bypass
        time.sleep(6) 
                
        github_token = st.secrets.get("GITHUB_TOKEN", "")
        extra_context = ""
        if app_data.get('source_link') and "github.com" in app_data['source_link']:
            extra_context = fetch_github_context(app_data['source_link'], github_token)

        full_prompt = f"""
        You are an elite, world-class Python Streamlit developer and AI App Builder. Your ultimate task is to build a flawless, fully functional application.
        App Name: {app_data['app_name']}
        User Request / Link: {app_data['source_link']}
        
        {extra_context}
        
        CRITICAL RULES (VIOLATING THESE WILL CAUSE FATAL ERRORS):
        1. PURE PYTHON CODE ONLY. NO markdown. Start immediately with import streamlit as st.
        2. NO SUPABASE INITIALIZATION (CRITICAL): NEVER define `supabase_url`, `supabase_key` or use `create_client()`. The `supabase` object is ALREADY INJECTED globally. Use it directly.
        3. SUPABASE V2 SYNTAX (CRITICAL - AVOID 'SyncRequestBuilder' ERROR): 
           - To read or filter data, you MUST call `.select('*')` IMMEDIATELY after `.table('tbl')` BEFORE calling `.order()`, `.eq()`, or `.limit()`.
           - RIGHT: `data = supabase.table('tbl').select('*').order('created_at', desc=True).execute().data`
           - WRONG: `data = supabase.table('tbl').order('created_at').execute()` -> This causes 'SyncRequestBuilder' has no attribute 'order' error!
           - You MUST append `.execute()` to EVERY query.
        4. STRICT IMPORTS RULE (CRITICAL): You may ONLY import standard Python libraries and 'streamlit', 'requests', 'pandas', 'plotly'. YOU ARE STRICTLY FORBIDDEN from importing 'bs4', 'beautifulsoup4', 'numpy', or any other unapproved external library.
        5. UNIQUE KEYS: EVERY st.input/button MUST have a unique `key=`.
        6. TABS RULE: NEVER use `key=` in `st.tabs`.
        7. EXCEPTION HANDLING: Catch all errors using a generic `except Exception as e:`. NEVER import `supabase.exceptions`.
        8. 📱 MOBILE-FIRST PREMIUM UI/UX (EXTREMELY CRITICAL): 
            - The user expects a stunning, modern MOBILE APP interface (e.g., like a YouTube app clone).
            - DO NOT just use basic vertical inputs and text.
            - USE `st.columns` (e.g., `col1, col2 = st.columns(2)`) to create beautiful grids and media layouts.
            - USE `st.markdown` with custom CSS for beautiful video thumbnails, rich text, rounded corners, and spacing.
        """
        
        if db_schema_sql and "NO_DB" not in db_schema_sql.upper(): 
            full_prompt += f"\n\nDATABASE EXISTS. You MUST use EXACTLY these tables: \n{db_schema_sql}\n"
            
        if app_data.get('app_code'): 
            full_prompt += f"\n\n--- CURRENT CODE ---\n{app_data['app_code']}\n"
            
        if chat_hist:
            for msg in chat_hist:
                if msg['role'] == 'user': 
                    full_prompt += f"User: {msg['content']}\n"
            full_prompt += "\nPlease rewrite the entire code flawlessly while obeying ALL CRITICAL RULES. DO NOT OMIT ANY PREVIOUS FEATURES."
        else: 
            full_prompt += "\nWrite the complete initial code obeying ALL CRITICAL RULES. MAKE SURE IT IS 100% READY TO RUN AND BEAUTIFUL."

        full_prompt += f"\n\n{auth_instruction}"
            
        generated_code = ""
        if app_data.get('selected_model') == 'gemini':
            client = genai.Client(api_key=gemini_key)
            response = client.models.generate_content(model='gemini-2.5-flash', contents=full_prompt)
            generated_code = response.text
        else:
            client = groq.Groq(api_key=groq_key)
            chat_completion = client.chat.completions.create(messages=[{"role": "user", "content": full_prompt}], model="llama-3.3-70b-versatile")
            generated_code = chat_completion.choices[0].message.content
            
        generated_code = generated_code.replace("```python", "").replace("```", "").strip()
        
        db.table("generated_apps").update({"status": "completed", "app_code": generated_code}).eq("id", app_id).execute()
        try: 
            db.table("app_versions").insert({"app_id": app_id, "version_code": generated_code, "prompt_used": f"AI: {last_user_prompt}"}).execute()
        except Exception: 
            pass 
            
    except Exception as e:
        error_msg = str(e)
        # 🚨 User Friendly Error Translation
        if "429" in error_msg or "Rate limit" in error_msg:
            error_msg = "⚠️ API Rate Limit (429): AI එන්ජිමේ කාර්යබහුලත්වය නිසා සීමාව ඉක්මවා ඇත. කරුණාකර විනාඩියක් රැඳී සිට නැවත 'Update App with AI' බොත්තම ඔබන්න. නැතහොත් 'Gemini (Pro)' Model එක තෝරා අලුතින් App එකක් සාදන්න."
        else:
            error_msg = f"API Error: {error_msg}"
            
        db.table("generated_apps").update({"status": "failed", "app_code": error_msg}).eq("id", app_id).execute()

def background_recovery_worker():
    try:
        admin_db = admin.get_admin_db()
        pending_apps = admin_db.table("generated_apps").select("*").eq("status", "pending").execute()
        for app in pending_apps.data:
            groq_key = st.secrets.get("GROQ_API_KEY", "").strip()
            gemini_key = st.secrets.get("GEMINI_KEY", "").strip()
            supa_url = st.secrets["SUPABASE_URL"].strip()
            supa_key = st.secrets.get("SUPABASE_SERVICE_KEY", st.secrets["SUPABASE_KEY"]).strip()
            process_single_app(app, groq_key, gemini_key, supa_url, supa_key)
    except Exception: 
        pass

if not st.session_state.get('worker_started', False):
    threading.Thread(target=background_recovery_worker, daemon=True).start()
    st.session_state.worker_started = True

def render_app_card(app, is_admin=False):
    try:
        if not isinstance(app, dict):
            return
            
        prefix = f"adm_{app['id']}_" if is_admin else f"usr_{app['id']}_"
        status_val = app.get('status')
        status_str = str(status_val).upper() if status_val else "UNKNOWN"
        app_name_val = app.get('app_name')
        app_name_safe = str(app_name_val) if app_name_val else "Untitled"
        short_id = str(app['id'])[:8]
        
        header = f"📦 {app_name_safe} | Status: {status_str}"
        if is_admin:
            vis = app.get('is_visible')
            vis_text = "Public 👁️" if (vis is True or vis is None) else "Private 🔒"
            header += f" | Vis: {vis_text} | ID: {short_id}"

        with st.expander(header):
            if is_admin:
                colA, colB = st.columns(2)
                with colA:
                    vis = app.get('is_visible', True)
                    if st.button("🔴 Hide App" if vis else "🟢 Make Public", key=f"{prefix}vis"):
                        admin.get_admin_db().table("generated_apps").update({"is_visible": not vis}).eq("id", app['id']).execute()
                        st.rerun()
                with colB:
                    if st.button("🗑️ Force Delete App", key=f"{prefix}del", type="primary"):
                        admin.get_admin_db().table("generated_apps").delete().eq("id", app['id']).execute()
                        st.rerun()
                st.markdown("---")

            st.write(f"**Source:** {app.get('source_link', 'N/A')}")
            if app.get('android_version'): 
                st.caption(f"🤖 Android Target: {app.get('android_version')}")
            
            if status_str == 'PENDING': 
                st.info("⏳ පෝලිමේ ඇත...")
            elif status_str == 'PROCESSING': 
                st.warning("⚙️ AI එක මගින් කේතය ලියමින් පවතී... කරුණාකර රැඳී සිටින්න.")
            elif status_str == 'FAILED': 
                st.error(f"❌ {app.get('app_code', 'දෝෂයකි.')}")
                if st.button("🗑️ මේක මකලා අලුතින් හදන්න", key=f"{prefix}faildel"):
                    admin.get_admin_db().table("generated_apps").delete().eq("id", app['id']).execute()
                    st.rerun()
                    
            elif status_str == 'COMPLETED':
                current_code = app.get('app_code', '')
                tab_code, tab_preview, tab_history, tab_export = st.tabs(["🧑‍💻 Code Editor", "👁️ Live Preview", "⏪ History", "📥 Export & APK"])
                
                with tab_code:
                    edited_code = st.text_area("කේතය (Code):", value=current_code, height=350, key=f"{prefix}editor")
                    if st.button("💾 Save Changes", key=f"{prefix}save"):
                        if edited_code != current_code:
                            update_db = get_db(is_admin)
                            update_db.table("generated_apps").update({"app_code": edited_code}).eq("id", app['id']).execute()
                            try: 
                                update_db.table("app_versions").insert({"app_id": app['id'], "version_code": edited_code, "prompt_used": "Manual Edit"}).execute()
                            except Exception: 
                                pass 
                            st.success("වෙනස්කම් සාර්ථකව Save කළා!")
                            time.sleep(1)
                            st.rerun()
                            
                with tab_preview:
                    preview_active = st.toggle("👁️ Turn On Live Preview", key=f"{prefix}runprev")
                    if preview_active:
                        try:
                            safe_code = clean_python_code(current_code)
                            
                            # 📱 MOBILE SIMULATOR UI
                            st.markdown("<h4 style='text-align: center; color: #888;'>📱 Mobile View Simulator</h4>", unsafe_allow_html=True)
                            
                            spacer1, phone_col, spacer2 = st.columns([1, 1.2, 1])
                            
                            with phone_col:
                                # Top Notch HTML
                                st.markdown('''
                                    <div style="background-color: #1E1E1E; border-radius: 30px 30px 0 0; padding: 10px; text-align: center; border: 2px solid #333; border-bottom: none; margin-bottom: -15px; position: relative; z-index: 10;">
                                        <div style="width: 60px; height: 6px; background-color: #444; border-radius: 5px; display: inline-block;"></div>
                                    </div>
                                ''', unsafe_allow_html=True)
                                
                                # App Screen (Scrollable Container)
                                with st.container(height=700, border=True):
                                    exec_globals = globals().copy()
                                    if 'supabase' in exec_globals:
                                        del exec_globals['supabase']
                                    exec_globals['supabase'] = get_db(is_admin)
                                    exec_globals['__name__'] = '__main__'
                                    
                                    try:
                                        exec(safe_code, exec_globals)
                                    except Exception as inner_e:
                                        if 'PGRST205' in str(inner_e) or 'Could not find the table' in str(inner_e):
                                            st.warning("⏳ AI එක අලුත් දත්ත ගබඩාවක් (Database Table) නිර්මාණය කරමින් පවතී. කරුණාකර තත්පර 15කින් පමණ නැවත බලන්න.")
                                        else:
                                            st.error(f"Preview Error: {inner_e}")
                                            
                                # Bottom Bezel HTML
                                st.markdown('''
                                    <div style="background-color: #1E1E1E; border-radius: 0 0 30px 30px; height: 25px; border: 2px solid #333; border-top: none; margin-top: -15px;"></div>
                                ''', unsafe_allow_html=True)
                                
                        except Exception as e: 
                            st.error(f"Preview Initialization Error: {e}")
                            
                with tab_history:
                    try:
                        hist_db = get_db(is_admin)
                        v_res = hist_db.table("app_versions").select("*").eq("app_id", app['id']).order("created_at", desc=True).execute()
                        if v_res.data:
                            for idx, v in enumerate(v_res.data):
                                with st.container(border=True):
                                    v_time = v['created_at'][:19].replace('T', ' ')
                                    st.write(f"**Version {len(v_res.data) - idx}** | ⏰ {v_time}")
                                    st.caption(f"📝 {v.get('prompt_used', 'N/A')}")
                                    if st.button("🔄 Restore", key=f"{prefix}res_{v['id']}"):
                                        hist_db.table("generated_apps").update({"app_code": v['version_code']}).eq("id", app['id']).execute()
                                        st.rerun()
                        else: 
                            st.info("පෙර සංස්කරණ කිසිවක් හමු නොවීය.")
                    except Exception: 
                        pass
                
                with tab_export:
                    col1, col2 = st.columns(2)
                    with col1:
                        st.info("📱 **Android APK**")
                        if st.button("🚀 1. Build APK", key=f"{prefix}buildapk", use_container_width=True):
                            try:
                                raw_token = st.secrets.get("GITHUB_TOKEN", "")
                                raw_repo = st.secrets.get("GITHUB_REPO", "")
                                clean_token = re.sub(r'[^a-zA-Z0-9_.-]', '', raw_token)
                                clean_repo = re.sub(r'[^a-zA-Z0-9_./-]', '', raw_repo)
                                
                                if not clean_token or not clean_repo:
                                    st.error("⚠️ කරුණාකර Streamlit Secrets වල GITHUB_TOKEN සහ GITHUB_REPO සකසන්න.")
                                else:
                                    with st.spinner("🚀 Build කරමින් පවතී..."):
                                        headers = {"Accept": "application/vnd.github.v3+json", "Authorization": f"token {clean_token}"}
                                        custom_app_url = f"[https://ai-app-builder-x6qbi2k3iobvvzqbktkfma.streamlit.app/?app_id=](https://ai-app-builder-x6qbi2k3iobvvzqbktkfma.streamlit.app/?app_id=){str(app['id'])}"
                                        payload = {
                                            "event_type": "build_apk",
                                            "client_payload": {
                                                "app_id": str(app['id']), "app_name": app_name_safe, 
                                                "app_code": current_code, "android_version": app.get('android_version', 'Android 4.0+'), 
                                                "app_icon_url": app.get('app_icon_url', ''), "app_url": custom_app_url
                                            }
                                        }
                                        res = requests.post(f"[https://api.github.com/repos/](https://api.github.com/repos/){clean_repo}/dispatches", json=payload, headers=headers)
                                        if res.status_code == 204:
                                            st.success(f"✅ APK එක සෑදීම ආරම්භ විය! කරුණාකර විනාඩි 2ක් හෝ 3ක් රැඳී සිට පහත බොත්තම ඔබන්න.")
                                        else: 
                                            st.error(f"❌ Error: (Status {res.status_code}) - {res.text}")
                            except Exception as e: 
                                st.error(f"⚠️ Network Error: {e}")

                        st.markdown("<br>", unsafe_allow_html=True)
                        if st.button("📥 2. Download Final APK", key=f"{prefix}chkapk", use_container_width=True, type="primary"):
                            with st.spinner("📦 APK එක සෙවීම..."):
                                try:
                                    raw_token = st.secrets.get("GITHUB_TOKEN", "")
                                    raw_repo = st.secrets.get("GITHUB_REPO", "")
                                    clean_token = re.sub(r'[^a-zA-Z0-9_.-]', '', raw_token)
                                    clean_repo = re.sub(r'[^a-zA-Z0-9_./-]', '', raw_repo)
                                    
                                    headers = {"Authorization": f"token {clean_token}"}
                                    url = f"[https://api.github.com/repos/](https://api.github.com/repos/){clean_repo}/actions/artifacts"
                                    req = requests.get(url, headers=headers)
                                    
                                    if req.status_code == 200:
                                        data = req.json()
                                        target_name = f"{app_name_safe}-Android-App"
                                        artifact = next((a for a in data.get('artifacts', []) if a['name'] == target_name), None)
                                        
                                        if artifact and not artifact['expired']:
                                            dl_url = artifact['archive_download_url']
                                            zip_req = requests.get(dl_url, headers=headers)
                                            if zip_req.status_code == 200:
                                                st.download_button("✅ මෙතන ඔබලා Download කරගන්න", data=zip_req.content, file_name=f"{target_name}.zip", mime="application/zip", key=f"{prefix}dlbtn")
                                                st.balloons()
                                            else:
                                                st.error("APK එක ලබා ගැනීමට නොහැක.")
                                        else:
                                            st.warning("⚠️ තවම APK එක හැදෙමින් පවතී. කරුණාකර තව විනාඩියකින් නැවත බලන්න.")
                                    else:
                                        st.error("GitHub API දෝෂයකි.")
                                except Exception as e:
                                    st.error(str(e))

                    with col2:
                        st.warning("🗂️ **Source Code (ZIP)**")
                        if st.session_state.package == 'gold' or is_admin:
                            zip_buffer = io.BytesIO()
                            with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                                zip_file.writestr("app.py", current_code)
                                zip_file.writestr("requirements.txt", "streamlit\nsupabase\npg8000\nrequests\n")
                            
                            st.download_button(
                                "Download ZIP", data=zip_buffer.getvalue(), 
                                file_name=f"{app_name_safe.replace(' ', '_')}.zip", mime="application/zip", 
                                key=f"{prefix}zip", use_container_width=True
                            )
                        else: 
                            st.error("🔒 Source Code ලබා ගැනීමට Gold Package එකට Upgrade කරන්න.")
                            
                st.markdown("---")
                st.markdown("💬 **AI එකට කියලා තව කෑලි එකතු කරගන්න**")
                chat_hist = app.get('chat_history') or []
                for msg in chat_hist: 
                    st.info(f"🧑‍💻 **ඔබ:** {msg['content']}")
                    
                new_prompt = st.text_input("ඔබට අලුතින් එකතු කරගන්න ඕන දේ මෙතන කියන්න...", key=f"{prefix}prompt")
                
                if st.button("🚀 Update App with AI", key=f"{prefix}aiupd", type="primary"):
                    if new_prompt:
                        new_hist = chat_hist + [{"role": "user", "content": new_prompt}]
                        update_db = get_db(is_admin)
                        
                        res_update = update_db.table("generated_apps").update({"status": "pending", "chat_history": new_hist, "app_code": current_code}).eq("id", app['id']).execute()
                        
                        if res_update.data:
                            groq_key = st.secrets.get("GROQ_API_KEY", "").strip()
                            gemini_key = st.secrets.get("GEMINI_KEY", "").strip()
                            supa_url = st.secrets["SUPABASE_URL"].strip()
                            supa_key = st.secrets.get("SUPABASE_SERVICE_KEY", st.secrets["SUPABASE_KEY"]).strip()
                            
                            threading.Thread(target=process_single_app, args=(res_update.data[0], groq_key, gemini_key, supa_url, supa_key), daemon=True).start()
                        
                        st.success("AI එක ක්‍රියාත්මකයි! Refresh කර බලන්න.")
                        time.sleep(2)
                        st.rerun()
                    else: 
                        st.warning("කරුණාකර වෙනස්කම ටයිප් කරන්න.")
                        
            if st.button("🔄 Refresh Status", key=f"{prefix}ref"): 
                st.rerun()
    except Exception as e:
        st.error(f"⚠️ App Card Error: {str(e)}")

def render_generator_dashboard():
    trigger_social_proof()
    st.markdown("### 🛠️ App Generation Engine")
    
    db = get_db(False)
    res_count = db.table("generated_apps").select("id", count="exact").eq("owner_id", st.session_state.user.id).neq("status", "failed").execute()
    app_count = res_count.count if res_count.count else 0
    max_apps = 1 if st.session_state.package == 'free' else (10 if st.session_state.package == 'silver' else 9999)
    
    expiry_text = ""
    if st.session_state.package != 'free' and st.session_state.expires_at:
        exp_dt = datetime.fromisoformat(st.session_state.expires_at.replace('Z', '+00:00'))
        expiry_text = f" | ⏳ වලංගු දිනය: {exp_dt.strftime('%Y-%m-%d')}"
        
    st.info(f"📦 පැකේජය: **{st.session_state.package.upper()}**{expiry_text} | Active Apps: **{app_count}/{'Unlimited' if max_apps == 9999 else max_apps}**")
    
    if app_count >= max_apps:
        st.error("⚠️ උපරිම සීමාවට පැමිණ ඇත. තවත් Apps සෑදීමට කරුණාකර Upgrade කරන්න. (Fail වූ ඇප් පහළින් මකා දැමිය හැක)")
    else:
        app_name = st.text_input("App එකේ නම", placeholder="Ex: My Awesome App")
        col_a, col_b = st.columns(2)
        with col_a: 
            android_version = st.selectbox("Android Version එක තෝරන්න:", ["Android 4.0+", "Android 5.0+", "Android 6.0+", "Android 8.0+", "Android 10.0+", "Android 12.0+", "Android 14.0+"])
        with col_b: 
            app_icon = st.file_uploader("App Logo එකක් තෝරන්න (Optional):", type=['png', 'jpg', 'jpeg'])

        icon_prompt = st.text_input("අයිකන් එකේ මොනවද තියෙන්න ඕනේ කියලා AI එකට කියන්න:")
        st.markdown("---")

        col1, col2 = st.columns(2)
        with col1: 
            upload_option = st.radio("විස්තරය ලබා දෙන ආකාරය:", ["✍️ විස්තරයක්/Prompt දීම", "📁 File Upload කිරීම"], horizontal=True)
        with col2: 
            ai_model_choice = st.radio("AI එන්ජිම තෝරන්න:", ["⚡ Groq (Fast)", "🧠 Gemini (Pro)"], horizontal=True)
            selected_model = "gemini" if "Gemini" in ai_model_choice else "groq"
        
        source_link = ""
        uploaded_file = None
        
        if "Prompt" in upload_option: 
            source_link = st.text_area("ඔබේ අදහස මෙහි ටයිප් කරන්න:", height=100)
        else: 
            uploaded_file = st.file_uploader("File එක තෝරන්න", type=['zip', 'txt', 'py'])
            
        is_private = st.checkbox("මේ ඇප් එක හංගලා තියන්න (Private)", value=False)
            
        if st.button("🚀 Generate App", use_container_width=True, type="primary"):
            if app_name and (source_link or uploaded_file):
                final_source_link = source_link
                icon_url = ""
                
                if uploaded_file:
                    with st.spinner("☁️ File Uploading..."):
                        file_path = f"{st.session_state.user.id}/{int(time.time())}_{uploaded_file.name}"
                        db.storage.from_("app_sources").upload(file_path, uploaded_file.getvalue())
                        final_source_link = db.storage.from_("app_sources").get_public_url(file_path)

                if app_icon:
                    with st.spinner("☁️ Icon Uploading..."):
                        icon_path = f"{st.session_state.user.id}/icons/{int(time.time())}_{app_icon.name}"
                        db.storage.from_("app_sources").upload(icon_path, app_icon.getvalue())
                        icon_url = db.storage.from_("app_sources").get_public_url(icon_path)

                insert_data = {
                    "owner_id": st.session_state.user.id, 
                    "app_name": app_name, 
                    "source_link": final_source_link, 
                    "is_visible": not is_private, 
                    "status": "pending", 
                    "selected_model": selected_model, 
                    "chat_history": [],
                    "android_version": android_version, 
                    "app_icon_url": icon_url, 
                    "icon_prompt": icon_prompt
                }

                res = db.table("generated_apps").insert(insert_data).execute()
                if res.data:
                    groq_key = st.secrets.get("GROQ_API_KEY", "").strip()
                    gemini_key = st.secrets.get("GEMINI_KEY", "").strip()
                    supa_url = st.secrets["SUPABASE_URL"].strip()
                    supa_key = st.secrets.get("SUPABASE_SERVICE_KEY", st.secrets["SUPABASE_KEY"]).strip()
                    
                    threading.Thread(target=process_single_app, args=(res.data[0], groq_key, gemini_key, supa_url, supa_key), daemon=True).start()
                    st.success("✅ App එක පෝලිමට එක් කරන ලදී!")
                    time.sleep(2)
                    st.rerun()
            else: 
                st.error("කරුණාකර නම සහ විස්තරය / File එක ලබා දෙන්න.")

    st.markdown("---")
    st.markdown("### 📂 ඔබගේ Apps")
    apps_data = db.table("generated_apps").select("*").eq("owner_id", st.session_state.user.id).order("created_at", desc=True).execute()
    
    if apps_data.data:
        for app in apps_data.data:
            render_app_card(app, is_admin=False)
    else: 
        st.info("ඔබ තවම කිසිදු ඇප් එකක් සාදා නැත.")

def render_upgrade_section():
    trigger_social_proof()
    st.markdown("### 💳 Upgrade Your Package")
    
    settings = admin.get_system_settings()
    pricing = settings.get("pricing", {"silver_price": 2500, "gold_price": 5000})
    payment = settings.get("payment_details", {
        "ipay_num": "0757970703", 
        "ipay_name": "w.k.pradeep prasanna", 
        "boc_num": "88314511", 
        "boc_name": "W.K.P.P.SENEVIRATHNA"
    })
    
    col1, col2 = st.columns(2)
    with col1: 
        st.info(f"**🥈 Silver Package**\n\n- Apps 10ක් සෑදිය හැක.\n- ⏳ දින 30යි\n- **Rs. {pricing.get('silver_price', 2500)}**")
    with col2: 
        st.warning(f"**🥇 Gold Package**\n\n- අසීමිත Apps & Source Code.\n- ⏳ දින 30යි\n- **Rs. {pricing.get('gold_price', 5000)}**")
        
    st.markdown("#### 🏦 ගෙවීම් කළ යුතු ගිණුම් විස්තර")
    
    st.markdown(f"""
    <div style="display: flex; gap: 20px; flex-wrap: wrap; margin-bottom: 20px;">
        <div style="flex: 1; background: linear-gradient(135deg, #1e3c72 0%, #2a5298 100%); padding: 25px; border-radius: 15px; color: white; box-shadow: 0 10px 20px rgba(0,0,0,0.2);">
            <h3 style="margin-top:0; color: #4dc9ff; font-family: sans-serif;">📱 iPay / Online Transfer</h3>
            <p style="font-size: 18px; margin: 8px 0; opacity: 0.9;">Account Number</p>
            <h2 style="margin: 0; font-size: 28px; letter-spacing: 2px;">{{payment.get('ipay_num', '')}}</h2>
            <p style="font-size: 16px; margin: 15px 0 0 0; color: #b3d4ff;">Name: <strong style="color: white;">{{payment.get('ipay_name', '').upper()}}</strong></p>
        </div>
        <div style="flex: 1; background: linear-gradient(135deg, #d4af37 0%, #aa7700 100%); padding: 25px; border-radius: 15px; color: white; box-shadow: 0 10px 20px rgba(0,0,0,0.2);">
            <h3 style="margin-top:0; color: #fffef0; font-family: sans-serif;">🏦 BOC Flex / CDM Machine</h3>
            <p style="font-size: 18px; margin: 8px 0; opacity: 0.9;">Account Number</p>
            <h2 style="margin: 0; font-size: 28px; letter-spacing: 2px;">{{payment.get('boc_num', '')}}</h2>
            <p style="font-size: 16px; margin: 15px 0 0 0; color: #ffefb3;">Name: <strong style="color: white;">{{payment.get('boc_name', '').upper()}}</strong></p>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    with st.form("payment_form"):
        selected_pkg = st.selectbox("පැකේජය තෝරන්න:", ["silver", "gold"])
        slip_file = st.file_uploader("Slip එක Upload කරන්න (Image/PDF)", type=['jpg', 'jpeg', 'png', 'pdf'])
        
        if st.form_submit_button("Submit Payment", use_container_width=True):
            if slip_file:
                with st.spinner("Uploading..."):
                    db = get_db(False)
                    file_path = f"{st.session_state.user.id}/{int(time.time())}_{slip_file.name}"
                    db.storage.from_("payment_slips").upload(file_path, slip_file.getvalue())
                    slip_url = db.storage.from_("payment_slips").get_public_url(file_path)
                    
                    db.table("payments").insert({
                        "user_id": st.session_state.user.id, 
                        "package_name": selected_pkg, 
                        "slip_url": slip_url, 
                        "duration_days": 30, 
                        "status": "pending"
                    }).execute()
                st.success("✅ ගෙවීම යවන ලදී. Admin අනුමත කළ පසු යාවත්කාලීන වනු ඇත.")
            else: 
                st.error("කරුණාකර Slip එක Upload කරන්න.")
