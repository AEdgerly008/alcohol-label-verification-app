"""
TTB Alcohol Label Verification App
AI-powered label compliance checking for TTB compliance agents.
"""

import streamlit as st
import anthropic
import base64
import json
import time
from PIL import Image
import io

from verifier import verify_fields, REQUIRED_GOVT_WARNING
from utils import image_to_base64, format_result_badge, build_csv_export

# ── Page config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title="TTB Label Verifier",
    page_icon="🏷️",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Custom CSS ─────────────────────────────────────────────────────────────────

st.markdown("""
<style>
    /* Main palette */
    :root {
        --bourbon: #2C1810;
        --amber: #B5722A;
        --paper: #F5ECD7;
        --pass: #1E3A2F;
        --fail: #8B1A1A;
        --review: #7A4F00;
    }

    .main { background-color: #F0EEE6; }

    /* Header */
    .ttb-header {
        background: #2C1810;
        color: #F5ECD7;
        padding: 18px 28px;
        border-radius: 8px;
        margin-bottom: 24px;
        display: flex;
        align-items: center;
        gap: 14px;
    }
    .ttb-header h1 { margin: 0; font-size: 22px; color: #F5ECD7; }
    .ttb-header p  { margin: 0; font-size: 11px; color: #C4A97D; letter-spacing: 0.08em; text-transform: uppercase; }

    /* Result badges */
    .badge-pass   { background:#1E3A2F; color:#A8D5B5; padding:3px 10px; border-radius:4px; font-family:monospace; font-weight:700; font-size:13px; }
    .badge-fail   { background:#5C0F0F; color:#F4A0A0; padding:3px 10px; border-radius:4px; font-family:monospace; font-weight:700; font-size:13px; }
    .badge-review { background:#3D2B00; color:#F5C842; padding:3px 10px; border-radius:4px; font-family:monospace; font-weight:700; font-size:13px; }
    .badge-na     { background:#2A2A2A; color:#999;    padding:3px 10px; border-radius:4px; font-family:monospace; font-weight:700; font-size:13px; }

    /* Field rows */
    .field-row {
        border-bottom: 1px solid #E8E0D0;
        padding: 10px 0;
        font-size: 14px;
    }
    .field-label {
        font-size: 11px;
        font-weight: 700;
        color: #6B5B45;
        text-transform: uppercase;
        letter-spacing: 0.06em;
    }

    /* Overall stamp */
    .stamp-pass   { color:#1E3A2F; border:4px double #2D5A3D; display:inline-block; padding:8px 20px; border-radius:8px; transform:rotate(-8deg); font-family:monospace; font-size:26px; font-weight:900; letter-spacing:0.15em; }
    .stamp-fail   { color:#8B1A1A; border:4px double #C0392B; display:inline-block; padding:8px 20px; border-radius:8px; transform:rotate(5deg);  font-family:monospace; font-size:26px; font-weight:900; letter-spacing:0.15em; }
    .stamp-review { color:#7A4F00; border:4px double #B5722A; display:inline-block; padding:8px 20px; border-radius:8px; transform:rotate(-3deg); font-family:monospace; font-size:26px; font-weight:900; letter-spacing:0.15em; }

    /* Info box */
    .info-box {
        background: #FFFBE8;
        border: 1px solid #E8D87A;
        border-radius: 6px;
        padding: 10px 14px;
        font-size: 13px;
        color: #7A5F00;
        margin-top: 8px;
    }

    /* Warning reference box */
    .warning-ref {
        background: #FDFAF4;
        border-left: 3px solid #B5722A;
        padding: 10px 14px;
        font-size: 12px;
        font-family: monospace;
        color: #4A3520;
        line-height: 1.6;
        border-radius: 0 4px 4px 0;
        margin: 8px 0;
    }
</style>
""", unsafe_allow_html=True)

# ── Header ─────────────────────────────────────────────────────────────────────

st.markdown("""
<div class="ttb-header">
    <span style="font-size:32px">🏷️</span>
    <div>
        <h1>TTB Label Verifier</h1>
        <p>Alcohol Label Compliance Tool · Prototype · AI-Assisted Review</p>
    </div>
</div>
""", unsafe_allow_html=True)

# ── Tabs ───────────────────────────────────────────────────────────────────────

tab_single, tab_batch, tab_ref = st.tabs(["Single Label", "Batch Review", "Reference"])

# ══════════════════════════════════════════════════════════════════════════════
# SINGLE LABEL TAB
# ══════════════════════════════════════════════════════════════════════════════

with tab_single:

    col_left, col_right = st.columns([1, 1.6], gap="large")

    with col_left:
        st.markdown("#### 1. Upload Label Image")
        uploaded = st.file_uploader(
            "Drop a label image here",
            type=["jpg", "jpeg", "png", "webp"],
            help="Works with angled, glare-affected, or imperfect photos",
        )

        if uploaded:
            image = Image.open(uploaded)
            st.image(image, caption=uploaded.name, use_container_width=True)

            if uploaded.size > 10 * 1024 * 1024:
                st.warning("Image is large (>10MB). Consider compressing for faster results.")

        st.markdown("---")
        st.markdown("#### 2. Application Data")
        st.caption("Enter the expected values from the TTB application. Leave blank to skip that field.")

        brand_name     = st.text_input("Brand Name",       placeholder="e.g. OLD TOM DISTILLERY")
        class_type     = st.text_input("Class / Type",     placeholder="e.g. Kentucky Straight Bourbon Whiskey")
        alcohol_content = st.text_input("Alcohol Content", placeholder="e.g. 45% Alc./Vol. (90 Proof)")
        net_contents   = st.text_input("Net Contents",     placeholder="e.g. 750 mL")
        producer_name  = st.text_input("Producer / Bottler (optional)", placeholder="e.g. Old Tom Distillery LLC")

        run_btn = st.button(
            "▶ Run Verification",
            type="primary",
            disabled=not uploaded,
            use_container_width=True,
        )

    with col_right:
        st.markdown("#### 3. Verification Results")

        if not uploaded:
            st.info("Upload a label image on the left to get started.")

        elif run_btn or st.session_state.get("single_result"):

            # Only re-run if button was just pressed
            if run_btn:
                with st.spinner("Extracting label fields…"):
                    try:
                        img_b64, media_type = image_to_base64(uploaded)
                        client = anthropic.Anthropic()

                        # Step 1: Extract
                        extract_msg = client.messages.create(
                            model="claude-sonnet-4-6",
                            max_tokens=1000,
                            messages=[{
                                "role": "user",
                                "content": [
                                    {
                                        "type": "image",
                                        "source": {"type": "base64", "media_type": media_type, "data": img_b64},
                                    },
                                    {
                                        "type": "text",
                                        "text": """Extract all visible text from this alcohol beverage label. Return ONLY valid JSON with these exact keys. Use null if not present.

{
  "brand_name": "exact brand name as shown",
  "class_type": "class and type designation",
  "alcohol_content": "ABV and proof as shown",
  "net_contents": "volume as shown",
  "producer_name": "bottler/producer/importer name",
  "producer_address": "address as shown",
  "country_of_origin": "country if shown, null if domestic",
  "government_warning": "FULL government warning text EXACTLY as it appears, preserving capitalization",
  "other_text": "any other notable text",
  "image_quality_notes": "note on image quality issues or null if clean"
}"""
                                    },
                                ],
                            }],
                        )
                        raw = extract_msg.content[0].text
                        # Strip markdown fences if present
                        raw = raw.strip()
                        if raw.startswith("```"):
                            raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
                        extracted = json.loads(raw)

                        # Step 2: Verify
                        app_data = {
                            "brand_name": brand_name,
                            "class_type": class_type,
                            "alcohol_content": alcohol_content,
                            "net_contents": net_contents,
                            "producer_name": producer_name,
                        }
                        result = verify_fields(extracted, app_data)
                        st.session_state["single_result"] = result
                        st.session_state["single_extracted"] = extracted

                    except json.JSONDecodeError as e:
                        st.error(f"Could not parse AI response. Try again. ({e})")
                        st.stop()
                    except anthropic.APIError as e:
                        st.error(f"API error: {e}")
                        st.stop()

            result    = st.session_state.get("single_result")
            extracted = st.session_state.get("single_extracted", {})

            if result:
                # ── Overall result ──
                overall = result["overall_result"]
                stamp_class = {"PASS": "stamp-pass", "FAIL": "stamp-fail"}.get(overall, "stamp-review")
                stamp_label = {"PASS": "APPROVED", "FAIL": "REJECTED"}.get(overall, "REVIEW")

                res_col, stamp_col = st.columns([2, 1])
                with res_col:
                    st.markdown(f"**Overall Result:** `{overall}`")
                    if result.get("agent_notes"):
                        st.markdown(f"*{result['agent_notes']}*")
                    for flag in result.get("flags", []):
                        st.markdown(f"⚑ {flag}")
                with stamp_col:
                    st.markdown(f'<div class="{stamp_class}">{stamp_label}</div>', unsafe_allow_html=True)

                st.markdown("---")

                # ── Field breakdown ──
                field_labels = {
                    "brand_name":       "Brand Name",
                    "class_type":       "Class / Type",
                    "alcohol_content":  "Alcohol Content",
                    "net_contents":     "Net Contents",
                    "producer_info":    "Producer / Bottler",
                    "government_warning": "Government Warning",
                }

                for key, label in field_labels.items():
                    field = result["fields"].get(key, {})
                    status = field.get("status", "NOT_PROVIDED")
                    badge_class = {
                        "PASS": "badge-pass",
                        "FAIL": "badge-fail",
                        "NEEDS_REVIEW": "badge-review",
                    }.get(status, "badge-na")

                    with st.container():
                        fc1, fc2, fc3 = st.columns([1.2, 2.5, 0.8])
                        with fc1:
                            st.markdown(f'<span class="field-label">{label}</span>', unsafe_allow_html=True)
                        with fc2:
                            lv = field.get("label_value") or "—"
                            av = field.get("application_value") or ""
                            st.markdown(f"`{lv}`")
                            if av and av != lv and status != "NOT_PROVIDED":
                                st.caption(f"App: {av[:80]}{'…' if len(av) > 80 else ''}")
                            if field.get("note"):
                                st.caption(f"⚠ {field['note']}")
                        with fc3:
                            st.markdown(f'<span class="{badge_class}">{status}</span>', unsafe_allow_html=True)
                        st.markdown('<hr style="margin:4px 0;border-color:#E8E0D0">', unsafe_allow_html=True)

                # ── Image quality note ──
                if extracted.get("image_quality_notes"):
                    st.markdown(f'<div class="info-box">📷 <strong>Image notes:</strong> {extracted["image_quality_notes"]}</div>', unsafe_allow_html=True)

                # ── CSV export ──
                st.markdown("---")
                csv_data = build_csv_export([{"filename": uploaded.name, **result}])
                st.download_button(
                    "⬇ Export Results (CSV)",
                    data=csv_data,
                    file_name=f"ttb_verification_{uploaded.name.rsplit('.',1)[0]}.csv",
                    mime="text/csv",
                )


# ══════════════════════════════════════════════════════════════════════════════
# BATCH TAB
# ══════════════════════════════════════════════════════════════════════════════

with tab_batch:
    st.markdown("#### Batch Label Review")
    st.caption("Upload multiple label images. Government Warning is checked for each. Select a completed row to see its full report.")

    batch_files = st.file_uploader(
        "Upload label images",
        type=["jpg", "jpeg", "png", "webp"],
        accept_multiple_files=True,
        key="batch_uploader",
    )

    if batch_files:
        st.markdown(f"**{len(batch_files)} image(s) queued**")

        if st.button("▶ Run Batch Verification", type="primary"):
            client = anthropic.Anthropic()
            batch_results = []
            progress = st.progress(0, text="Starting…")

            for i, bf in enumerate(batch_files):
                progress.progress((i) / len(batch_files), text=f"Processing {bf.name} ({i+1}/{len(batch_files)})…")
                try:
                    img_b64, media_type = image_to_base64(bf)

                    extract_msg = client.messages.create(
                        model="claude-sonnet-4-6",
                        max_tokens=1000,
                        messages=[{
                            "role": "user",
                            "content": [
                                {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": img_b64}},
                                {"type": "text", "text": """Extract all visible text from this alcohol beverage label. Return ONLY valid JSON:
{
  "brand_name": null, "class_type": null, "alcohol_content": null,
  "net_contents": null, "producer_name": null, "producer_address": null,
  "country_of_origin": null,
  "government_warning": "FULL warning text EXACTLY as shown",
  "image_quality_notes": null
}"""},
                            ],
                        }],
                    )
                    raw = extract_msg.content[0].text.strip()
                    if raw.startswith("```"):
                        raw = raw.split("\n", 1)[1].rsplit("```", 1)[0]
                    extracted = json.loads(raw)
                    result = verify_fields(extracted, {})
                    batch_results.append({"filename": bf.name, "extracted": extracted, "result": result, "error": None})
                except Exception as e:
                    batch_results.append({"filename": bf.name, "extracted": {}, "result": None, "error": str(e)})

            progress.progress(1.0, text="Done!")
            st.session_state["batch_results"] = batch_results

        # Display batch results table
        if st.session_state.get("batch_results"):
            results = st.session_state["batch_results"]

            st.markdown("---")
            st.markdown("**Summary**")

            # Summary table
            summary_rows = []
            for r in results:
                if r["error"]:
                    summary_rows.append({"File": r["filename"], "Result": "ERROR", "Flags": r["error"]})
                else:
                    overall = r["result"].get("overall_result", "?")
                    flags   = "; ".join(r["result"].get("flags", [])) or "—"
                    summary_rows.append({"File": r["filename"], "Result": overall, "Flags": flags})

            import pandas as pd
            df = pd.DataFrame(summary_rows)
            st.dataframe(df, use_container_width=True, hide_index=True)

            # Detail expanders
            st.markdown("**Detail View**")
            for r in results:
                icon = {"PASS": "✅", "FAIL": "❌", "NEEDS_REVIEW": "⚠️"}.get(
                    r["result"].get("overall_result") if r["result"] else "ERROR", "🔴"
                )
                with st.expander(f"{icon} {r['filename']}"):
                    if r["error"]:
                        st.error(r["error"])
                    else:
                        res = r["result"]
                        st.markdown(f"**Result:** `{res['overall_result']}`")
                        if res.get("agent_notes"):
                            st.markdown(f"*{res['agent_notes']}*")
                        for key, field in res["fields"].items():
                            st.markdown(f"- **{key}**: `{field.get('label_value','—')}` → `{field.get('status','?')}`"
                                        + (f" — {field['note']}" if field.get("note") else ""))

            # Batch CSV export
            all_csv = build_csv_export([
                {"filename": r["filename"], **(r["result"] or {})}
                for r in results if r["result"]
            ])
            st.download_button(
                "⬇ Export All Results (CSV)",
                data=all_csv,
                file_name="ttb_batch_verification.csv",
                mime="text/csv",
            )


# ══════════════════════════════════════════════════════════════════════════════
# REFERENCE TAB
# ══════════════════════════════════════════════════════════════════════════════

with tab_ref:
    st.markdown("#### Required Government Warning")
    st.markdown("The following text must appear **exactly** on every alcohol beverage label, with `GOVERNMENT WARNING:` in all-caps:")
    st.markdown(f'<div class="warning-ref">{REQUIRED_GOVT_WARNING}</div>', unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("#### Required Label Fields (Distilled Spirits)")

    fields_table = [
        ("Brand Name", "Required", "Case-insensitive match accepted"),
        ("Class / Type Designation", "Required", "e.g. Kentucky Straight Bourbon Whiskey"),
        ("Alcohol Content (ABV)", "Required", "Must show % Alc./Vol. and optionally proof"),
        ("Net Contents", "Required", "e.g. 750 mL"),
        ("Name & Address of Bottler/Producer", "Required", "Full address required"),
        ("Country of Origin", "Required for imports", "Must state country of origin"),
        ("Government Warning Statement", "Required", "Must be verbatim, GOVERNMENT WARNING: in all-caps"),
    ]

    import pandas as pd
    st.dataframe(
        pd.DataFrame(fields_table, columns=["Field", "Requirement", "Notes"]),
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("---")
    st.caption("Reference: TTB Beverage Alcohol Manual · ttb.gov · This prototype is not a substitute for full TTB regulatory review.")


# ── Footer ─────────────────────────────────────────────────────────────────────

st.markdown("---")
st.markdown(
    '<p style="text-align:center;font-size:11px;color:#B4A898;font-family:monospace">'
    'TTB LABEL VERIFIER · PROTOTYPE · NOT FOR PRODUCTION USE · AI-ASSISTED · AGENT REVIEW REQUIRED'
    '</p>',
    unsafe_allow_html=True,
)
