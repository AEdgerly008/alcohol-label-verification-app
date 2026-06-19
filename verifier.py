"""
verifier.py — TTB label compliance verification logic.

Compares AI-extracted label fields against application data
and the mandatory government warning statement.
"""

import re
from difflib import SequenceMatcher

# ── Required Government Warning ────────────────────────────────────────────────

REQUIRED_GOVT_WARNING = (
    "GOVERNMENT WARNING: (1) According to the Surgeon General, women should not "
    "drink alcoholic beverages during pregnancy because of the risk of birth defects. "
    "(2) Consumption of alcoholic beverages impairs your ability to drive a car or "
    "operate machinery, and may cause health problems."
)

# ── Similarity threshold (0–1) ────────────────────────────────────────────────

GOVT_WARNING_THRESHOLD = 0.92   # Strict: warning must be very close to exact
FIELD_MATCH_THRESHOLD   = 0.80   # Looser: handles minor OCR noise


# ── Helper utilities ──────────────────────────────────────────────────────────

def _similarity(a: str, b: str) -> float:
    """Return a 0–1 similarity score between two strings (case-insensitive)."""
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a.strip().lower(), b.strip().lower()).ratio()


def _normalize_abv(text: str) -> str | None:
    """Extract the numeric ABV value from a string like '45% Alc./Vol.' → '45'."""
    if not text:
        return None
    m = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    return m.group(1) if m else None


def _normalize_volume(text: str) -> str | None:
    """Normalize net contents: '750 mL', '750ml', '750ML' → '750ml'."""
    if not text:
        return None
    text = text.lower().replace(" ", "")
    m = re.search(r"(\d+(?:\.\d+)?)(ml|l|oz|fl\.?oz\.?)", text)
    if m:
        return f"{m.group(1)}{m.group(2).replace('.','')}"
    return text.strip()


def _field_result(status: str, label_value, application_value, note: str = "") -> dict:
    return {
        "status": status,
        "label_value": str(label_value) if label_value is not None else None,
        "application_value": str(application_value) if application_value is not None else None,
        "note": note,
    }


# ── Individual field checks ───────────────────────────────────────────────────

def check_brand_name(label_val: str | None, app_val: str | None) -> dict:
    """Case-insensitive brand name check. Flags if application value provided."""
    if not app_val:
        return _field_result("NOT_PROVIDED", label_val, None, "No application value entered.")
    if not label_val:
        return _field_result("FAIL", None, app_val, "Brand name not found on label.")

    sim = _similarity(label_val, app_val)
    if label_val.strip().lower() == app_val.strip().lower():
        return _field_result("PASS", label_val, app_val)
    elif sim >= FIELD_MATCH_THRESHOLD:
        return _field_result(
            "NEEDS_REVIEW", label_val, app_val,
            f"Minor difference detected (similarity {sim:.0%}). Likely the same — confirm visually."
        )
    else:
        return _field_result(
            "FAIL", label_val, app_val,
            f"Brand name mismatch (similarity {sim:.0%})."
        )


def check_class_type(label_val: str | None, app_val: str | None) -> dict:
    if not app_val:
        return _field_result("NOT_PROVIDED", label_val, None)
    if not label_val:
        return _field_result("FAIL", None, app_val, "Class/type not found on label.")

    sim = _similarity(label_val, app_val)
    if sim >= FIELD_MATCH_THRESHOLD:
        return _field_result("PASS", label_val, app_val)
    return _field_result("FAIL", label_val, app_val, f"Class/type mismatch (similarity {sim:.0%}).")


def check_alcohol_content(label_val: str | None, app_val: str | None) -> dict:
    if not app_val:
        return _field_result("NOT_PROVIDED", label_val, None)
    if not label_val:
        return _field_result("FAIL", None, app_val, "Alcohol content not found on label.")

    label_abv = _normalize_abv(label_val)
    app_abv   = _normalize_abv(app_val)

    if label_abv and app_abv:
        if label_abv == app_abv:
            return _field_result("PASS", label_val, app_val)
        else:
            return _field_result(
                "FAIL", label_val, app_val,
                f"ABV mismatch: label shows {label_abv}%, application shows {app_abv}%."
            )

    # Fallback to similarity if parsing fails
    sim = _similarity(label_val, app_val)
    if sim >= FIELD_MATCH_THRESHOLD:
        return _field_result("PASS", label_val, app_val)
    return _field_result("FAIL", label_val, app_val, f"Alcohol content mismatch (similarity {sim:.0%}).")


def check_net_contents(label_val: str | None, app_val: str | None) -> dict:
    if not app_val:
        return _field_result("NOT_PROVIDED", label_val, None)
    if not label_val:
        return _field_result("FAIL", None, app_val, "Net contents not found on label.")

    lv_norm = _normalize_volume(label_val)
    av_norm = _normalize_volume(app_val)

    if lv_norm and av_norm and lv_norm == av_norm:
        return _field_result("PASS", label_val, app_val)

    sim = _similarity(label_val, app_val)
    if sim >= FIELD_MATCH_THRESHOLD:
        return _field_result("PASS", label_val, app_val)
    return _field_result("FAIL", label_val, app_val, f"Net contents mismatch.")


def check_producer(label_val: str | None, app_val: str | None) -> dict:
    if not app_val:
        return _field_result("NOT_PROVIDED", label_val, None)
    if not label_val:
        return _field_result("FAIL", None, app_val, "Producer/bottler not found on label.")

    sim = _similarity(label_val, app_val)
    if sim >= FIELD_MATCH_THRESHOLD:
        return _field_result("PASS", label_val, app_val)
    return _field_result(
        "NEEDS_REVIEW", label_val, app_val,
        f"Producer name differs (similarity {sim:.0%}). Confirm visually."
    )


def check_government_warning(label_val: str | None) -> dict:
    """
    Strict government warning check.
    Rules:
      1. 'GOVERNMENT WARNING:' must appear in all-caps.
      2. Full warning text must be present and very close to the required text.
    """
    required = REQUIRED_GOVT_WARNING

    if not label_val:
        return _field_result(
            "FAIL", None, required,
            "Government warning not found on label."
        )

    # Rule 1: All-caps check
    if "GOVERNMENT WARNING:" not in label_val:
        # Check if lowercase version exists (common violation)
        lv_lower = label_val.lower()
        if "government warning" in lv_lower:
            return _field_result(
                "FAIL", label_val, required,
                "'GOVERNMENT WARNING:' must appear in all caps. "
                "Label appears to use title case or lowercase — this is a compliance violation."
            )
        else:
            return _field_result(
                "FAIL", label_val, required,
                "'GOVERNMENT WARNING:' header not found on label."
            )

    # Rule 2: Text similarity
    sim = _similarity(label_val, required)
    if sim >= GOVT_WARNING_THRESHOLD:
        return _field_result("PASS", label_val, required)
    elif sim >= 0.75:
        return _field_result(
            "NEEDS_REVIEW", label_val, required,
            f"Warning text differs from required language (similarity {sim:.0%}). Review exact wording."
        )
    else:
        return _field_result(
            "FAIL", label_val, required,
            f"Warning text significantly differs from required language (similarity {sim:.0%})."
        )


# ── Master verifier ───────────────────────────────────────────────────────────

def verify_fields(extracted: dict, application: dict) -> dict:
    """
    Run all field checks and return a structured verification report.

    Args:
        extracted:   Dict of fields extracted from the label image by AI.
        application: Dict of expected values from the TTB application form.

    Returns:
        Dict with overall_result, per-field results, flags, and agent_notes.
    """

    fields = {
        "brand_name": check_brand_name(
            extracted.get("brand_name"),
            application.get("brand_name"),
        ),
        "class_type": check_class_type(
            extracted.get("class_type"),
            application.get("class_type"),
        ),
        "alcohol_content": check_alcohol_content(
            extracted.get("alcohol_content"),
            application.get("alcohol_content"),
        ),
        "net_contents": check_net_contents(
            extracted.get("net_contents"),
            application.get("net_contents"),
        ),
        "producer_info": check_producer(
            extracted.get("producer_name"),
            application.get("producer_name"),
        ),
        "government_warning": check_government_warning(
            extracted.get("government_warning"),
        ),
    }

    # Determine overall result
    statuses = [f["status"] for f in fields.values()]
    flags = []

    if "FAIL" in statuses:
        overall = "FAIL"
        fail_fields = [k for k, v in fields.items() if v["status"] == "FAIL"]
        flags = [f"FAIL: {k.replace('_', ' ').title()}" for k in fail_fields]
    elif "NEEDS_REVIEW" in statuses:
        overall = "NEEDS_REVIEW"
        review_fields = [k for k, v in fields.items() if v["status"] == "NEEDS_REVIEW"]
        flags = [f"REVIEW: {k.replace('_', ' ').title()}" for k in review_fields]
    else:
        overall = "PASS"

    # Build agent notes
    if overall == "PASS":
        agent_notes = "All checked fields match the application data. Government warning is present and correct."
    elif overall == "FAIL":
        fail_list = ", ".join(k.replace("_", " ").title() for k in fail_fields)
        agent_notes = (
            f"Verification failed on: {fail_list}. "
            "Review flagged fields before approving this application."
        )
    else:
        review_list = ", ".join(k.replace("_", " ").title() for k in review_fields)
        agent_notes = (
            f"Minor discrepancies found in: {review_list}. "
            "These may be acceptable formatting differences — agent judgment required."
        )

    return {
        "overall_result": overall,
        "fields": fields,
        "flags": flags,
        "agent_notes": agent_notes,
    }
