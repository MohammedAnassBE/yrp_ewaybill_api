# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

from yrp_ewaybill_api.gst.compute import compute_gst_details
from yrp_ewaybill_api.gst.resolver import resolve_source
from yrp_ewaybill_api.yrp_e_waybill_integration.doctype.yrp_e_waybill_settings.yrp_e_waybill_settings import (
	get_ewb_settings,
)


def update_gst_details(doc, method=None):
	settings = get_ewb_settings()
	row = settings.get_enabled_config(doc.doctype)
	if not row:
		return
	# The company (from / authenticating) GSTIN is a GLOBAL setting — the GSTIN
	# the e-Way Bill is generated from, matched to a credential — NOT the
	# document's from-location. Authoritative from Settings (override any stale
	# cached value); fall back to the configured dotted-path source only if
	# Settings has no company GSTIN.
	doc.company_gstin = settings.get_company_gstin() or resolve_source(doc, row.from_gstin_source)
	# Party (to / recipient) GSTIN is per-document.
	doc.party_gstin = resolve_source(doc, row.to_gstin_source)
	# gst_category default (2026-07-10): the form field is read-only, so derive
	# a sensible category when nothing meaningful set it. A party without a
	# GSTIN left on the field default is Unregistered — treating it as
	# "Registered Regular" would silently mis-split CGST/SGST vs IGST in
	# compute_gst_details. An explicit dialog choice (SEZ / Overseas — both
	# legitimately GSTIN-less flows) is preserved.
	if not doc.get("party_gstin") and (doc.get("gst_category") or "Registered Regular") == "Registered Regular":
		doc.gst_category = "Unregistered"
	elif not doc.get("gst_category"):
		doc.gst_category = "Registered Regular"
	for item in doc.items:
		if not item.get("gst_hsn_code"):
			item.gst_hsn_code = resolve_source(item, row.item_hsn_source)
	compute_gst_details(doc)
