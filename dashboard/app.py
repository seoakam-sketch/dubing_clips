import os

import requests
import streamlit as st

API_BASE_URL = os.environ.get("API_BASE_URL", "http://localhost:8000")

st.set_page_config(page_title="Clip + Dub Dashboard", layout="wide")
st.title("پلتفرم برش خودکار ویدیو + دوبله فارسی")

tab_new, tab_review, tab_status = st.tabs(["ویدیوی جدید", "تایید کلیپ‌ها", "وضعیت Job‌ها"])

with tab_new:
    st.subheader("افزودن لینک یوتیوب")
    url = st.text_input("لینک یوتیوب")
    if st.button("شروع پردازش", type="primary") and url:
        resp = requests.post(f"{API_BASE_URL}/videos", json={"source_url": url}, timeout=30)
        if resp.ok:
            st.success(f"ویدیو ثبت شد: {resp.json()['id']}")
        else:
            st.error(f"خطا: {resp.text}")

    st.divider()
    st.subheader("ویدیوهای موجود")
    videos_resp = requests.get(f"{API_BASE_URL}/videos", timeout=30)
    if videos_resp.ok:
        for v in videos_resp.json():
            st.write(f"**{v.get('title') or v['source_url']}** — status: `{v['status']}` — id: `{v['id']}`")
            if v.get("error"):
                st.caption(f"خطا: {v['error']}")

with tab_review:
    st.subheader("تایید / ویرایش کلیپ‌های پیشنهادی")
    video_id_filter = st.text_input("فیلتر بر اساس video_id (اختیاری)")
    params = {"video_id": video_id_filter} if video_id_filter else {}
    candidates_resp = requests.get(f"{API_BASE_URL}/clip-candidates", params=params, timeout=30)

    if candidates_resp.ok:
        for c in candidates_resp.json():
            with st.container(border=True):
                cols = st.columns([3, 1, 1, 1, 1])
                cols[0].markdown(f"**{c.get('title_suggestion') or '(بدون عنوان)'}**\n\n{c.get('reason') or ''}")
                new_start = cols[1].number_input(
                    "شروع (ثانیه)", value=float(c["start"]), key=f"start-{c['id']}"
                )
                new_end = cols[2].number_input(
                    "پایان (ثانیه)", value=float(c["end"]), key=f"end-{c['id']}"
                )
                cols[3].write(f"امتیاز: {c.get('score', 0):.2f}")
                cols[4].write(f"وضعیت: `{c['status']}`")

                btn_cols = st.columns(3)
                if btn_cols[0].button("ذخیره ویرایش", key=f"save-{c['id']}"):
                    requests.patch(
                        f"{API_BASE_URL}/clip-candidates/{c['id']}",
                        json={"start": new_start, "end": new_end},
                        timeout=30,
                    )
                    st.rerun()
                if btn_cols[1].button("تایید ✅", key=f"approve-{c['id']}"):
                    requests.post(
                        f"{API_BASE_URL}/clip-candidates/{c['id']}/decision",
                        json={"status": "approved"},
                        timeout=30,
                    )
                    st.rerun()
                if btn_cols[2].button("رد ❌", key=f"reject-{c['id']}"):
                    requests.post(
                        f"{API_BASE_URL}/clip-candidates/{c['id']}/decision",
                        json={"status": "rejected"},
                        timeout=30,
                    )
                    st.rerun()
    else:
        st.info("کلیپی یافت نشد.")

with tab_status:
    st.subheader("وضعیت Job‌ها")
    jobs_resp = requests.get(f"{API_BASE_URL}/jobs", timeout=30)
    if jobs_resp.ok:
        st.dataframe(jobs_resp.json(), use_container_width=True)
