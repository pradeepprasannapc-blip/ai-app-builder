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

if "app_code" not in st.session_state:
    st.session_state.app_code = None
# --- 2. SECRETS & OAUTH LOGIN ---
default_gemini_key = st.secrets.get("GEMINI_KEY", "")
client_id = st.secrets.get("GITHUB_CLIENT_ID", "")
client_secret = st.secrets.get("GITHUB_CLIENT_SECRET", "")

if "github_token" not in st.session_state:
    st.session_state.github_token = None

with st.sidebar:
    st.title("⚙️ Control Panel")
    gemini_key = st.text_input("Gemini API Key", value=default_gemini_key, type="password")
    
    st.markdown("---")
    st.subheader("🐙 GitHub Account Login")
    
    # --- නියම GITHUB OAUTH LOGIN FLOW එක ---
    # URL එකේ 'code' එකක් ඇවිත් තියෙනවද කියලා බලනවා (GitHub එකෙන් ආපසු එනකොට)
    if "code" in st.query_params and not st.session_state.github_token:
        auth_code = st.query_params["code"]
        token_url = "https://github.com/login/oauth/access_token"
        headers = {"Accept": "application/json"}
        data = {
            "client_id": client_id,
            "client_secret": client_secret,
            "code": auth_code
        }
        res = requests.post(token_url, headers=headers, data=data).json()
        
        if "access_token" in res:
            st.session_state.github_token = res["access_token"]
            st.query_params.clear() # URL එක ක්ලියර් කරනවා ලස්සනට තියෙන්න
            st.rerun()
        else:
            st.error("ලොගින් වීම අසාර්ථකයි!")

    # බොත්තම පෙන්වීම හෝ ලොග් වී ඇති බව පෙන්වීම
    if not st.session_state.github_token:
        # ලොගින් ලින්ක් එක හැදීම (repo සහ workflow අවසර ඉල්ලමින්)
        auth_url = f"https://github.com/login/oauth/authorize?client_id={client_id}&scope=repo%20workflow"
        st.link_button("🔑 Login with GitHub", auth_url, type="primary", use_container_width=True)
        st.caption("Base44 Pro හි මෙන් ඔබගේ ගිණුමට ආරක්ෂිතව ලොග් වන්න.")
        
        # ලොග් වෙලා නැත්නම් repo එක මැනුවල් ගහන්න දෙන්න පුළුවන්, හෝ disable කරන්න පුළුවන්
        github_repo = st.text_input("GitHub Repository Name", placeholder="username/repo-name", disabled=True)
        github_token = ""
    else:
        st.success("✅ GitHub ගිණුමට සාර්ථකව ලොග් වී ඇත")
        if st.button("🚪 Logout"):
            st.session_state.github_token = None
            st.rerun()
            
        github_token = st.session_state.github_token
        github_repo = st.text_input("GitHub Repository Name", placeholder="username/repo-name", help="ඔබගේ කේතය සෑදිය යුතු රෙපෝ එකේ නම දෙන්න.")

    st.markdown("---")
    st.subheader("🤖 AI Model")
    selected_model = st.selectbox("Select Model:", ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash"], index=0)
    
    if st.button("🗑️ Clear Workspace"):
        st.session_state.app_code = None
        st.rerun()


# --- 4. ENGINE START ---
if st.button("🚀 GENERATE MASTER APP", use_container_width=True):
    if not gemini_key:
        st.error("👈 කරුණාකර ප්‍රථමයෙන් Gemini API Key එක ලබා දෙන්න.")
    elif not user_context:
        st.warning("⚠️ කරුණාකර තොරතුරු ඇතුළත් කරන්න.")
    else:
        with st.spinner("AI මාදිලිය මඟින් කේතය ලියමින් පවතී..."):
            try:
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel(selected_model)
                master_prompt = f"ඔබ Premium UI Developer කෙනෙක්. මූලාශ්‍රය: {source_info}. විස්තරය: {user_context}. කරුණාකර Tailwind CSS සහ ලස්සන Dark Mode සහිත සම්පූර්ණ Single HTML කේතය පමණක් ```html සහ ``` අතර ලබා දෙන්න."
                
                response = model.generate_content(master_prompt)
                match = re.search(r'```html(.*?)```', response.text, re.DOTALL | re.IGNORECASE)
                st.session_state.app_code = match.group(1).strip() if match else response.text.strip()
            except Exception as e:
                st.error(f"❌ දෝෂයක්: {e}")

# --- 5. LIVE DISPLAY & REAL-TIME CLOUD BUILD ---
if st.session_state.app_code:
    col1, col2 = st.columns([1, 1])
    with col1:
        st.subheader("💻 Live Code Editor")
        edited_code = st.text_area("කේතය වෙනස් කරන්න", st.session_state.app_code, height=500)
    with col2:
        st.subheader("📱 Instant Mobile View")
        st.markdown('<div class="mobile-frame">', unsafe_allow_html=True)
        components.html(edited_code, height=480, scrolling=True)
        st.markdown('</div>', unsafe_allow_html=True)
        
    # --- 6. GITHUB ACTIONS REAL APK BUILD ENGINE ---
    st.markdown("---")
    st.subheader("📦 Base44 Pro APK Compiler (Cloud Engine)")
    
    if st.button("🏗️ Trigger Remote Cloud Build & Get APK", type="primary", use_container_width=True):
        if not github_token or not github_repo:
            st.error("👈 කරුණාකර වම් පස ඇති Sidebar එකෙන් ඔබගේ GitHub Token සහ Repository Name එක ලබා දී සිටින්න්න.")
        else:
            headers = {"Authorization": f"token {github_token}", "Accept": "application/vnd.github.v3+json"}
            file_url = f"https://api.github.com/repos/{github_repo}/contents/index.html"
            
            # පරණ ෆයිල් එකක් තිබේ නම් එහි SHA එක ලබා ගැනීම
            sha = ""
            get_res = requests.get(file_url, headers=headers)
            if get_res.status_code == 200: sha = get_res.json()['sha']
            
            encoded_code = base64.b64encode(edited_code.encode('utf-8')).decode('utf-8')
            payload = {"message": "Update AI App Source Code", "content": encoded_code}
            if sha: payload["sha"] = sha
                
            with st.status("Cloud Build Engine එක ක්‍රියාත්මක වෙමින් පවතී...", expanded=True) as status:
                status.write("🔄 කේතය GitHub වෙත Upload කරමින්...")
                push_res = requests.put(file_url, headers=headers, json=payload)
                
                if push_res.status_code in [200, 201]:
                    status.write("🚀 කෝඩ් එක අප්ලෝඩ් වුණා. GitHub Actions පද්ධතිය පණගැන්වීමට තත්පර කිහිපයක් රැඳී සිටින්න...")
                    time.sleep(8) # Race condition එක මඟහරවා ගැනීමට පොඩි විවේකයක්
                    
                    runs_url = f"https://api.github.com/repos/{github_repo}/actions/runs"
                    apk_download_url = None
                    
                    for i in range(20): # උපරිම වට 20ක් (විනාඩි 4ක් පමණ) ලයිව් චෙක් කිරීම
                        run_res = requests.get(runs_url, headers=headers).json()
                        if run_res.get("workflow_runs"):
                            latest_run = run_res["workflow_runs"][0]
                            status_git = latest_run["status"]
                            conclusion = latest_run["conclusion"]
                            
                            status.write(f"⏳ Cloud Compiler තත්ත්වය: **{status_git.upper()}** (වැඩප්‍රගතිය උකහා ගනිමින්...)")
                            
                            if status_git == "completed":
                                if conclusion == "success":
                                    status.write("🎉 APK එක සාර්ථකව නිම කර ඇත!")
                                    artifact_res = requests.get(latest_run["artifacts_url"], headers=headers).json()
                                    if artifact_res.get("artifacts"):
                                        art_id = artifact_res["artifacts"][0]["id"]
                                        apk_download_url = f"https://github.com/{github_repo}/actions/artifacts/{art_id}"
                                    break
                                else:
                                    st.error("❌ Cloud Build එක අසාර්ථක වුණා. ඔබගේ GitHub Actions Actions ලොග් බලන්න.")
                                    break
                        time.sleep(12)
                    
                    if apk_download_url:
                        status.update(label="🎯 APK බිල්ඩ් එක 100% ක් සාර්ථකයි!", state="complete")
                        st.balloons()
                        st.link_button("📥 DOWNLOAD OFFICIAL APK (ZIP)", apk_download_url, use_container_width=True)
                        st.write("💡 *සටහන: ලැබෙන ZIP ගොනුව දිගහැර (Extract) එහි ඇති සැබෑ APK එක දුරකථනයට ස්ථාපනය කරන්න.*")
                    else:
                        st.warning("⚠️ බිල්ඩ් එක නිම වීමට තව සුළු වෙලාවක් ගත වේ. කරුණාකර ඔබගේ GitHub Repository එකෙහි Actions ටැබ් එක පරීක්ෂා කරන්න.")
                else:
                    st.error(f"❌ GitHub එකට කෝඩ් එක දාන්න බැරි වුණා. කරුණාකර Token එක නිවැරදිදැයි බලන්න: {push_res.text}")
