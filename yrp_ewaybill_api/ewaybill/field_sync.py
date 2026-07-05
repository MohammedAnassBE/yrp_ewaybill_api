# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

"""Create the e-Waybill custom fields on the base yrp doctypes.

`create_gst_fields()` creates the Phase-1 GST tax-breakup fields on Delivery
Challan (+ item). `sync_ewaybill_fields()` is the settings-driven entry point:
on save of `YRP E-Waybill Settings` it adds the transport + result fields to
every enabled DocType and (re)creates the GST fields. Both are idempotent
(`create_custom_fields(..., update=True)`).
"""

import frappe
from frappe.custom.doctype.custom_field.custom_field import create_custom_fields

from yrp_ewaybill_api.ewaybill.settings import get_ewb_settings
from yrp_ewaybill_api.gst.custom_fields import (
	EWAYBILL_GST_CUSTOM_FIELDS,
	EWAYBILL_TRANSPORT_FIELDS,
	SUPPLIER_EWAYBILL_FIELDS,
)


def _standard_fieldnames(doctype):
	"""Fieldnames already defined as STANDARD (non-custom) fields on `doctype`.
	A new Custom Field colliding with a standard field raises, so we skip those
	and reuse the existing field (e.g. Delivery Challan already has `vehicle_no`).
	Our own previously-created Custom Fields are NOT skipped, so update=True can
	refresh them."""
	custom = set(frappe.get_all("Custom Field", filters={"dt": doctype}, pluck="fieldname"))
	return {df.fieldname for df in frappe.get_meta(doctype).fields} - custom


def _without_standard_collisions(doctype, fields):
	standard = _standard_fieldnames(doctype)
	return [f for f in fields if f["fieldname"] not in standard]


def create_gst_fields():
	"""Create/update the GST tax-breakup custom fields on Delivery Challan (+ item)."""
	safe = {dt: _without_standard_collisions(dt, fields)
		for dt, fields in EWAYBILL_GST_CUSTOM_FIELDS.items()}
	safe = {dt: fields for dt, fields in safe.items() if fields}
	if safe:
		create_custom_fields(safe, update=True)


def create_supplier_fields():
	"""Create/update `is_transporter` + `gst_transporter_id` on Supplier.

	Skipped when india_compliance is installed — it defines these same fields; we
	reuse them rather than reassign their module/ordering and break its fixtures."""
	if "india_compliance" in frappe.get_installed_apps():
		return
	safe = {dt: _without_standard_collisions(dt, fields)
		for dt, fields in SUPPLIER_EWAYBILL_FIELDS.items()}
	safe = {dt: fields for dt, fields in safe.items() if fields}
	if safe:
		create_custom_fields(safe, update=True)


def sync_ewaybill_fields(doc=None):
	"""Create transport + e-Waybill fields on every enabled DocType, plus the GST fields.

	Wired to `YRP E-Waybill Settings` on_update (via the controller, passing the
	just-saved doc) and to after_migrate (doc=None → read the stored single).
	Fields whose name already exists as a STANDARD field on the target are skipped
	(reused). Disabling a row does not delete previously-created fields.
	"""
	settings = doc or get_ewb_settings()
	transport_fields = {}
	for row in settings.enabled_doctypes or []:
		if row.enabled:
			fields = _without_standard_collisions(row.reference_doctype, EWAYBILL_TRANSPORT_FIELDS)
			if fields:
				transport_fields[row.reference_doctype] = fields

	if transport_fields:
		create_custom_fields(transport_fields, update=True)

	create_gst_fields()
	create_supplier_fields()
