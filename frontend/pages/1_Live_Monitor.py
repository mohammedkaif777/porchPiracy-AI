"""Live Monitor — real-time event feed and video upload."""

from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.components import empty_state, error_state, event_feed, timeline
from frontend.styles import GLOBAL_CSS


def render() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.header("📹 Live Monitor")
    st.caption("Upload a video or view the live event stream.")

    # --- Video upload ---
    st.subheader("Upload Video")
    uploaded = st.file_uploader("Choose a porch video", type=["mp4", "mov", "avi", "mkv"])
    if uploaded is not None:
        # Save temporarily and upload.
        import tempfile
        from pathlib import Path

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp.write(uploaded.getbuffer())
            tmp_path = tmp.name
        try:
            result = api_client.upload_video(tmp_path)
            st.success(f"✅ Uploaded: {result.get('filename')} → {result.get('video_id', '?')[:8]}")
            if st.button("▶️ Start Analysis"):
                api_client.analyze_video(result["video_id"])
                st.info("Analysis started in background. Refresh to see progress.")
        except Exception as exc:
            error_state(str(exc))

    st.divider()

    # --- Videos list ---
    st.subheader("Recent Videos")
    try:
        videos = api_client.get_videos(limit=10)
        if videos:
            for v in videos:
                status_emoji = {"UPLOADED": "📤", "ANALYZING": "⏳", "COMPLETED": "✅", "FAILED": "❌"}.get(
                    v.get("status", ""), "❓"
                )
                progress = v.get("progress", 0)
                st.markdown(
                    f'{status_emoji} **{v.get("filename", "unknown")}** — '
                    f'{v.get("status", "UNKNOWN")} ({progress:.0%})'
                )
                if v.get("status") == "ANALYZING":
                    st.progress(progress)
        else:
            empty_state("No Videos", "Upload a video to get started.")
    except Exception as exc:
        error_state(str(exc))

    st.divider()

    # --- Event stream ---
    st.subheader("Event Stream")
    try:
        events = api_client.get_events(limit=50)
        event_feed(events, max_items=30)
        if events:
            st.subheader("📊 Event Timeline")
            timeline(events)
    except Exception as exc:
        error_state(str(exc))


render()
