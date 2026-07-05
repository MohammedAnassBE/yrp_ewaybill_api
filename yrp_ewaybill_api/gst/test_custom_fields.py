# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from yrp_ewaybill_api.ewaybill.field_sync import create_gst_fields
from yrp_ewaybill_api.gst.custom_fields import (
	EWAYBILL_GST_CUSTOM_FIELDS,
	EWAYBILL_TRANSPORT_FIELDS,
	MODULE,
)


class TestEwaybillCustomFields(FrappeTestCase):
	@classmethod
	def setUpClass(cls):
		super().setUpClass()
		create_gst_fields()

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

	def test_all_gst_definitions_carry_module(self):
		for _dt, fields in EWAYBILL_GST_CUSTOM_FIELDS.items():
			for df in fields:
				self.assertEqual(df["module"], MODULE)
				self.assertIn("fieldname", df)
				self.assertIn("label", df)
				self.assertIn("fieldtype", df)

	def test_transport_definitions_carry_module(self):
		fieldnames = [df["fieldname"] for df in EWAYBILL_TRANSPORT_FIELDS]
		for expected in ("transporter", "vehicle_no", "ewaybill", "e_waybill_status"):
			self.assertIn(expected, fieldnames)
		for df in EWAYBILL_TRANSPORT_FIELDS:
			self.assertEqual(df["module"], MODULE)
