# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

import frappe


def get_gst_rate(hsn_code):
	"""Return the GST rate info for an HSN/SAC code.

	Returns a dict with keys ``gst_rate``, ``cess_rate`` and ``gst_treatment``.
	When no ``YRP HSN GST Rate`` row exists for the code, the item is treated
	as ``Nil-Rated`` at 0%.
	"""
	row = frappe.db.get_value(
		"YRP HSN GST Rate", hsn_code,
		["gst_rate", "cess_rate", "gst_treatment"], as_dict=True)
	if not row:
		return {"gst_rate": 0.0, "cess_rate": 0.0, "gst_treatment": "Nil-Rated"}
	return {
		"gst_rate": row.gst_rate or 0.0,
		"cess_rate": row.cess_rate or 0.0,
		"gst_treatment": row.gst_treatment or "Taxable",
	}
