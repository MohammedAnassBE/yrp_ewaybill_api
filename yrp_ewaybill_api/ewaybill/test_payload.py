# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

from unittest.mock import MagicMock, patch

import frappe
from frappe.tests.utils import FrappeTestCase

from yrp_ewaybill_api.ewaybill.payload import (
	build_cancel_payload,
	build_generate_payload,
	build_vehicle_payload,
)

SETTINGS = "yrp_ewaybill_api.ewaybill.payload.get_ewb_settings"


def _mock_settings(sandbox=0):
	s = MagicMock()
	s.sandbox_mode = sandbox
	s.get_enabled_config.return_value = frappe._dict(supply_direction="Outward")
	return s


def _make_computed_doc():
	"""A fake, already-GST-computed Delivery Challan (intra-state, 18%)."""
	return frappe._dict(
		doctype="Delivery Challan",
		name="DC-2026-00001",
		posting_date="2026-07-05",
		company_gstin="33AAAAA0000A1Z5",
		party_gstin="33BBBBB0000B1Z5",
		total_taxable_value=1500,
		total_cgst_amount=135,
		total_sgst_amount=135,
		total_igst_amount=0,
		total_cess_amount=0,
		items=[
			frappe._dict(
				idx=1,
				item_name="T-Shirt",
				gst_hsn_code="61091000",
				qty=10,
				uom="Nos",
				taxable_value=1000,
				cgst_rate=9,
				cgst_amount=90,
				sgst_rate=9,
				sgst_amount=90,
				igst_rate=0,
				igst_amount=0,
				cess_rate=0,
				cess_amount=0,
			),
			frappe._dict(
				idx=2,
				item_name="Cap",
				gst_hsn_code="61091000",
				qty=5,
				uom="Nos",
				taxable_value=500,
				cgst_rate=9,
				cgst_amount=45,
				sgst_rate=9,
				sgst_amount=45,
				igst_rate=0,
				igst_amount=0,
				cess_rate=0,
				cess_amount=0,
			),
		],
	)


class TestPayload(FrappeTestCase):
	def test_generate_payload_item_and_doc_fields(self):
		doc = _make_computed_doc()
		values = {
			"transporter_id": "88AAAAA0000A1Z5",
			"mode_of_transport": "Road",
			"vehicle_no": "tn01ab1234",
			"gst_vehicle_type": "Regular",
			"distance": 12,
		}
		# Production payload (sandbox off) → real from/to GSTINs.
		with patch(SETTINGS, return_value=_mock_settings(sandbox=0)):
			data = build_generate_payload(doc, values)

		self.assertEqual(data["docType"], "CHL")
		self.assertEqual(data["supplyType"], "O")
		self.assertEqual(data["userGstin"], doc.company_gstin)
		self.assertEqual(data["fromGstin"], doc.company_gstin)
		self.assertEqual(data["toGstin"], doc.party_gstin)

		first = data["itemList"][0]
		self.assertEqual(first["hsnCode"], "61091000")
		self.assertEqual(first["taxableAmount"], 1000)
		self.assertEqual(first["cgstRate"], 9)

		self.assertEqual(data["cgstValue"], doc.total_cgst_amount)
		self.assertEqual(data["sgstValue"], doc.total_sgst_amount)

		# Part B: vehicle details present, translated to NIC codes.
		self.assertEqual(data["vehicleNo"], "TN01AB1234")
		self.assertEqual(data["transMode"], 1)
		self.assertEqual(data["vehicleType"], "R")

	def test_sandbox_overrides_to_test_identity(self):
		# In sandbox, from/to are replaced by the GSP test identity (state 05,
		# URP recipient) so the sandbox accepts it — but tax/item data is kept.
		doc = _make_computed_doc()
		with patch(SETTINGS, return_value=_mock_settings(sandbox=1)):
			data = build_generate_payload(doc, {"transporter_id": "88AAAAA0000A1Z5"})
		self.assertEqual(data["userGstin"], "05AAACG2115R1ZN")
		self.assertEqual(data["fromGstin"], "05AAACG2115R1ZN")
		self.assertEqual(data["fromStateCode"], "05")
		self.assertEqual(data["actFromStateCode"], "05")
		self.assertEqual(data["toGstin"], "URP")
		self.assertEqual(data["toStateCode"], "05")
		self.assertEqual(data["transDistance"], 100)
		# Real tax/value data preserved.
		self.assertEqual(data["cgstValue"], 135)
		self.assertEqual(data["itemList"][0]["hsnCode"], "61091000")

	def test_generate_payload_part_a_omits_vehicle(self):
		doc = _make_computed_doc()
		# No vehicle_no -> Part A. transporter_id supplied so it does not raise.
		with patch(SETTINGS, return_value=_mock_settings(sandbox=0)):
			data = build_generate_payload(doc, {"transporter_id": "88AAAAA0000A1Z5"})

		self.assertNotIn("vehicleNo", data)
		self.assertNotIn("transMode", data)
		self.assertNotIn("vehicleType", data)
		self.assertEqual(data["transporterId"], "88AAAAA0000A1Z5")

	def test_part_a_without_transporter_raises(self):
		doc = _make_computed_doc()
		with self.assertRaises(frappe.ValidationError):
			build_generate_payload(doc, {})

	def test_cancel_payload(self):
		data = build_cancel_payload("123456789012", "2", "Order cancelled")
		self.assertEqual(data["ewbNo"], "123456789012")
		self.assertEqual(data["cancelRsnCode"], "2")
		self.assertEqual(data["cancelRmrk"], "Order cancelled")

	def test_vehicle_payload(self):
		data = build_vehicle_payload(
			"123456789012",
			{
				"vehicle_no": "tn10xy9999",
				"mode_of_transport": "Road",
				"gst_vehicle_type": "Regular",
				"reason_code": "2",
				"remark": "break down",
			},
		)
		self.assertEqual(data["ewbNo"], "123456789012")
		self.assertEqual(data["vehicleNo"], "TN10XY9999")
		self.assertEqual(data["transMode"], 1)
		self.assertEqual(data["vehicleType"], "R")
		self.assertEqual(data["reasonCode"], "2")
