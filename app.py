app_code = """import streamlit as st
import google.generativeai as genai
import streamlit.components.v1 as components
import re
import requests
import base64
import time
import json

# --- 1. PAGE CONFIGURATION & PREMIUM UI ---
st.set_page_config(page_title="Base44 Pro - Cloud AI Factory", page_icon="⚡", layout="wide")

st.markdown('''
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .stButton>button { 
        background: linear-gradient(45deg, #4f46e5, #06b6d4); 
        color: white; border: none; padding: 10px 24px; 
        border-radius: 8px; font-weight: bold; transition: 0.3s; 
    }
    .stButton>button:hover { transform: scale(1.02); box-shadow: 0 0 15px rgba(6, 182, 212, 0.4); }
    h1, h2, h3 { color: #ffffff !important; font-family: 'Poppins', sans-serif; }
    .sidebar .sidebar-content { background-color: #161b22; }
    .stTextArea>div>div>textarea { background-color: #1e242c; color: #58a6ff; font-family: monospace; border-radius: 8px; }
    .mobile-frame { border: 6px solid #30363d; border-radius: 24px; padding: 10px; background: #000; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
    </style>
''', unsafe_allow_html=True)

# Session States
if "app_code" not in st.session_state: st.session_state.app_code = None
if "github_token" not in st.session_state: st.session_state.github_token = None
if "build_running" not in st.session_state: st.session_state.build_running = False
if "apk_url" not in st.session_state: st.session_state.apk_url = None

# --- 2. SECRETS & SETUP ---
def get_secret(key):
    val = st.secrets.get(key, "")
    return str(val).strip() if val else ""

client_id = get_secret("GITHUB_CLIENT_ID")
client_secret = get_secret("GITHUB_CLIENT_SECRET")
supabase_url = get_secret("SUPABASE_URL")
supabase_key = get_secret("SUPABASE_KEY")
groq_default_key = get_secret("GROQ_API_KEY")

with st.sidebar:
    st.title("⚙️ Control Panel")
    
    # --- MULTI-AI SETUP ---
    st.subheader("🤖 AI Engine")
    ai_provider = st.selectbox("Select AI Provider:", ["Google Gemini (Default)", "Groq (High Speed/Free)"], index=1)
    
    if ai_provider == "Google Gemini (Default)":
        api_key = st.text_input("Gemini API Key", type="password", value=get_secret("GEMINI_KEY"))
        selected_model = st.selectbox("Select Model:", ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-2.5-flash"], index=0)
    else:
        api_key = st.text_input("Groq API Key", type="password", value=groq_default_key)
        selected_model = st.selectbox("Select Model:", ["llama-3.3-70b-versatile", "llama-3.1-8b-instant", "mixtral-8x7b-32768"], index=0)
    
    st.markdown("---")
    st.subheader("🎨 App Customization")
    custom_app_name = st.text_input("App Name (ඇප් එකේ නම):", value="PRO AI Trading")
    custom_logo_url = st.text_input("Logo URL (ලෝගෝ ලින්ක් එක):", placeholder="https://example.com/logo.png")
    
    # --- GITHUB ACCOUNT ---
    st.markdown("---")
    st.subheader("🐙 GitHub Account")
    login_method = st.radio("සම්බන්ධ වන ක්‍රමය:", ["OAuth Login (Browser)", "Manual Token (For Shortcuts)"], horizontal=True)
    
    if login_method == "OAuth Login (Browser)":
        if "code" in st.query_params and not st.session_state.github_token:
            auth_code = st.query_params["code"]
            token_url = base64.b64decode("aHR0cHM6Ly9naXRodWIuY29tL2xvZ2luL29hdXRoL2FjY2Vzc190b2tlbg==").decode('utf-8')
            res = requests.post(token_url, headers={"Accept": "application/json"}, data={"client_id": client_id, "client_secret": client_secret, "code": auth_code}).json()
            if "access_token" in res:
                st.session_state.github_token = res["access_token"]
                st.query_params.clear()
                st.rerun()
        
        if not st.session_state.github_token:
            auth_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&scope=repo%20workflow"
            st.markdown(f'<a href="{auth_url}" target="_blank" style="display:block; text-align:center; background:linear-gradient(45deg, #4f46e5, #06b6d4); color:white; padding:10px 24px; border-radius:8px; font-weight:bold; text-decoration:none; margin-bottom: 10px;">🔑 Login with GitHub (New Tab)</a>', unsafe_allow_html=True)
    else:
        manual_token = st.text_input("GitHub Token එක දමන්න:", type="password")
        if manual_token: st.session_state.github_token = manual_token

    github_repo, github_token = "", ""
    if st.session_state.github_token:
        st.success("✅ GitHub සම්බන්ධ වී ඇත!")
        if st.button("🚪 Logout"):
            st.session_state.github_token = None
            st.session_state.build_running = False
            st.session_state.apk_url = None
            st.rerun()
            
        github_token = st.session_state.github_token.strip()
        with st.spinner("Repositories ගෙන එමින්..."):
            try:
                repo_headers = {"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github.v3+json"}
                repos_api = base64.b64decode("aHR0cHM6Ly9hcGkuZ2l0aHViLmNvbS91c2VyL3JlcG9zP3NvcnQ9dXBkYXRlZCZwZXJfcGFnZT01MA==").decode('utf-8')
                repos_res = requests.get(repos_api, headers=repo_headers)
                
                if repos_res.status_code == 200:
                    repo_list = [r["full_name"] for r in repos_res.json()]
                    if repo_list:
                        github_repo = st.selectbox("📌 Select your Repository", repo_list)
                    else:
                        st.warning("ඔබගේ ගිණුමේ Repositories කිසිවක් සොයාගත නොහැක.")
                        github_repo = st.text_input("GitHub Repository Name", placeholder="username/repo-name")
                else:
                    st.error(f"GitHub API Error: {repos_res.status_code}")
                    github_repo = st.text_input("GitHub Repository Name", placeholder="username/repo-name")
            except Exception as e:
                st.error(f"Network Error: {e}")
                github_repo = st.text_input("GitHub Repository Name", placeholder="username/repo-name")
    else:
        st.selectbox("GitHub Repository", ["කරුණාකර පළමුව ලොග් වන්න"], disabled=True)

# --- 3. MAIN INTERFACE ---
st.title("⚡ AI App Factory (Base44 Pro Edition)")

tab1, tab2, tab3 = st.tabs(["💡 App Idea", "🌐 Web URL Scanner", "🐙 GitHub Repo Scanner"])
user_context, source_info = "", ""

with tab1:
    idea_input = st.text_area("ඔබට අවශ්‍ය ඇප් එක ගැන විස්තර කරන්න:", height=120, placeholder="උදා: Trading signals පෙන්නන ඇප් එකක්...")
    if idea_input: user_context, source_info = f"User Request: {idea_input}", "Text Idea"
with tab2:
    url_input = st.text_input("ස්කෑන් කිරීමට අවශ්‍ය වෙබ් අඩවියේ URL එක දමන්න:")
    if url_input: user_context, source_info = f"Web URL: {url_input}.", f"Web Scanner ({url_input})"
with tab3:
    github_input = st.text_input("කියවීමට අවශ්‍ය GitHub Repo URL එක හෝ නම දමන්න:", value=github_repo, placeholder="username/repo-name")
    if github_input:
        with st.spinner("GitHub Repository එක ගැඹුරින් පරීක්ෂා කරමින් පවතී..."):
            try:
                repo_path = github_input.strip().split("github.com/")[-1].rstrip("/") if "github.com/" in github_input else github_input.strip().rstrip("/")
                gh_contents_url = base64.b64decode("aHR0cHM6Ly9hcGkuZ2l0aHViLmNvbS9yZXBvcy8=").decode('utf-8') + f"{repo_path}/contents"
                res = requests.get(gh_contents_url, headers={"User-Agent": "Mozilla/5.0"})
                if res.status_code == 200:
                    files_list, readme_content = [], ""
                    for f in res.json():
                        if isinstance(f, dict) and 'name' in f:
                            files_list.append(f['name'])
                            if f['name'].lower() in ['readme.md', 'app.py', 'index.js', 'main.py']:
                                if 'download_url' in f and f['download_url']:
                                    file_res = requests.get(f['download_url'])
                                    if file_res.status_code == 200:
                                        readme_content += f"\\n--- {f['name']} ---\\n{file_res.text[:1500]}"
                    user_context = f"GitHub Repo: {repo_path}. \\nFiles: {', '.join(files_list)}. \\nProject Snippets: {readme_content}\\nCreate a MATCHING app based EXACTLY on these algorithms."
                    source_info = f"GitHub Scanner ({repo_path})"
                    st.success("🐙 GitHub Repo එකේ අන්තර්ගතය සාර්ථකව කියවන ලදී!")
                else:
                    user_context, source_info = f"GitHub Repo: {repo_path}.", "GitHub Repo Manual"
            except:
                user_context, source_info = f"GitHub Repo: {github_input}", "GitHub Fallback"

# --- 4. ENGINE START ---
if st.button("🚀 GENERATE MASTER APP", use_container_width=True):
    if not api_key:
        st.error(f"👈 කරුණාකර ප්‍රථමයෙන් {ai_provider.split(' ')[0]} API Key එක ලබා දෙන්න.")
    elif not user_context:
        st.warning("⚠️ කරුණාකර තොරතුරු ඇතුළත් කරන්න.")
    else:
        with st.spinner(f"{ai_provider.split(' ')[0]} AI මඟින් Premium කේතය ලියමින් පවතී... (මඳක් රැඳී සිටින්න)"):
            try:
                # 🚀 DYNAMIC, CONTEXT-AWARE PREMIUM PROMPT 🚀
                master_prompt = f\"\"\"You are a World-Class Principal UI/UX Engineer and Full-Stack Mobile App Developer.
Source: {source_info}. Context: {user_context}.

CRITICAL MISSION: Build an ultra-premium, visually stunning Single Page Application (SPA) for Mobile based EXACTLY on the user's context/repo. Do NOT default to a trading app unless the context implies it. Adapt your UI/UX to the specific domain (e.g., E-commerce, Social, Utility, Finance).

CRITICAL TECHNICAL RULES:
1. **DOMAIN ADAPTATION**: Analyze the Context/Repo. If it's a Trading app, use TradingView/Chart.js and order books. If it's E-commerce, build beautiful product grids and cart UI. If it's Social, build elegant feeds. Match the UI vibe perfectly to the use-case.
2. **ULTRA-PREMIUM UI**: Use Tailwind CSS (`<script src="https://cdn.tailwindcss.com"></script>`). Create a breathtaking, modern design (e.g., glassmorphism, beautiful gradients, subtle borders, high-end typography). Use FontAwesome (`<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">`).
3. **SPA NAVIGATION (CRITICAL FOR IFRAME)**: 
   - Create at least 4 distinct functional screens/tabs.
   - Switch them using JavaScript (`display: none` / `block`). 
   - ABSOLUTELY NEVER use `<a href>` for internal navigation! It crashes the iframe. Use `<button onclick="...">` or `<div onclick="...">`.
4. **DENSITY & MOCK DATA**: No empty states! Provide highly detailed JavaScript arrays for mock data. Fill the UI with realistic content (images, names, metrics, timestamps).
5. **GITHUB REPO COMPLETENESS**: If a repo is provided, you MUST integrate ALL its implied logic, algorithms, and features into this UI. Make the UI functional to represent the repo's purpose.

Output ONLY raw HTML code (starting with <!DOCTYPE html> and ending with </html>). NO Markdown, NO explanations.\"\"\"
                
                raw_code = ""
                clean_api_key = str(api_key).strip()
                
                if ai_provider == "Google Gemini (Default)":
                    genai.configure(api_key=clean_api_key)
                    model = genai.GenerativeModel(selected_model, generation_config={"max_output_tokens": 8192})
                    response = model.generate_content(master_prompt)
                    raw_code = response.text
                else:
                    groq_url = base64.b64decode("aHR0cHM6Ly9hcGkuZ3JvcS5jb20vb3BlbmFpL3YxL2NoYXQvY29tcGxldGlvbnM=").decode('utf-8')
                    
                    headers = {
                        "Authorization": f"Bearer {clean_api_key}", 
                        "Content-Type": "application/json"
                    }
                    payload = {
                        "model": selected_model, 
                        "messages": [{"role": "user", "content": master_prompt}], 
                        "max_tokens": 8000,
                        "temperature": 0.3
                    }
                    res = requests.post(groq_url, headers=headers, json=payload)
                    if res.status_code == 200:
                        raw_code = res.json()["choices"][0]["message"]["content"]
                    else:
                        st.error(f"Groq API Error: {res.text}")
                        st.stop()
                
                html_match = re.search(r'(<!DOCTYPE\s+html>.*?</html>)', raw_code, re.IGNORECASE | re.DOTALL)
                final_code = html_match.group(1).strip() if html_match else re.search(r'(<html.*?>.*?</html>)', raw_code, re.IGNORECASE | re.DOTALL).group(1).strip() if re.search(r'(<html.*?>.*?</html>)', raw_code, re.IGNORECASE | re.DOTALL) else raw_code.replace("```html", "").replace("```", "").strip()
                
                st.session_state.app_code = final_code
                st.session_state.apk_url = None
                
                safe_supa_url = supabase_url.strip() if supabase_url else ""
                if safe_supa_url and supabase_key:
                    try:
                        supa_headers = {"apikey": supabase_key, "Authorization": f"Bearer {supabase_key}", "Content-Type": "application/json", "Prefer": "return=minimal"}
                        supa_data = {"app_name": custom_app_name, "provider": ai_provider, "model": selected_model, "source_code": final_code}
                        requests.post(f"{safe_supa_url}/rest/v1/generated_apps", headers=supa_headers, json=supa_data)
                    except:
                        pass
                        
                st.rerun()
            except Exception as e:
                st.error(f"❌ දෝෂයක්: {e}")

# --- 5. LIVE DISPLAY & EDITING ---
if st.session_state.app_code:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("💻 Live Code Editor")
        edited_code = st.text_area("කේතය වෙනස් කරන්න", st.session_state.app_code, height=600)
    with col2:
        st.subheader("📱 Instant Mobile View")
        st.markdown('<div class="mobile-frame">', unsafe_allow_html=True)
        components.html(edited_code, height=580, scrolling=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    # --- 6. GITHUB ACTIONS APK BUILD ENGINE ---
    st.markdown("---")
    st.subheader("📦 Base44 Pro APK Compiler (Cloud Engine)")
    
    if st.button("🏗️ Trigger Remote Cloud Build & Get APK", type="primary", use_container_width=True, disabled=st.session_state.build_running):
        if not github_token or not github_repo:
            st.error("👈 කරුණාකර වම් පස ඇති Sidebar එකෙන් GitHub ගිණුමට ලොග් වී Repo එකක් තෝරන්න.")
        else:
            headers = {"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github.v3+json"}
            wf_url = base64.b64decode("aHR0cHM6Ly9hcGkuZ2l0aHViLmNvbS9yZXBvcy8=").decode('utf-8') + f"{github_repo}/contents/.github/workflows/build.yml"
            wf_check = requests.get(wf_url, headers=headers)
            if wf_check.status_code != 200:
                yaml_content = \"\"\"name: Build Android APK
on:
  push:
    branches: [ main ]
  workflow_dispatch:
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v3
    - uses: actions/setup-node@v3
      with:
        node-version: 18
    - run: npm install -g cordova
    - run: |
        cordova create myapp com.premium.aifactory AI_App
        cd myapp
        cordova platform add android
        rm www/index.html
        cp ../index.html www/index.html
    - uses: actions/setup-java@v3
      with:
        distribution: 'zulu'
        java-version: '17'
    - uses: android-actions/setup-android@v3
    - run: |
        cd myapp
        cordova build android --no-telemetry
    - uses: actions/upload-artifact@v4
      with:
        name: premium-app-apk
        path: myapp/platforms/android/app/build/outputs/apk/debug/app-debug.apk\"\"\"
                requests.put(wf_url, headers=headers, json={"message": "Auto-setup Cloud Build Workflow", "content": base64.b64encode(yaml_content.encode('utf-8')).decode('utf-8')})
            
            file_url = base64.b64decode("aHR0cHM6Ly9hcGkuZ2l0aHViLmNvbS9yZXBvcy8=").decode('utf-8') + f"{github_repo}/contents/index.html"
            sha = ""
            get_res = requests.get(file_url, headers=headers)
            if get_res.status_code == 200: sha = get_res.json()['sha']
            
            payload = {"message": "Update AI App Source Code", "content": base64.b64encode(edited_code.encode('utf-8')).decode('utf-8')}
            if sha: payload["sha"] = sha
                
            push_res = requests.put(file_url, headers=headers, json=payload)
            if push_res.status_code in [200, 201]:
                st.session_state.build_running = True
                st.session_state.apk_url = None
                st.rerun()
            else:
                st.error(f"❌ GitHub අප්ලෝඩ් එක අසාර්ථකයි: {push_res.text}")

    # --- 7. MANUAL COMPILER TRACKER ---
    if st.session_state.build_running:
        st.info("🛠️ Cloud Build එක සිදුවෙමින් පවතී... මෙය සාමාන්‍යයෙන් විනාඩි 2-3ක් ගත වේ.")
        if st.button("🔄 තත්ත්වය පරීක්ෂා කරන්න (Check Status)", use_container_width=True):
            try:
                runs_api = base64.b64decode("aHR0cHM6Ly9hcGkuZ2l0aHViLmNvbS9yZXBvcy8=").decode('utf-8') + f"{github_repo}/actions/runs"
                run_res = requests.get(runs_api, headers={"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github.v3+json"}).json()
                if "workflow_runs" in run_res and len(run_res["workflow_runs"]) > 0:
                    latest_run = run_res["workflow_runs"][0]
                    st.write(f"⏳ Cloud Compiler තත්ත්වය: **{latest_run['status'].upper()}**")
                    if latest_run['status'] == "completed":
                        st.session_state.build_running = False
                        if latest_run['conclusion'] == "success":
                            art_res = requests.get(latest_run["artifacts_url"], headers={"Authorization": f"Bearer {github_token}", "Accept": "application/vnd.github.v3+json"}).json()
                            if art_res.get("artifacts"):
                                st.session_state.apk_url = f"https://github.com/{github_repo}/actions/runs/{latest_run['id']}/artifacts/{art_res['artifacts'][0]['id']}"
                            else:
                                st.error("⚠️ APK ෆයිල් එක සොයාගත නොහැක.")
                        else:
                            st.error("❌ Cloud Build එක අසාර්ථක වුණා. GitHub වල Actions ටැබ් එක බලන්න.")
                        st.rerun()
                    else:
                        st.warning("⏳ තවම Build වෙමින් පවතී. තව තත්පර 30කින් පමණ නැවත Check කරන්න.")
                else:
                    st.warning("⏳ GitHub Actions තවම පටන් ගෙන නැත...")
            except Exception as e:
                st.error(f"⚠️ ජාලයේ ගැටලුවක්: {e}")

    if st.session_state.apk_url:
        st.markdown("---")
        st.success("🎯 සාර්ථකයි! ඔබගේ APK ගොනුව සූදානම්.")
        st.balloons()
        st.link_button("📥 DOWNLOAD OFFICIAL APK (ZIP)", st.session_state.apk_url, use_container_width=True)
"""

with open("app.py", "w", encoding="utf-8") as f:
    f.write(app_code)
