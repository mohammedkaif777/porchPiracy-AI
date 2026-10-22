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

    @st.fragment(run_every=2)
    def _monitor() -> None:
        _render_video_monitor()

    _monitor()


def _render_video_monitor() -> None:
    """Refresh video status and show only events belonging to the selected upload."""
    st.subheader("Recent Videos")
    try:
        videos = api_client.get_videos(limit=10)
    except Exception as exc:
        error_state(str(exc))
        videos = []

    if videos:
        for video in videos:
            status = video.get("status", "")
            progress = float(video.get("progress") or 0)
            st.markdown(f"**{video.get('filename', 'unknown')}** — {status} ({progress:.0%})")
            if status == "FAILED":
                st.error(video.get("error") or "Analysis failed. No failure details were returned.")
            if status == "ANALYZING":
                st.progress(min(max(progress, 0.0), 1.0))
            video_id = video.get("video_id")
            label = "Retry analysis" if status == "FAILED" else "Analyze"
            if (
                status in {"UPLOADED", "FAILED"}
                and video_id
                and st.button(label, key=f"an-{video_id}")
            ):
                try:
                    api_client.analyze_video(str(video_id))
                    st.rerun()
                except Exception as exc:
                    error_state(str(exc))
    else:
        empty_state("No Videos", "Upload a video to get started.")
        return

    by_id = {str(video["video_id"]): video for video in videos}
    selected_id = st.selectbox(
        "Video to inspect",
        options=list(by_id),
        format_func=lambda value: f"{by_id[value]['filename']} ({value[:8]})",
        key="monitor_video_id",
    )
    st.subheader("Event Stream")
    st.caption("Events from the selected video only.")
    try:
        events = api_client.get_events(limit=50, video_id=selected_id)
        if api_client.using_mock():
            st.warning(
                "The backend is unavailable or demo mode is enabled. Video detections are unavailable."
            )
            return
        selected = by_id[selected_id]
        if selected.get("status") == "FAILED":
            st.warning("Analysis failed. Any events below are partial results from this video.")
        if events:
            event_feed(events, max_items=30)
            st.subheader("Event Timeline")
            timeline(events)
        else:
            st.info("No detection events recorded for this video.")
    except Exception as exc:
        error_state(str(exc))


render()
