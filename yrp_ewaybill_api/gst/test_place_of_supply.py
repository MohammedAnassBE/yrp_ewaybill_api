# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from yrp_ewaybill_api.gst.place_of_supply import (
	get_state, state_code_from_gstin, get_place_of_supply, is_inter_state)


class TestPlaceOfSupply(FrappeTestCase):
	def test_get_state(self):
		self.assertEqual(get_state("33"), "Tamil Nadu")

	def test_state_code_from_gstin(self):
		self.assertEqual(state_code_from_gstin("33AAACG2115R1ZN"), "33")
		self.assertIsNone(state_code_from_gstin(""))

	def test_pos_registered_uses_party_gstin(self):
		self.assertEqual(
			get_place_of_supply(party_gstin="29AAAAA0000A1Z5", company_gstin="33AAACG2115R1ZN"),
			"29-Karnataka")

	def test_pos_unregistered_uses_state_code(self):
		self.assertEqual(
			get_place_of_supply(party_gstin=None, company_gstin="33AAACG2115R1ZN",
				party_state_code="27", gst_category="Unregistered"),
			"27-Maharashtra")

	def test_pos_overseas(self):
		self.assertEqual(
			get_place_of_supply(party_gstin=None, company_gstin="33AAACG2115R1ZN",
				gst_category="Overseas"),
			"96-Other Countries")

	def test_inter_state_true_when_pos_differs(self):
		self.assertTrue(is_inter_state("33AAACG2115R1ZN", "29-Karnataka", "Registered Regular"))
		self.assertFalse(is_inter_state("33AAACG2115R1ZN", "33-Tamil Nadu", "Registered Regular"))

	def test_sez_is_always_inter_state(self):
		self.assertTrue(is_inter_state("33AAACG2115R1ZN", "33-Tamil Nadu", "SEZ"))
