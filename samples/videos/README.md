# Sample Videos

Drop test video clips here. They are **gitignored**.

Supported formats: `.mp4`, `.mov`, `.avi`, `.mkv`, `.m4v`, `.webm`.

The analysis pipeline (`POST /videos/{id}/analyze`) accepts any of these formats,
runs the YOLO detector per frame, and writes an annotated copy to `data/annotated/`.

## Recommended test clips

| Clip | Duration | Content |
|---|---|---|
| `porch_delivery.mp4` | ~15 s | A delivery person dropping off a package |
| `porch_loiterer.mp4` | ~20 s | Someone lingering near a package for > 10 s |
| `porch_theft.mp4` | ~20 s | Someone grabbing a package and leaving |
| `porch_passerby.mp4` | ~10 s | A pedestrian walking past, no interaction |

Record your own clips with a phone or use a royalty-free porch video from YouTube.
