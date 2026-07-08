import streamlit as st
import google.generativeai as genai
import streamlit.components.v1 as components

# --- 1. PAGE CONFIGURATION & PREMIUM UI ---
st.set_page_config(page_title="Base44 Alternative - Pro AI App Factory", page_icon="⚡", layout="wide")

# UI එක ලස්සන කරන්න Custom CSS (මෙහි තිබූ unsafe_scale වැරැද්ද නිවැරදි කර ඇත)
st.markdown("""
    <style>
    .stApp {
        background-color: #0d1117;
        color: #c9d1d9;
    }
    .stButton>button {
        background: linear-gradient(45deg, #4f46e5, #06b6d4);
        color: white;
        border: none;
        padding: 10px 24px;
        border-radius: 8px;
        font-weight: bold;
        transition: 0.3s;
    }
    .stButton>button:hover {
        transform: scale(1.02);
        box-shadow: 0 0 15px rgba(6, 182, 212, 0.4);
    }
    h1, h2, h3 {
        color: #ffffff !important;
        font-family: 'Poppins', sans-serif;
    }
    .sidebar .sidebar-content {
        background-color: #161b22;
    }
    .stTextArea>div>div>textarea {
        background-color: #1e242c;
        color: #58a6ff;
        font-family: monospace;
        border-radius: 8px;
    }
    </style>
""", unsafe_allow_html=True)

# --- 2. SECRETS HANDLING (Error-Proof) ---
default_gemini_key = ""
if hasattr(st, "secrets") and "GEMINI_KEY" in st.secrets:
    default_gemini_key = st.secrets["GEMINI_KEY"]

# --- 3. SIDEBAR (Control Panel) ---
with st.sidebar:
    st.title("⚙️ Control Panel")
    gemini_key = st.text_input("Gemini API Key", value=default_gemini_key, type="password")
    
    st.markdown("---")
    st.subheader("🤖 AI Model Selector")
    st.write("ඔබගේ Key එකට ගැළපෙන හොඳම Model එක තෝරන්න:")
    
    model_options = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-1.5-flash", 
        "gemini-1.5-pro", 
        "gemini-1.0-pro",
        "gemini-pro"
    ]
    selected_model = st.selectbox("Available Models:", model_options, index=0)
    st.info(f"දැනට ක්‍රියාත්මක: **{selected_model}**")
    
    st.markdown("---")
    st.write("🔒 Powered by Streamlit & Gemini AI")

# --- 4. MAIN INTERFACE ---
st.title("⚡ AI App Factory (Premium Builder)")
st.write("Web URL එකක්, GitHub Repo එකක් හෝ ඔබගේ අදහසක් ලබා දී තත්පර කිහිපයකින් සම්පූර්ණ ඇප් එකක් නිර්මාණය කරගන්න.")

# Input ක්‍රම 3ක්
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
        user_context = f"වෙබ් අඩවියේ URL එක: {url_input}. මෙම වෙබ් අඩවියේ ඇති සැලසුම සහ අරමුණ තේරුම් ගෙන ඊට සමාන ජංගම යෙදුමක් (App) නිර්මාණය කරන්න."
        source_info = f"Web URL ({url_input})"

with tab3:
    github_input = st.text_input("GitHub Repo URL එක දමන්න (Public):", placeholder="https://github.com/user/repo")
    if github_input:
        user_context = f"GitHub කේත ගබඩාව: {github_input}. මෙම කේත ගබඩාවේ ඇති අරමුණ තේරුම් ගෙන එයට ගැළපෙන UI එකක් සහිත ඇප් එකක් සාදන්න."
        source_info = f"GitHub Repo ({github_input})"

# --- 5. ENGINE START (App Generation) ---
if st.button("🚀 GENERATE MASTER APP", use_container_width=True):
    if not gemini_key:
        st.error("👈 කරුණාකර ප්‍රථමයෙන් වම් පස ඇති Sidebar එකට Gemini API Key එක ලබා දෙන්න.")
    elif not user_context:
        st.warning("⚠️ කරුණාකර එක Input ක්‍රමයකට හෝ තොරතුරු ඇතුළත් කරන්න (Idea, URL හෝ GitHub).")
    else:
        with st.spinner(f"Using {selected_model} to build your app... කරුණාකර රැඳී සිටින්න..."):
            try:
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel(selected_model)
                
                master_prompt = f"""
                ඔබ ලෝකයේ සිටින අති දක්ෂතම 'Premium Mobile App UI/UX Designer' සහ 'Frontend Developer' කෙනෙක්. Base44 වැනි ලෝක මට්ටමේ SaaS පද්ධති වල UI නිර්මාණය කිරීම ඔබේ විශේෂත්වයයි.
                
                පරිශීලකයාගේ ඉල්ලීම: {user_input}
                
                කරුණාකර පහත දැඩි නීතිරීති වලට අනුව සම්පූර්ණ ඇප් එක (Single HTML file) සාදන්න:
                
                1. **UI Framework:** අනිවාර්යයෙන්ම Tailwind CSS (CDN හරහා) භාවිතා කරන්න. (`<script src="https://cdn.tailwindcss.com"></script>`)
                2. **Design Language (Premium Look):** - සම්පූර්ණයෙන්ම නවීන Dark Mode එකක් භාවිතා කරන්න (උදා: bg-slate-900).
                   - Base44 හි මෙන් Glassmorphism effects (backdrop-blur, bg-white/10) භාවිතා කරන්න.
                   - බටන් සහ වැදගත් කොටස් සඳහා Neon/Gradients (උදා: bg-gradient-to-r from-cyan-500 to-blue-500) භාවිතා කරන්න.
                   - Soft shadows සහ rounded-2xl/rounded-3xl borders අනිවාර්ය වේ.
                3. **Typography & Icons:** 'Poppins' හෝ 'Inter' Google Font එක සහ FontAwesome අයිකන භාවිතා කරන්න.
                4. **Responsiveness:** ජංගම දුරකථන (Mobile-first) සඳහා 100% ක් ගැළපෙන සේ UI එක නිර්මාණය කරන්න. (Bottom navigation bar එකක් අවශ්‍ය නම් එකතු කරන්න).
                5. **Interactivity:** ලස්සන Hover effects සහ සිනිඳු Animations ඇතුළත් කරන්න. අවශ්‍ය JavaScript කේතයද HTML ගොනුවටම (script tag තුළ) ඇතුළත් කරන්න.

                ඉතා වැදගත්: 
                - කේතය (Code) පමණක් ```html සහ ``` යන සලකුණු අතර ලබා දෙන්න. වෙනත් කිසිදු අමතර විස්තරයක් කේතය තුළට නොදාන්න.
                """

                
                response = model.generate_content(master_prompt)
                full_text = response.text
                
                if "```html" in full_text:
                    parts = full_text.split("```html")
                    explanation = parts[0].strip()
                    html_code = parts[1].split("```")[0].strip()
                else:
                    explanation = "මෙන්න ඔබගේ ඇප් එකේ කේතය:"
                    html_code = full_text
                
                st.success("🎯 ඇප් එක සාර්ථකව නිම කරන ලදී!")
                st.info(explanation)
                
                # --- 6. LIVE CODE EDITOR & PREVIEW ---
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.subheader("💻 Live Code Editor")
                    edited_code = st.text_area("කේතය වෙනස් කර Preview එක බලන්න (HTML/CSS/JS)", html_code, height=600)
                    
                with col2:
                    st.subheader("📱 Instant Mobile View")
                    st.markdown('<div style="border: 6px solid #30363d; border-radius: 24px; padding: 10px; background: #000; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">', unsafe_allow_html=True)
                    components.html(edited_code, height=580, scrolling=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                
                # --- 7. APK EXPORT SECTION ---
                st.markdown("---")
                st.subheader("📦 Export Package (APK / AAB)")
                st.write("ඔබගේ ඇප් එක දැන් සූදානම්! මීළඟ අදියරේදී අපි මෙතනින් කෙලින්ම APK එක Download කරගන්නා Cloud Build System එක සම්බන්ධ කරමු.")
                st.button("⚙️ Compile & Download APK (Coming Soon)", disabled=True, use_container_width=True)
                
            except Exception as e:
                st.error(f"❌ {selected_model} මගින් ඇප් එක සෑදීමට නොහැකි විය.")
                st.error(f"Error Details: {e}")
                st.info("💡 උපදෙස්: Sidebar එකෙන් වෙනත් Model එකක් තෝරා (උදා: gemini-1.5-flash) නැවත උත්සාහ කරන්න.")
