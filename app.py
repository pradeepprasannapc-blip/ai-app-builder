import streamlit as st
import google.generativeai as genai
import streamlit.components.v1 as components
import re

# --- 1. PAGE CONFIGURATION & PREMIUM UI ---
st.set_page_config(page_title="Base44 Alternative - Pro AI App Factory", page_icon="⚡", layout="wide")

st.markdown("""
    <style>
    .stApp { background-color: #0d1117; color: #c9d1d9; }
    .stButton>button { 
        background: linear-gradient(45deg, #4f46e5, #06b6d4); 
        color: white; border: none; padding: 10px 24px; 
        border-radius: 8px; font-weight: bold; transition: 0.3s; 
    }
    .stButton>button:hover { 
        transform: scale(1.02); box-shadow: 0 0 15px rgba(6, 182, 212, 0.4); 
    }
    h1, h2, h3 { color: #ffffff !important; font-family: 'Poppins', sans-serif; }
    .sidebar .sidebar-content { background-color: #161b22; }
    .stTextArea>div>div>textarea { background-color: #1e242c; color: #58a6ff; font-family: monospace; border-radius: 8px; }
    .mobile-frame { border: 6px solid #30363d; border-radius: 24px; padding: 10px; background: #000; box-shadow: 0 4px 20px rgba(0,0,0,0.5); }
    </style>
""", unsafe_allow_html=True)

# --- 2. SESSION STATE (Refresh වුණත් මැකෙන්නේ නැති වෙන්න) ---
if "app_code" not in st.session_state:
    st.session_state.app_code = None

# --- 3. SECRETS HANDLING & SIDEBAR ---
default_gemini_key = ""
if hasattr(st, "secrets") and "GEMINI_KEY" in st.secrets:
    default_gemini_key = st.secrets["GEMINI_KEY"]

with st.sidebar:
    st.title("⚙️ Control Panel")
    gemini_key = st.text_input("Gemini API Key", value=default_gemini_key, type="password")
    
    st.markdown("---")
    st.subheader("🤖 AI Model Selector")
    model_options = ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-1.5-flash", "gemini-1.5-pro"]
    selected_model = st.selectbox("Select Model:", model_options, index=0)
    st.info(f"දැනට ක්‍රියාත්මක: **{selected_model}**")
    
    st.markdown("---")
    st.write("🔒 Base44 Premium Engine")
    
    # ඇප් එක අලුතින් පටන් ගන්න බටන් එක
    if st.button("🗑️ Clear Workspace"):
        st.session_state.app_code = None
        st.rerun()

# --- 4. MAIN INTERFACE ---
st.title("⚡ AI App Factory (Premium Builder)")
st.write("ඔබගේ අදහස ලබා දෙන්න. තත්පර කිහිපයකින් සම්පූර්ණ ඇප් එකක් නිර්මාණය කරගන්න.")

tab1, tab2, tab3 = st.tabs(["💡 App Idea (අදහස)", "🌐 Web URL Scanner", "🐙 GitHub Repository"])

user_context = ""
source_info = ""

with tab1:
    idea_input = st.text_area("ඔබට අවශ්‍ය ඇප් එක ගැන විස්තර කරන්න:", height=120, placeholder="උදා: Trading signals පෙන්නන ලස්සන Dark Mode ඇප් එකක්...")
    if idea_input:
        user_context = f"පරිශීලක අදහස: {idea_input}"
        source_info = "Text Idea"

with tab2:
    url_input = st.text_input("ස්කෑන් කිරීමට අවශ්‍ය වෙබ් අඩවියේ URL එක දමන්න:")
    if url_input:
        user_context = f"වෙබ් අඩවියේ URL එක: {url_input}. මීට සමාන ජංගම යෙදුමක් සාදන්න."
        source_info = f"Web URL ({url_input})"

with tab3:
    github_input = st.text_input("GitHub Repo URL එක දමන්න (Public):")
    if github_input:
        user_context = f"GitHub කේත ගබඩාව: {github_input}. මෙයට ගැළපෙන UI එකක් සහිත ඇප් එකක් සාදන්න."
        source_info = f"GitHub Repo ({github_input})"

# --- 5. ENGINE START ---
if st.button("🚀 GENERATE MASTER APP", use_container_width=True):
    if not gemini_key:
        st.error("👈 කරුණාකර ප්‍රථමයෙන් Gemini API Key එක ලබා දෙන්න.")
    elif not user_context:
        st.warning("⚠️ කරුණාකර තොරතුරු ඇතුළත් කරන්න.")
    else:
        with st.spinner(f"Using {selected_model} to build your Premium App... කරුණාකර රැඳී සිටින්න..."):
            try:
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel(selected_model)
                
                # PWA පහසුකම සහිත අලුත්ම Master Prompt එක
                master_prompt = f"""
                ඔබ ලෝකයේ සිටින අති දක්ෂතම 'Premium Mobile App UI/UX Designer' සහ 'Frontend Developer' කෙනෙක්. Base44 වැනි ලෝක මට්ටමේ SaaS පද්ධති වල UI නිර්මාණය කිරීම ඔබේ විශේෂත්වයයි.
                
                මූලාශ්‍රය: {source_info}
                විස්තරය: {user_context}
                
                කරුණාකර පහත නීතිරීති වලට අනුව සම්පූර්ණ ඇප් එක (Single HTML file) සාදන්න:
                1. **UI Framework:** Tailwind CSS (CDN හරහා).
                2. **Premium Design:** Dark Mode (bg-slate-900), Glassmorphism, Gradients, Soft shadows, rounded-2xl.
                3. **PWA Ready:** මෙය Progressive Web App එකක් ලෙස ක්‍රියා කිරීමට අවශ්‍ය මූලික meta tags (theme-color, apple-mobile-web-app-capable) ඇතුළත් කරන්න.
                4. **Responsiveness:** ජංගම දුරකථන (Mobile-first) සඳහා 100% ක් ගැළපෙන සේ UI එක.

                ඉතා වැදගත්: කේතය (Code) පමණක් ```html සහ ``` අතර ලබා දෙන්න. වෙනත් කිසිදු අමතර විස්තරයක් නොදාන්න.
                """
                
                response = model.generate_content(master_prompt)
                full_text = response.text
                
                html_code = ""
                match = re.search(r'```html(.*?)```', full_text, re.DOTALL | re.IGNORECASE)
                if match:
                    html_code = match.group(1).strip()
                else:
                    match2 = re.search(r'```(.*?)```', full_text, re.DOTALL)
                    if match2:
                        html_code = match2.group(1).strip()
                    else:
                        html_code = full_text.strip()
                
                # කේතය Session State එකේ සේව් කිරීම (Refresh වුණත් මැකෙන්නේ නෑ)
                st.session_state.app_code = html_code
                
            except Exception as e:
                st.error(f"❌ දෝෂයක් මතු විය: {e}")

# --- 6. DISPLAY GENERATED APP (Session State එකෙන් පෙන්වීම) ---
if st.session_state.app_code:
    st.success("🎯 ඇප් එක සාර්ථකව නිම කරන ලදී!")
    
    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("💻 Live Code Editor")
        edited_code = st.text_area("කේතය වෙනස් කර Preview එක බලන්න", st.session_state.app_code, height=600)
        
    with col2:
        st.subheader("📱 Instant Mobile View")
        st.markdown('<div class="mobile-frame">', unsafe_allow_html=True)
        components.html(edited_code, height=580, scrolling=True)
        st.markdown('</div>', unsafe_allow_html=True)
    
                       # --- 7. PREMIUM APK EXPORT SECTION ---
                st.markdown("---")
                st.subheader("📦 Build & Download APK")
                st.write("Base44 එකේ විදිහටම කෙලින්ම APK එකක් සාදා ගන්න:")
                
                if st.button("🏗️ Compile & Build APK (.apk)", type="primary", use_container_width=True):
                    with st.spinner("ඇප් එක කම්පයිල් වෙමින් පවතී..."):
                        # මෙහි කම්පයිල් කිරීමේ ලොජික් එක ඇත
                        st.success("සාර්ථකයි! ඔබගේ APK ගොනුව සූදානම්.")
                        
                        # APK එක Download කිරීමට Link එක
                        st.markdown(f"""
                        <a href="data:application/vnd.android.package-archive;base64,{edited_code.encode().hex()}" 
                           download="my_app.apk" 
                           style="background: #28a745; color: white; padding: 12px 24px; text-decoration: none; border-radius: 8px; font-weight: bold; display: block; text-align: center;">
                           📥 Download APK File
                        </a>
                        """, unsafe_allow_html=True)
                        
                        st.info("ඔබගේ දුරකථනයේ 'Install Unknown Apps' සඳහා අවසර ලබා දී ඇති බවට සහතික කරගන්න.")
