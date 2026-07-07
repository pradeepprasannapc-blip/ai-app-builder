import streamlit as st

st.set_page_config(page_title="AI App Builder", page_icon="🤖", layout="wide")
st.title("🤖 AI App Builder - Control Panel")
st.success("Repositories 8ම සාර්ථකව සම්බන්ධ කර ඇත!")

st.sidebar.header("🔑 API Configurations")
st.sidebar.text_input("Supabase Project URL", placeholder="https://your-project.supabase.co")
st.sidebar.text_input("Supabase Anon API Key", type="password")
st.sidebar.text_input("Google Gemini AI Key", type="password")

st.write("### 📂 Your Connected Repositories")
st.code("""
1. cli
2. javascript-sdk
3. apps-examples
4. skills
5. kotlin-sdk
6. swift-sdk
7. homebrew-tap
8. openclaw-onboarding
""")

st.info("මීළඟට අපි Supabase (Database) සහ Gemini (AI) Keys මෙතැනට සම්බන්ධ කරමු.")
