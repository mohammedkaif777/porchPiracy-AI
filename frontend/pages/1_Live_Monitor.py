"""Live Monitor — real-time event feed and video upload."""

from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.components import empty_state, error_state, event_feed, timeline
from frontend.styles import GLOBAL_CSS


def render() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.header("📹 Live Monitor")
    st.caption("Upload a porch clip, simulate a delivery, then run analysis.")

    if st.button("📦 Simulate delivery"):
        try:
            result = api_client.simulate_delivery()
            st.success(f"Protection is {result.get('state')}. Source is labeled Simulated.")
            st.rerun()
        except Exception as exc:
            error_state(str(exc))

    st.subheader("Upload Video")
    uploaded = st.file_uploader("Choose a porch video", type=["mp4", "mov", "avi", "mkv"])
    if uploaded is not None and st.button("Upload"):
        try:
            result = api_client.upload_video_bytes(uploaded.name, bytes(uploaded.getbuffer()))
            st.success(f"Uploaded {result.get('filename')}")
            st.rerun()
        except Exception as exc:
            error_state(str(exc))

    st.divider()
    st.subheader("Recent Videos")
    try:
        videos = api_client.get_videos(limit=10)
    except Exception as exc:
        error_state(str(exc))
        videos = []

    analyzing = False
    if videos:
        for video in videos:
            status = video.get("status", "")
            progress = float(video.get("progress") or 0)
            st.markdown(f"**{video.get('filename', 'unknown')}** — {status} ({progress:.0%})")
            if status == "ANALYZING":
                analyzing = True
                st.progress(min(max(progress, 0.0), 1.0))
            video_id = video.get("video_id")
            if status == "UPLOADED" and video_id and st.button("Analyze", key=f"an-{video_id}"):
                try:
                    api_client.analyze_video(str(video_id))
                    st.rerun()
                except Exception as exc:
                    error_state(str(exc))
    else:
        empty_state("No Videos", "Upload a video to get started.")

    run_every = 2 if analyzing else None

    @st.fragment(run_every=run_every)
    def _events() -> None:
        st.subheader("Event Stream")
        try:
            events = api_client.get_events(limit=50)
            event_feed(events, max_items=30)
            if events:
                st.subheader("Event Timeline")
                timeline(events)
        except Exception as exc:
            error_state(str(exc))

    _events()


render()
