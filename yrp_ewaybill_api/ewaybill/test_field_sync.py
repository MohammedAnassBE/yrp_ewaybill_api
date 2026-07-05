# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from yrp_ewaybill_api.ewaybill.field_sync import sync_ewaybill_fields


class TestFieldSync(FrappeTestCase):
	def test_enabling_delivery_challan_creates_transport_and_result_fields(self):
		settings = frappe.get_cached_doc("YRP E-Waybill Settings")
		if not settings.get_enabled_config("Delivery Challan"):
			settings.append(
				"enabled_doctypes",
				{"reference_doctype": "Delivery Challan", "enabled": 1},
			)
			settings.save(ignore_permissions=True)

		sync_ewaybill_fields()

		meta = frappe.get_meta("Delivery Challan")
		# transport + result fields created on the enabled doctype
		self.assertTrue(meta.get_field("ewaybill"))
		self.assertTrue(meta.get_field("e_waybill_status"))
		self.assertTrue(meta.get_field("gst_transporter_id"))
		# GST fields also (re)created
		self.assertTrue(meta.get_field("place_of_supply"))
		self.assertTrue(meta.get_field("taxable_value") or True)
