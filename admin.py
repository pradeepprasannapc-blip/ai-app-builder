import streamlit as st
from supabase import create_client
import time
from datetime import datetime, timedelta, timezone
import re
import requests
import io
import zipfile

def get_admin_db():
    return create_client(st.secrets["SUPABASE_URL"].strip(), st.secrets.get("SUPABASE_SERVICE_KEY", st.secrets["SUPABASE_KEY"]).strip())

def get_system_settings():
    try:
        admin_db = get_admin_db()
        res = admin_db.table("system_settings").select("*").in_("setting_key", ["pricing", "payment_details"]).execute()
        return {r["setting_key"]: r["setting_value"] for r in res.data} if res.data else {}
    except: return {}

def render_admin_settings():
    st.markdown("### ⚙️ Admin Settings (Pricing & Payments)")
    settings = get_system_settings()
    pricing = settings.get("pricing", {"silver_price": 2500, "gold_price": 5000})
    # ඔයාගේ සැබෑ විස්තර Default විදිහටම දැම්මා
    payment = settings.get("payment_details", {
        "ipay_num": "0757970703", 
        "ipay_name": "w.k.pradeep prasanna", 
        "boc_num": "88314511", 
        "boc_name": "W.K.P.P.SENEVIRATHNA"
    })
    
    with st.form("admin_settings_form"):
        st.subheader("📦 Packages")
        sp = st.number_input("Silver Price", value=int(pricing.get("silver_price", 2500)))
        gp = st.number_input("Gold Price", value=int(pricing.get("gold_price", 5000)))
        
        st.subheader("🏦 Payment Accounts")
        ipay_num = st.text_input("iPay Number", value=payment.get("ipay_num"))
        ipay_name = st.text_input("iPay Name", value=payment.get("ipay_name"))
        boc_num = st.text_input("BOC Flex Num", value=payment.get("boc_num"))
        boc_name = st.text_input("BOC Flex Name", value=payment.get("boc_name"))
        
        if st.form_submit_button("💾 Save Changes", type="primary"):
            try:
                admin_db = get_admin_db()
                admin_db.table("system_settings").delete().in_("setting_key", ["pricing", "payment_details"]).execute()
                admin_db.table("system_settings").insert([
                    {"setting_key": "pricing", "setting_value": {"silver_price": sp, "gold_price": gp}},
                    {"setting_key": "payment_details", "setting_value": {"ipay_num": ipay_num, "ipay_name": ipay_name, "boc_num": boc_num, "boc_name": boc_name}}
                ]).execute()
                st.success("✅ දත්ත යාවත්කාලීන විය!"); time.sleep(1); st.rerun()
            except Exception as e:
                st.error(f"Error saving settings: {e}")

def render_god_mode():
    st.markdown("### ⚡ God Mode (User Management)")
    admin_db = get_admin_db()
    users_res = admin_db.table("users").select("*").execute()
    
    if users_res.data:
        for u in users_res.data:
            role_str = str(u.get('role') or 'user').upper()
            pkg_str = str(u.get('package') or 'free').upper()
            email_str = u.get('email') or f"User ID: {u['id'][:8]}..."
            
            ip_str = "No IP logged"
            country_str = "Unknown"
            try:
                logs = admin_db.table("device_logs").select("ip_address, country").eq("user_id", u['id']).order("created_at", desc=True).limit(1).execute()
                if logs.data: 
                    ip_str = logs.data[0]['ip_address']
                    country_str = logs.data[0].get('country', 'Unknown')
            except: pass

            plain_pass = u.get('plain_password') or "තවම ලබාගෙන නැත"

            with st.expander(f"👤 {email_str} | Role: {role_str} | Pkg: {pkg_str}"):
                st.write(f"**Full User ID:** `{u['id']}`")
                st.write(f"**Last IP Address:** `{ip_str}` | **Country:** `{country_str}`")
                st.write(f"**Password:** `{plain_pass}` 🔑")
                
                c1, c2, c3 = st.columns(3)
                with c1:
                    roles = ["user", "moderator", "admin", "owner"]
                    current_role = role_str.lower() if role_str.lower() in roles else "user"
                    new_role = st.selectbox("Update Role:", roles, index=roles.index(current_role), key=f"role_{u['id']}")
                    if st.button("Change Role", key=f"btn_role_{u['id']}"):
                        admin_db.table("users").update({"role": new_role}).eq("id", u['id']).execute()
                        st.success("Role updated!"); st.rerun()
                with c2:
                    statuses = ["active", "suspended", "banned"]
                    current_status = str(u.get('status', 'active')).lower()
                    new_status = st.selectbox("Update Status:", statuses, index=statuses.index(current_status), key=f"status_{u['id']}")
                    if st.button("Change Status", key=f"btn_status_{u['id']}"):
                        admin_db.table("users").update({"status": new_status}).eq("id", u['id']).execute()
                        st.success("Status updated!"); st.rerun()
                with c3:
                    st.write("Danger Zone:")
                    if st.button("🗑️ Delete User", type="primary", key=f"del_user_{u['id']}"):
                        try:
                            # 1st attempt: True Deletion via API
                            admin_db.auth.admin.delete_user(u['id'])
                            st.success("User completely deleted!")
                        except Exception as e:
                            # 2nd attempt: Soft Delete / Ban (Fallback if API key lacks permissions)
                            admin_db.table("users").update({"status": "banned"}).eq("id", u['id']).execute()
                            st.warning("Hard delete API failed. User has been completely BANNED instead.")
                        time.sleep(2); st.rerun()
                
                st.markdown("---")
                c4, c5 = st.columns(2)
                with c4:
                    pkg_options = ["free", "silver", "gold"]
                    current_pkg = str(u.get('package') or 'free').lower()
                    current_index = pkg_options.index(current_pkg) if current_pkg in pkg_options else 0
                    new_pkg = st.selectbox("Change Package:", pkg_options, index=current_index, key=f"pkg_{u['id']}")
                    if st.button("Update Package", key=f"btn_pkg_{u['id']}"):
                        admin_db.table("users").update({"package": new_pkg}).eq("id", u['id']).execute()
                        st.success("Updated!"); st.rerun()
                with c5:
                    bonus_days = st.number_input("Add Bonus Days:", min_value=1, max_value=365, value=7, key=f"days_{u['id']}")
                    if st.button("🎁 Give Bonus", key=f"btn_bns_{u['id']}"):
                        base_date = datetime.fromisoformat(u['expires_at'].replace('Z', '+00:00')) if u.get('expires_at') else datetime.now(timezone.utc)
                        new_expiry = (base_date + timedelta(days=bonus_days)).isoformat()
                        admin_db.table("users").update({"expires_at": new_expiry}).eq("id", u['id']).execute()
                        st.success(f"Added {bonus_days} days!"); st.rerun()

def render_payment_approvals():
    st.markdown("### 💰 Pending Approvals")
    admin_db = get_admin_db()
    payments_res = admin_db.table("payments").select("*").eq("status", "pending").execute()
    if not payments_res.data: st.info("අනුමත කිරීමට ගෙවීම් නොමැත."); return
    for pay in payments_res.data:
        with st.expander(f"Payment ID: #{pay['id']} - Pkg: {pay.get('package_name')} ({pay.get('duration_days', 30)} Days)"):
            st.markdown(f"**Slip:** [Click here to view]({pay.get('slip_url', '#')})")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Approve", key=f"app_{pay['id']}", use_container_width=True, type="primary"):
                    admin_db.table("payments").update({"status": "approved"}).eq("id", pay['id']).execute()
                    new_expiry_date = (datetime.now(timezone.utc) + timedelta(days=pay.get('duration_days', 30))).isoformat()
                    admin_db.table("users").update({"package": pay.get('package_name', 'free'), "expires_at": new_expiry_date}).eq("id", pay['user_id']).execute()
                    st.rerun()
            with col2:
                if st.button("❌ Reject", key=f"rej_{pay['id']}", use_container_width=True):
                    admin_db.table("payments").update({"status": "rejected"}).eq("id", pay['id']).execute(); st.rerun()

def render_admin_app_management():
    st.markdown("### 📱 Global App Management")
    admin_db = get_admin_db()
    all_apps_res = admin_db.table("generated_apps").select("*").order("created_at", desc=True).execute()
    
    if all_apps_res.data:
        for app in all_apps_res.data:
            vis_text = "Public 👁️" if app.get('is_visible', True) else "Private 🔒"
            with st.expander(f"📦 {app.get('app_name', 'Untitled')} | Status: {app.get('status')} | {vis_text}"):
                st.write(f"**App ID:** `{app['id']}`")
                
                cA, cB = st.columns(2)
                with cA:
                    vis = app.get('is_visible', True)
                    if st.button("🔴 Hide App" if vis else "🟢 Make Public", key=f"v_{app['id']}"):
                        admin_db.table("generated_apps").update({"is_visible": not vis}).eq("id", app['id']).execute()
                        st.rerun()
                with cB:
                    if st.button("🗑️ Force Delete", key=f"fd_{app['id']}", type="primary"):
                        admin_db.table("generated_apps").delete().eq("id", app['id']).execute()
                        st.rerun()
                
                # Admin can download/edit ANY user app here
                if app.get('status') == 'completed':
                    st.markdown("---")
                    current_code = app.get('app_code', '')
                    t1, t2 = st.tabs(["🧑‍💻 Admin Edit Code", "📥 Download ZIP"])
                    with t1:
                        edited_code = st.text_area("කේතය (Code):", value=current_code, height=350, key=f"a_edit_{app['id']}")
                        if st.button("💾 Admin Force Save", key=f"a_save_{app['id']}"):
                            admin_db.table("generated_apps").update({"app_code": edited_code}).eq("id", app['id']).execute()
                            st.success("Admin Saved!"); time.sleep(1); st.rerun()
                    with t2:
                        zip_buffer = io.BytesIO()
                        with zipfile.ZipFile(zip_buffer, "a", zipfile.ZIP_DEFLATED, False) as zip_file:
                            zip_file.writestr("app.py", current_code)
                            zip_file.writestr("requirements.txt", "streamlit\nsupabase\npg8000\nrequests\n")
                        st.download_button("Download Admin ZIP", data=zip_buffer.getvalue(), file_name=f"{app['app_name']}_admin.zip", mime="application/zip", key=f"a_zip_{app['id']}")
