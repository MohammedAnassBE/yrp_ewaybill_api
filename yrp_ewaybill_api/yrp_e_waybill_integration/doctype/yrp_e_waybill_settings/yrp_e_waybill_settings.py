# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

import frappe
from frappe import _
from frappe.model.document import Document


class YRPEWaybillSettings(Document):
	def get_company_gstin(self):
		"""The GSTIN e-Way Bills are generated from (the authenticating / from
		GSTIN). Explicit `company_gstin` wins; otherwise, if exactly one
		credential is configured, use its GSTIN."""
		if self.company_gstin:
			return self.company_gstin
		creds = self.credentials or []
		if len(creds) == 1:
			return creds[0].gstin
		return None

	def get_enabled_config(self, reference_doctype):
		"""Return the enabled-doctype row for `reference_doctype`, or None."""
		for row in self.enabled_doctypes or []:
			if row.reference_doctype == reference_doctype and row.enabled:
				return row
		return None

	def get_credential(self, gstin):
		"""Return {username, password} for a company GSTIN. Raises if missing."""
		for row in self.credentials or []:
			if row.gstin == gstin:
				return {"username": row.username, "password": row.get_password("password")}
		frappe.throw(_("No e-Way Bill portal credential configured for GSTIN {0}").format(gstin))


def get_ewb_settings():
	return frappe.get_cached_doc("YRP E-Waybill Settings")
