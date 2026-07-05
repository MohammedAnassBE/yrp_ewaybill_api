# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from yrp_ewaybill_api.gst.rates import get_gst_rate


class TestRates(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("YRP HSN GST Rate", {"hsn_code": "61091000"})
		frappe.get_doc({
			"doctype": "YRP HSN GST Rate",
			"hsn_code": "61091000",
			"gst_rate": 5,
			"gst_treatment": "Taxable",
		}).insert(ignore_permissions=True)

	def test_known_hsn(self):
		r = get_gst_rate("61091000")
		self.assertEqual(r["gst_rate"], 5)
		self.assertEqual(r["gst_treatment"], "Taxable")

	def test_unknown_hsn_is_nil(self):
		r = get_gst_rate("99999999")
		self.assertEqual(r["gst_rate"], 0)
		self.assertEqual(r["gst_treatment"], "Nil-Rated")
