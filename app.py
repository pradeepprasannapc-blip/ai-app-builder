import streamlit as st
import google.generativeai as genai
import streamlit.components.v1 as components
from supabase import create_client

st.set_page_config(page_title="Base44 Alternative - AI App Factory", page_icon="⚡", layout="wide")

# 1. Secrets වලින් Keys ගැනීම (දැන් හැමදාම ගහන්න ඕනේ නෑ)
default_supa_url = st.secrets.get("SUPABASE_URL", "")
default_supa_key = st.secrets.get("SUPABASE_KEY", "")
default_gemini_key = st.secrets.get("GEMINI_KEY", "")

# Sidebar 
with st.sidebar:
    st.header("⚙️ පද්ධති සැකසුම්")
    gemini_key = st.text_input("Gemini API Key", value=default_gemini_key, type="password")
    st.markdown("---")
    st.write("අනාගතයේදී මෙතනින් APK Build එකට අදාළ දේවල් පාලනය කරමු.")

st.title("⚡ AI App Factory (Pro Builder)")
st.write("ඕනෑම වෙබ් අඩවියක් හෝ අදහසක් ලබා දී තත්පර ගණනකින් සම්පූර්ණ ඇප් එකක් නිර්මාණය කරගන්න.")

if gemini_key:
    genai.configure(api_key=gemini_key)
    # Gemini Pro Model එක පාවිච්චි කරමු (තාර්කික වැඩ වලට හොඳම)
    model = genai.GenerativeModel('gemini-pro')
    
    # 2. පරිශීලකයාගෙන් තොරතුරු ගැනීම
    user_input = st.text_area("ඔබට අවශ්‍ය ඇප් එක ගැන විස්තර කරන්න (හෝ URL එකක් දෙන්න):", height=100, placeholder="උදා: මට Trading Signals පෙන්නන ලස්සන Dark Mode ඇප් එකක් හදලා දෙන්න...")
    
    if st.button("🚀 Generate App", type="primary"):
        if user_input:
            with st.spinner("AI මොළය ක්‍රියාත්මක වෙමින් පවතී. කරුණාකර රැඳී සිටින්න..."):
                try:
                    # 3. Master Prompt (සිංහලෙන් සහ කේතනයෙන්)
                    prompt = f"""
                    ඔබ ලෝකයේ දක්ෂතම 'Mobile App UI/UX Developer' කෙනෙක්. 
                    පරිශීලකයාගේ ඉල්ලීම: {user_input}
                    
                    කරුණාකර පහත පියවර අනුගමනය කරන්න:
                    1. මුලින්ම, ඔබ මෙම ඇප් එක සැලසුම් කරපු විදිහ සහ එහි ඇති විශේෂාංග ගැන කෙටියෙන් සිංහලෙන් විස්තර කරන්න.
                    2. ඉන්පසු, සම්පූර්ණ App එක සඳහා තනි HTML ගොනුවක් (Single HTML file) නිර්මාණය කරන්න. එහි CSS සඳහා 'Tailwind CSS' (CDN හරහා) සහ අවශ්‍ය නම් JavaScript භාවිතා කරන්න. Mobile-responsive, ඉතාමත් ලස්සන සහ නවීන පෙනුමක් (Base44 මට්ටමේ) ලබා දෙන්න.
                    3. කේතය (Code) පමණක් ```html සහ ``` අතර ලබා දෙන්න.
                    """
                    
                    response = model.generate_content(prompt)
                    full_response = response.text
                    
                    # AI ගේ සිංහල විස්තරය සහ කේතය වෙන් කරගැනීම
                    try:
                        explanation = full_response.split("```html")[0]
                        html_code = full_response.split("```html")[1].split("```")[0]
                    except:
                        explanation = full_response
                        html_code = ""
                        
                    st.success("✅ ඇප් එක සාර්ථකව නිර්මාණය කළා!")
                    st.info(explanation) # සිංහලෙන් විස්තරය පෙන්වීම
                    
                    # 4. Live Preview සහ Editor එක (කොටස් දෙකකට කඩා පෙන්වීම)
                    col1, col2 = st.columns([1, 1])
                    
                    with col1:
                        st.subheader("💻 Code Editor (කේතය වෙනස් කරන්න)")
                        # කේතය Edit කරන්න පුළුවන් text area එකක්
                        edited_code = st.text_area("HTML/CSS/JS Code", html_code, height=500)
                        
                    with col2:
                        st.subheader("📱 App Preview")
                        # Edit කරපු කේතය දකුණු පැත්තෙන් පෙන්වීම
                        components.html(edited_code, height=500, scrolling=True)
                        
                    # (අනාගත අදියර 2 සඳහා තැනක්)
                    st.markdown("---")
                    st.button("📦 Build APK / AAB (Coming Soon)", disabled=True)
                    
                except Exception as e:
                    st.error(f"දෝෂයක් මතු විය: {e}")
        else:
            st.warning("කරුණාකර ඔබගේ අදහස හෝ URL එක ඇතුළත් කරන්න.")
else:
    st.error("කරුණාකර වම් පසින් Gemini API Key එක ඇතුළත් කරන්න.")
