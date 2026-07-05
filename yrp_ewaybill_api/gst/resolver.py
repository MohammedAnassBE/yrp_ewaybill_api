# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

import frappe


def resolve_source(doc_or_row, dotted_path):
	"""Walk a dotted path like 'from_location.gstin' or
	'from_warehouse.supplier.gstin' or (on an item row) 'item_variant.item.hsn_code'.
	Each non-final segment is a Link field whose target doctype we read from meta."""
	if not dotted_path:
		return None
	parts = dotted_path.split(".")
	current_doctype = doc_or_row.doctype
	value = doc_or_row.get(parts[0])
	df = frappe.get_meta(current_doctype).get_field(parts[0])
	for field in parts[1:]:
		if not value:
			return None
		if not df or df.fieldtype != "Link" or not df.options:
			return None
		target_dt = df.options
		value = frappe.db.get_value(target_dt, value, field)
		df = frappe.get_meta(target_dt).get_field(field)
	return value
