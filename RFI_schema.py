# schemas.py
RFI_SCHEMA_JSON = r"""
{
  "type": "object",
  "required": ["supplier_name", "contact_email", "coverage_regions", "delivery_time_days",
               "iso_27001", "sla_summary", "pricing_notes", "exceptions", "attachments"],
  "properties": {
    "supplier_name": {"type":"string"},
    "contact_email": {"type":"string"},
    "coverage_regions": {"type":"array", "items":{"type":"string"}},
    "delivery_time_days": {"type":"integer"},
    "iso_27001": {"type":"string", "enum":["yes","no","unclear"]},
    "sla_summary": {"type":"string"},
    "pricing_notes": {"type":"string"},
    "exceptions": {"type":"array", "items":{"type":"string"}},
    "attachments": {"type":"array", "items":{"type":"string"}},
    "sources": {"type":"array", "items":{"type":"string"}}
  }
}
"""

# Buyer requirements you care about (edit per category)
REQUIREMENTS = {
    "must_have": ["iso_27001"],
    "nice_to_have": []
}

def gap_checks(record: dict) -> dict:
    """Return {missing:[], follow_ups:[], risks:[]} derived from record."""
    missing, follow_ups, risks = [], [], []
    # Required fields present?
    for f in ["supplier_name","contact_email","coverage_regions","delivery_time_days","iso_27001","sla_summary"]:
        if not record.get(f):
            missing.append(f)

    # ISO evidence
    if record.get("iso_27001") in ["no","unclear"]:
        follow_ups.append("Provide ISO 27001 certificate or explain compensating controls.")

    # Delivery sanity
    try:
        if int(record.get("delivery_time_days", -1)) <= 0:
            follow_ups.append("Confirm delivery_time_days; non-positive value detected.")
    except Exception:
        follow_ups.append("delivery_time_days not numeric; please clarify.")

    # Pricing notes present?
    if not record.get("pricing_notes"):
        follow_ups.append("Share pricing model and inclusions/exclusions (e.g., VAT, support).")

    return {"missing": missing, "follow_ups": follow_ups, "risks": risks}
