# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

import frappe
from frappe.model.document import Document


class YRPEWaybillLog(Document):
	def before_print(self, settings=None):
		# The print Jinja sandbox can't call frappe.parse_json, so parse the
		# stored full-e-Waybill JSON here and expose it as `doc.ewb`.
		self.ewb = frappe.parse_json(self.data) if self.data else {}
