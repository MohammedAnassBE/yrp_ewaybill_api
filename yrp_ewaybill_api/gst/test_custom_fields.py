# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

MODULE = "YRP E-Waybill Integration"


class TestEwaybillCustomFields(FrappeTestCase):
	def test_delivery_challan_parent_gst_fields(self):
		meta = frappe.get_meta("Delivery Challan")
		self.assertTrue(meta.get_field("company_gstin"))
		self.assertTrue(meta.get_field("party_gstin"))
		self.assertTrue(meta.get_field("place_of_supply"))
		self.assertTrue(meta.get_field("gst_category"))
		self.assertTrue(meta.get_field("total_taxable_value"))
		self.assertTrue(meta.get_field("total_cgst_amount"))

	def test_delivery_challan_item_gst_fields(self):
		meta = frappe.get_meta("Delivery Challan Item")
		self.assertTrue(meta.get_field("gst_hsn_code"))
		self.assertTrue(meta.get_field("taxable_value"))
		self.assertTrue(meta.get_field("igst_rate"))
		self.assertTrue(meta.get_field("cess_amount"))

	def test_custom_fields_are_fixture_owned(self):
		fields = frappe.get_all(
			"Custom Field",
			filters={"module": MODULE},
			fields=["dt", "fieldname"],
		)
		self.assertTrue(fields)
		fieldnames = {field.fieldname for field in fields if field.dt == "Delivery Challan"}
		for expected in ("transporter", "vehicle_no", "ewaybill", "e_waybill_status"):
			if expected != "vehicle_no":  # standard field on Delivery Challan
				self.assertIn(expected, fieldnames)

	def test_popup_owned_fields_are_read_only(self):
		for fieldname in (
			"company_gstin",
			"party_gstin",
			"place_of_supply",
			"gst_category",
			"transporter",
			"gst_transporter_id",
			"mode_of_transport",
			"gst_vehicle_type",
			"lr_no",
			"lr_date",
			"distance",
		):
			self.assertEqual(
				frappe.db.get_value(
					"Custom Field",
					{"dt": "Delivery Challan", "fieldname": fieldname},
					"read_only",
				),
				1,
			)
