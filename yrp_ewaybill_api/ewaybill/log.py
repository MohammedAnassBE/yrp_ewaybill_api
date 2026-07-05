# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

import frappe


def create_ewb_log(**kwargs):
	"""Insert a new YRP E-Waybill Log row.

	Audit-log rule (mirrors SMS Notification Log): always insert with
	`ignore_permissions` and `ignore_links` so the log is written regardless of
	the acting user's role or transient link state.
	"""
	log = frappe.get_doc({"doctype": "YRP E-Waybill Log", **kwargs})
	log.insert(ignore_permissions=True, ignore_links=True)
	return log


def update_ewb_log(name, **kwargs):
	"""Update an existing YRP E-Waybill Log row and save it."""
	log = frappe.get_doc("YRP E-Waybill Log", name)
	for fieldname, value in kwargs.items():
		log.set(fieldname, value)
	log.flags.ignore_links = True
	log.save(ignore_permissions=True)
	return log
