import streamlit as st
import google.generativeai as genai
import streamlit.components.v1 as components
import re

# --- 1. PAGE CONFIGURATION & PREMIUM UI ---
st.set_page_config(page_title="Pro AI App Factory", page_icon="⚡", layout="wide")

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
    </style>
""", unsafe_allow_html=True)

# --- 2. SIDEBAR (Model Selector) ---
with st.sidebar:
    st.title("⚙️ Control Panel")
    gemini_key = st.text_input("Gemini API Key", type="password")
    
    st.markdown("---")
    st.subheader("🤖 AI Model Selector")
    
    # 2.5 මාදිලි ඇතුළත් ලැයිස්තුව
    model_options = [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-1.5-flash",
        "gemini-1.5-pro"
    ]
    selected_model = st.selectbox("Select Model:", model_options, index=0)
    st.info(f"දැනට ක්‍රියාත්මක: **{selected_model}**")

# --- 3. MAIN INTERFACE ---
st.title("⚡ AI App Factory (Base44 Premium Builder)")
st.write("ඔබගේ අදහස ලබා දෙන්න. AI විසින් අතිශය ආකර්ෂණීය (Premium) යෙදුමක් තත්පර ගණනකින් සාදා දෙනු ඇත.")

user_input = st.text_area("ඔබට අවශ්‍ය ඇප් එක ගැන විස්තර කරන්න:", height=120, placeholder="උදා: Trading signals පෙන්නන ලස්සන Dark Mode ඇප් එකක්...")

# --- 4. ENGINE START ---
if st.button("🚀 GENERATE MASTER APP", use_container_width=True):
    if not gemini_key:
        st.error("👈 කරුණාකර ප්‍රථමයෙන් වම් පස ඇති Sidebar එකට Gemini API Key එක ලබා දෙන්න.")
    elif not user_input:
        st.warning("⚠️ කරුණාකර ඔබගේ අදහස ඇතුළත් කරන්න.")
    else:
        with st.spinner(f"Using {selected_model} to build your Premium App... කරුණාකර රැඳී සිටින්න..."):
            try:
                genai.configure(api_key=gemini_key)
                model = genai.GenerativeModel(selected_model)
                
                # සුපිරි Premium පෙනුමක් ලබාගැනීමට AI එකට දෙන දැඩි උපදෙස් (Master Prompt)
                master_prompt = f"""
                ඔබ ලෝකයේ සිටින අති දක්ෂතම 'Premium Mobile App UI/UX Designer' සහ 'Frontend Developer' කෙනෙක්. Base44 වැනි ලෝක මට්ටමේ SaaS පද්ධති වල UI නිර්මාණය කිරීම ඔබේ විශේෂත්වයයි.
                
                පරිශීලකයාගේ ඉල්ලීම: {user_input}
                
                කරුණාකර පහත දැඩි නීතිරීති වලට අනුව සම්පූර්ණ ඇප් එක (Single HTML file) සාදන්න:
                
                1. **UI Framework:** අනිවාර්යයෙන්ම Tailwind CSS (CDN හරහා) භාවිතා කරන්න. (`<script src="https://cdn.tailwindcss.com"></script>`)
                2. **Design Language (Premium Look):**
                   - සම්පූර්ණයෙන්ම නවීන Dark Mode එකක් භාවිතා කරන්න (උදා: bg-slate-900).
                   - Glassmorphism effects (backdrop-blur, bg-white/10) භාවිතා කරන්න.
                   - බටන් සහ වැදගත් කොටස් සඳහා Neon/Gradients (උදා: bg-gradient-to-r from-cyan-500 to-blue-500) භාවිතා කරන්න.
                   - Soft shadows සහ rounded-2xl/rounded-3xl borders අනිවාර්ය වේ.
                3. **Typography & Icons:** 'Poppins' හෝ 'Inter' Google Font එක සහ FontAwesome අයිකන භාවිතා කරන්න.
                4. **Responsiveness:** ජංගම දුරකථන (Mobile-first) සඳහා 100% ක් ගැළපෙන සේ UI එක නිර්මාණය කරන්න.
                5. **Interactivity:** ලස්සන Hover effects සහ Animations ඇතුළත් කරන්න. අවශ්‍ය JavaScript කේතයද HTML ගොනුවටම (script tag තුළ) ඇතුළත් කරන්න.

                ඉතා වැදගත්: කේතය (Code) පමණක් ```html සහ ``` යන සලකුණු අතර ලබා දෙන්න. වෙනත් කිසිදු අමතර විස්තරයක් කේතය තුළට නොදාන්න.
                """
                
                response = model.generate_content(master_prompt)
                full_text = response.text
                
                # --- 100% Error-proof Code Extraction (Regex භාවිතා කර ඇත) ---
                html_code = ""
                # පළමුව ```html සහ ``` අතර ඇති දේ සෙවීම
                match = re.search(r'```html(.*?)```', full_text, re.DOTALL | re.IGNORECASE)
                if match:
                    html_code = match.group(1).strip()
                else:
                    # බැරි වුණොත් නිකන්ම ``` සහ ``` අතර ඇති දේ සෙවීම
                    match2 = re.search(r'```(.*?)```', full_text, re.DOTALL)
                    if match2:
                        html_code = match2.group(1).strip()
                    else:
                        # ඒත් බැරි වුණොත් සම්පූර්ණ Text එකම ගැනීම
                        html_code = full_text.strip()
                
                st.success("🎯 ඇප් එක සාර්ථකව නිම කරන ලදී!")
                
                # --- LIVE CODE EDITOR & PREVIEW ---
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    st.subheader("💻 Live Code Editor")
                    edited_code = st.text_area("කේතය (HTML/CSS/JS)", html_code, height=600)
                    
                with col2:
                    st.subheader("📱 Instant Mobile View")
                    # ෆෝන් එකක් වගේ පෙනුම එන Box එක
                    st.markdown('<div style="border: 6px solid #30363d; border-radius: 24px; padding: 10px; background: #000; box-shadow: 0 4px 20px rgba(0,0,0,0.5);">', unsafe_allow_html=True)
                    components.html(edited_code, height=580, scrolling=True)
                    st.markdown('</div>', unsafe_allow_html=True)
                    
            except Exception as e:
                st.error(f"❌ දෝෂයක් මතු විය: {e}")
