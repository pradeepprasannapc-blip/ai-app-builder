import streamlit as st
from supabase import create_client
import google.generativeai as genai

st.set_page_config(page_title="AI App Builder", page_icon="🤖", layout="wide")
st.title("🤖 AI App Builder")

# Secrets වලින් Default Keys ගැනීම (තිබුණොත් විතරක්)
default_supa_url = st.secrets.get("SUPABASE_URL", "")
default_supa_key = st.secrets.get("SUPABASE_KEY", "")
default_gemini_key = st.secrets.get("GEMINI_KEY", "")

# Sidebar එකේ Keys ලබාගැනීම (Default values එක්ක)
st.sidebar.header("🔑 API Configurations")
supabase_url = st.sidebar.text_input("Supabase Project URL", value=default_supa_url, type="password")
supabase_key = st.sidebar.text_input("Supabase Anon API Key", value=default_supa_key, type="password")
gemini_key = st.sidebar.text_input("Google Gemini API Key", value=default_gemini_key, type="password")

if supabase_url and supabase_key and gemini_key:
    # Database සහ AI සම්බන්ධ කිරීම
    try:
        supabase = create_client(supabase_url, supabase_key)
        genai.configure(api_key=gemini_key)
        model = genai.GenerativeModel('gemini-pro')
        
        st.success("✅ Database සහ AI සාර්ථකව සම්බන්ධ විය!")

        # ඇප් එකේ ප්‍රධාන කොටස
        st.write("### 📂 Repositories")
        repos = ["cli", "javascript-sdk", "apps-examples", "skills", "kotlin-sdk", "swift-sdk", "homebrew-tap", "openclaw-onboarding"]
        selected_repo = st.selectbox("Select a Repository to Analyze", repos)
        
        user_query = st.text_input(f"What do you want to build or know about '{selected_repo}'?")

        if st.button("Ask AI"):
            if user_query:
                with st.spinner("AI is thinking..."):
                    try:
                        # AI එකෙන් පිළිතුරු ගැනීම
                        response = model.generate_content(f"Analyze the {selected_repo} repository context and answer this: {user_query}")
                        st.info(response.text)
                        
                        # අසපු දේ Supabase Database එකට සේව් කිරීම
                        supabase.table("ai_logs").insert({"repo": selected_repo, "query": user_query}).execute()
                        st.toast("✅ Saved to Database!")
                        
                    except Exception as e:
                        st.error(f"Error: {e}")
            else:
                st.warning("කරුණාකර ප්‍රශ්නයක් ඇතුළත් කරන්න.")
    except Exception as e:
        st.error(f"Connection Error: කරුණාකර ඔබගේ Keys නිවැරදිදැයි පරීක්ෂා කරන්න. ({e})")
else:
    st.warning("👈 කරුණාකර Sidebar එකට Supabase Keys සහ Gemini Key එක ඇතුළත් කරන්න.")
