"""
utils.py — Shared utility functions for the TTB Label Verifier.
"""

import base64
import io
import csv
from PIL import Image


# ── Image helpers ─────────────────────────────────────────────────────────────

def image_to_base64(uploaded_file) -> tuple[str, str]:
    """
    Convert a Streamlit UploadedFile to a base64 string and detect media type.

    Returns:
        (base64_string, media_type)  e.g. ("...", "image/jpeg")
    """
    content_type = uploaded_file.type or "image/jpeg"

    # Normalise media type
    ext = uploaded_file.name.rsplit(".", 1)[-1].lower()
    type_map = {
        "jpg":  "image/jpeg",
        "jpeg": "image/jpeg",
        "png":  "image/png",
        "webp": "image/webp",
        "gif":  "image/gif",
    }
    media_type = type_map.get(ext, content_type)

    raw = uploaded_file.read()
    uploaded_file.seek(0)          # Reset so callers can re-read if needed

    # Optionally downscale very large images to stay within API limits (~5 MB)
    try:
        img = Image.open(io.BytesIO(raw))
        max_dim = 2048
        if max(img.size) > max_dim:
            img.thumbnail((max_dim, max_dim), Image.LANCZOS)
            buf = io.BytesIO()
            fmt = "JPEG" if media_type == "image/jpeg" else "PNG"
            img.save(buf, format=fmt, quality=85)
            raw = buf.getvalue()
    except Exception:
        pass  # If PIL can't open it, send as-is

    return base64.b64encode(raw).decode("utf-8"), media_type


# ── Result formatting ─────────────────────────────────────────────────────────

def format_result_badge(status: str) -> str:
    """Return an emoji badge for a field status."""
    return {
        "PASS":         "✅",
        "FAIL":         "❌",
        "NEEDS_REVIEW": "⚠️",
        "NOT_PROVIDED": "—",
    }.get(status, "?")


# ── CSV export ────────────────────────────────────────────────────────────────

def build_csv_export(results: list[dict]) -> str:
    """
    Build a CSV string from a list of verification result dicts.

    Each result dict should have:
        filename, overall_result, fields (dict), flags (list), agent_notes

    Returns:
        CSV as a string.
    """
    field_keys = [
        "brand_name",
        "class_type",
        "alcohol_content",
        "net_contents",
        "producer_info",
        "government_warning",
    ]

    headers = ["filename", "overall_result", "agent_notes", "flags"]
    for k in field_keys:
        headers += [f"{k}_status", f"{k}_label_value", f"{k}_note"]

    output = io.StringIO()
    writer = csv.writer(output, quoting=csv.QUOTE_MINIMAL)
    writer.writerow(headers)

    for r in results:
        if not r:
            continue
        row = [
            r.get("filename", ""),
            r.get("overall_result", ""),
            r.get("agent_notes", ""),
            "; ".join(r.get("flags", [])),
        ]
        fields = r.get("fields", {})
        for k in field_keys:
            f = fields.get(k, {})
            row += [
                f.get("status", ""),
                f.get("label_value", ""),
                f.get("note", ""),
            ]
        writer.writerow(row)

    return output.getvalue()
