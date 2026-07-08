import streamlit as st
import google.generativeai as genai
import streamlit.components.v1 as components
import re
import requests
import base64
import time

# --- 1. PAGE CONFIGURATION & PREMIUM UI ---
st.set_page_config(page_title="Base44 Pro - Cloud AI Factory", page_icon="⚡", layout="wide")

st.markdown("""
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
""", unsafe_allow_html=True)

# Session States
if "app_code" not in st.session_state: st.session_state.app_code = None
if "github_token" not in st.session_state: st.session_state.github_token = None
if "build_running" not in st.session_state: st.session_state.build_running = False
if "apk_url" not in st.session_state: st.session_state.apk_url = None

# --- 2. SECRETS & OAUTH LOGIN ---
default_gemini_key = st.secrets.get("GEMINI_KEY", "")
client_id = st.secrets.get("GITHUB_CLIENT_ID", "")
client_secret = st.secrets.get("GITHUB_CLIENT_SECRET", "")

with st.sidebar:
    st.title("⚙️ Control Panel")
    gemini_key = st.text_input("Gemini API Key", value=default_gemini_key, type="password")
    
    st.markdown("---")
    st.subheader("🐙 GitHub Account")
    
    login_method = st.radio("සම්බන්ධ වන ක්‍රමය:", ["OAuth Login (Browser)", "Manual Token (For Shortcuts)"], horizontal=True)
    
    if login_method == "OAuth Login (Browser)":
        if "code" in st.query_params and not st.session_state.github_token:
            auth_code = st.query_params["code"]
            token_url = "[https://github.com/login/oauth/access_token](https://github.com/login/oauth/access_token)"
            headers = {"Accept": "application/json"}
            data = {"client_id": client_id, "client_secret": client_secret, "code": auth_code}
            res = requests.post(token_url, headers=headers, data=data).json()
            if "access_token" in res:
                st.session_state.github_token = res["access_token"]
                st.query_params.clear()
                st.rerun()
        
        if not st.session_state.github_token:
            auth_url = f"[https://github.com/login/oauth/authorize?client_id=](https://github.com/login/oauth/authorize?client_id=){client_id}&scope=repo%20workflow"
            st.link_button("🔑 Login with GitHub", auth_url, type="primary", use_container_width=True)
    else:
        manual_token = st.text_input("GitHub Token එක දමන්න:", type="password")
        if manual_token: st.session_state.github_token = manual_token

    github_repo = ""
    github_token = ""
    
    if st.session_state.github_token:
        st.success("✅ GitHub සම්බන්ධ වී ඇත!")
        if st.button("🚪 Logout"):
            st.session_state.github_token = None
            st.session_state.build_running = False
            st.session_state.apk_url = None
            st.rerun()
            
        github_token = st.session_state.github_token
        
        with st.spinner("Repositories ගෙන එමින්..."):
            try:
                repo_headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
                repos_res = requests.get("[https://api.github.com/user/repos?sort=updated&per_page=50](https://api.github.com/user/repos?sort=updated&per_page=50)", headers=repo_headers)
                if repos_res.status_code == 200:
                    repo_list = [r["full_name"] for r in repos_res.json()]
                    if repo_list:
                        github_repo = st.selectbox("📌 Select your Repository", repo_list)
                    else:
                        st.warning("Repos සොයාගත නොහැක.")
                else:
                    github_repo = st.text_input("GitHub Repository Name", placeholder="username/repo-name")
            except:
                github_repo = st.text_input("GitHub Repository Name", placeholder="username/repo-name")
    else:
        st.selectbox("GitHub Repository", ["කරුණාකර පළමුව ලොග් වන්න"], disabled=True)

    st.markdown("---")
    st.subheader("🤖 AI Model")
    selected_model = st.selectbox("Select Model:", ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"], index=0)

# --- 3. MAIN INTERFACE ---
st.title("⚡ AI App Factory (Base44 Pro Edition)")

tab1, tab2, tab3 = st.tabs(["💡 App Idea", "🌐 Web URL Scanner", "🐙 GitHub Repo Scanner"])
user_context, source_info = "", ""

with tab1:
    idea_input = st.text_area("ඔබට අවශ්‍ය ඇප් එක ගැන විස්තර කරන්න:", height=120, placeholder="උදා: Trading signals පෙන්නන ඇප් එකක්...")
    if idea_input: user_context, source_info = f"පරිශීලක අදහස: {idea_input}", "Text Idea"

with tab2:
    url_input = st.text_input("ස්කෑන් කිරීමට අවශ්‍ය වෙබ් අඩවියේ URL එක දමන්න:")
    if url_input: user_context, source_info = f"වෙබ් අඩවියේ URL එක: {url_input}.", f"Web URL ({url_input})"

with tab3:
    github_input = st.text_input("කියවීමට අවශ්‍ය GitHub Repo URL එක හෝ නම දමන්න:", value=github_repo, placeholder="username/repo-name")
    if github_input:
        with st.spinner("GitHub Repository එක ගැඹුරින් පරීක්ෂා කරමින් පවතී..."):
            try:
                clean_input = github_input.strip()
                repo_path = clean_input.split("[github.com/](https://github.com/)")[-1].rstrip("/") if "[github.com/](https://github.com/)" in clean_input else clean_input.rstrip("/")
                
                repo_api_url = f"[https://api.github.com/repos/](https://api.github.com/repos/){repo_path}/contents"
                res = requests.get(repo_api_url, headers={"User-Agent": "Mozilla/5.0"})
                
                if res.status_code == 200:
                    files_list = []
                    readme_content = ""
                    
                    for f in res.json():
                        if isinstance(f, dict) and 'name' in f:
                            files_list.append(f['name'])
                            if f['name'].lower() in ['readme.md', 'app.py', 'index.js']:
                                if 'download_url' in f and f['download_url']:
                                    file_res = requests.get(f['download_url'])
                                    if file_res.status_code == 200:
                                        readme_content += f"\n--- {f['name']} ---\n{file_res.text[:1000]}"
                    
                    user_context = f"GitHub Repo: {repo_path}. \nFiles: {', '.join(files_list)}. \nProject Content Snippets: {readme_content}\nමීට ගැළපෙන, සම්පූර්ණයෙන්ම වැඩ කරන ඇප් එකක් සාදන්න."
                    source_info = f"GitHub Scanner ({repo_path})"
                    st.success("🐙 GitHub Repo එකේ අන්තර්ගතය සාර්ථකව කියවන ලදී!")
                else:
                    user_context = f"GitHub Repo: {repo_path}."
                    source_info = f"GitHub Repo Manual"
            except Exception as e:
                user_context = f"GitHub Repo: {github_input}"
                source_info = "GitHub Fallback"

# --- 4. ENGINE START (ADVANCED FULL-STACK PROMPT & FOOL-PROOF EXTRACTOR) ---
if st.button("🚀 GENERATE MASTER APP", use_container_width=True):
    if not gemini_key:
        st.error("👈 කරුණාකර ප්‍රථමයෙන් Gemini API Key එක ලබා දෙන්න.")
    elif not user_context:
        st.warning("⚠️ කරුණාකර තොරතුරු ඇතුළත් කරන්න.")
    else:
        with st.spinner("AI මාදිලිය මඟින් සම්පූර්ණ App එක ලියමින් පවතී... (මඳක් රැඳී සිටින්න)"):
            try:
                genai.configure(api_key=gemini_key)
                # වචන ගණන සීමාව වැඩි කිරීම (Max Output Tokens)
                model = genai.GenerativeModel(selected_model, generation_config={"max_output_tokens": 8192})
                
                master_prompt = f"""ඔබ ලෝකයේ සිටින දක්ෂතම Full-Stack Mobile App Developer සහ UI/UX Designer කෙනෙකි.
                මූලාශ්‍රය: {source_info}. විස්තරය සහ කේතය: {user_context}. 
                
                ඔබගේ කාර්යය වන්නේ ඉහත Project එකට අදාළව, ජංගම දුරකථන සඳහා සම්පූර්ණයෙන්ම ක්‍රියාත්මක වන (Fully Functional) Single Page Application (SPA) එකක් නිර්මාණය කිරීමයි.
                
                අනිවාර්ය අවශ්‍යතා:
                1. Premium UI: Tailwind CSS භාවිතයෙන් අතිශය නවීන, ආකර්ෂණීය Dark Mode UI එකක් සාදන්න. Glassmorphism, Box Shadows සහ Smooth CSS animations භාවිතා කරන්න.
                2. Real Functionality: කේතයේ ඇති බොත්තම්, Side menus, සහ Bottom Navigation අනිවාර්යයෙන්ම වැඩ කළ යුතුය. JavaScript භාවිතයෙන් පිටු අතර (Sections) මාරු වීම සකසන්න (Hide/Show divs).
                3. Business Logic: යෙදුමේ ප්‍රධාන කාර්යයන් සඳහා අවශ්‍ය JavaScript Logic (උදා: Forms submit වීම, ගණනය කිරීම්, දත්ත පෙන්නුම් කිරීම) අනිවාර්යයෙන්ම ලියන්න.
                4. Data Storage: API සම්බන්ධතා නොමැති තැන් වලදී දත්ත අහිමි නොවීම සඳහා LocalStorage භාවිතා කර දත්ත Save සහ Load වීමට සකසන්න. 
                5. Font & Icons: Google Fonts (Poppins) සහ FontAwesome icons භාවිතා කරන්න.
                
                කිසිදු පැහැදිලි කිරීමක් අවශ්‍ය නැත. සම්පූර්ණ HTML, CSS (Tailwind), සහ අදාළ සියලුම JavaScript කේතයන් එකම කේතයක් ලෙස ```html සහ ``` අතර පමණක් ලබා දෙන්න."""
                
                response = model.generate_content(master_prompt)
                
                # 💡 FIX: Fool-proof Code Extractor
                raw_text = response.text
                
                # HTML Markdown එක ඉවත් කිරීම
                if re.search(r'```html', raw_text, re.IGNORECASE):
                    raw_text = re.split(r'```html', raw_text, flags=re.IGNORECASE)[1]
                elif "```" in raw_text:
                    raw_text = raw_text.split("```", 1)[1]
                
                # අවසානයේ ඇති Markdown එක ඉවත් කිරීම
                if "```" in raw_text:
                    raw_text = raw_text.split("```")[0]
                    
                st.session_state.app_code = raw_text.strip()
                st.session_state.apk_url = None
                st.rerun()
            except Exception as e:
                st.error(f"❌ දෝෂයක්: {e}")

# --- 5. LIVE DISPLAY & EDITING ---
if st.session_state.app_code:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("💻 Live Code Editor")
        edited_code = st.text_area("කේතය වෙනස් කරන්න", st.session_state.app_code, height=450)
    with col2:
        st.subheader("📱 Instant Mobile View")
        st.markdown('<div class="mobile-frame">', unsafe_allow_html=True)
        components.html(edited_code, height=430, scrolling=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    # --- 6. GITHUB ACTIONS APK BUILD ENGINE ---
    st.markdown("---")
    st.subheader("📦 Base44 Pro APK Compiler (Cloud Engine)")
    
    if st.button("🏗️ Trigger Remote Cloud Build & Get APK", type="primary", use_container_width=True, disabled=st.session_state.build_running):
        if not github_token or not github_repo:
            st.error("👈 කරුණාකර වම් පස ඇති Sidebar එකෙන් GitHub ගිණුමට ලොග් වී Repo එකක් තෝරන්න.")
        else:
            headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
            
            wf_url = f"[https://api.github.com/repos/](https://api.github.com/repos/){github_repo}/contents/.github/workflows/build.yml"
            wf_check = requests.get(wf_url, headers=headers)
            if wf_check.status_code != 200:
                yaml_content = """name: Build Android APK\non:\n  push:\n    branches: [ main ]\n  workflow_dispatch:\njobs:\n  build:\n    runs-on: ubuntu-latest\n    steps:\n    - uses: actions/checkout@v3\n    - uses: actions/setup-node@v3\n      with:\n        node-version: 18\n    - run: npm install -g cordova\n    - run: |\n        cordova create myapp com.premium.aifactory AI_App\n        cd myapp\n        cordova platform add android\n        rm www/index.html\n        cp ../index.html www/index.html\n    - uses: actions/setup-java@v3\n      with:\n        distribution: 'zulu'\n        java-version: '17'\n    - uses: android-actions/setup-android@v3\n    - run: |\n        cd myapp\n        cordova build android --no-telemetry\n    - uses: actions/upload-artifact@v4\n      with:\n        name: premium-app-apk\n        path: myapp/platforms/android/app/build/outputs/apk/debug/app-debug.apk"""
                wf_payload = {"message": "Auto-setup Cloud Build Workflow", "content": base64.b64encode(yaml_content.encode('utf-8')).decode('utf-8')}
                requests.put(wf_url, headers=headers, json=wf_payload)
            
            file_url = f"[https://api.github.com/repos/](https://api.github.com/repos/){github_repo}/contents/index.html"
            sha = ""
            get_res = requests.get(file_url, headers=headers)
            if get_res.status_code == 200: sha = get_res.json()['sha']
            
            encoded_code = base64.b64encode(edited_code.encode('utf-8')).decode('utf-8')
            payload = {"message": "Update AI App Source Code", "content": encoded_code}
            if sha: payload["sha"] = sha
                
            push_res = requests.put(file_url, headers=headers, json=payload)
            if push_res.status_code in [200, 201]:
                st.session_state.build_running = True
                st.session_state.apk_url = None
                st.rerun()
            else:
                st.error(f"❌ GitHub අප්ලෝඩ් එක අසාර්ථකයි: {push_res.text}")

    # --- 7. MANUAL COMPILER TRACKER (100% TIMEOUT SAFE & 404 FIXED) ---
    if st.session_state.build_running:
        st.info("🛠️ Cloud Build එක සිදුවෙමින් පවතී... මෙය සාමාන්‍යයෙන් විනාඩි 2-3ක් ගත වේ.")
        
        if st.button("🔄 තත්ත්වය පරීක්ෂා කරන්න (Check Status)", use_container_width=True):
            headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
            runs_url = f"[https://api.github.com/repos/](https://api.github.com/repos/){github_repo}/actions/runs"
            
            try:
                run_res = requests.get(runs_url, headers=headers).json()
                
                if "workflow_runs" in run_res and len(run_res["workflow_runs"]) > 0:
                    latest_run = run_res["workflow_runs"][0]
                    status_git = latest_run["status"]
                    conclusion = latest_run["conclusion"]
                    
                    st.write(f"⏳ Cloud Compiler තත්ත්වය: **{status_git.upper()}**")
                    
                    if status_git == "completed":
                        st.session_state.build_running = False
                        if conclusion == "success":
                            artifact_res = requests.get(latest_run["artifacts_url"], headers=headers).json()
                            if artifact_res.get("artifacts"):
                                art_id = artifact_res["artifacts"][0]["id"]
                                run_id = latest_run["id"] 
                                st.session_state.apk_url = f"[https://github.com/](https://github.com/){github_repo}/actions/runs/{run_id}/artifacts/{art_id}"
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
