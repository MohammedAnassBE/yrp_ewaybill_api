# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from yrp_ewaybill_api.ewaybill.log import create_ewb_log, update_ewb_log


class TestEWBLog(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("YRP E-Waybill Log", {"e_waybill_number": "TESTEWB000001"})

	def test_create_and_update_round_trip(self):
		# create
		log = create_ewb_log(
			e_waybill_number="TESTEWB000001",
			reference_doctype="YRP E-Waybill Log",
			status="Generated",
			is_sandbox=1,
			created_on="2026-07-05 10:00:00",
			data='{"ewayBillNo": "TESTEWB000001"}',
		)
		self.assertEqual(log.name, "TESTEWB000001")
		self.assertEqual(log.status, "Generated")
		self.assertEqual(log.is_cancelled, 0)

		# it persisted
		reloaded = frappe.get_doc("YRP E-Waybill Log", "TESTEWB000001")
		self.assertEqual(reloaded.e_waybill_number, "TESTEWB000001")
		self.assertEqual(reloaded.is_sandbox, 1)

		# update flips is_cancelled + status
		updated = update_ewb_log(
			"TESTEWB000001",
			is_cancelled=1,
			status="Cancelled",
			cancelled_on="2026-07-05 12:00:00",
		)
		self.assertEqual(updated.is_cancelled, 1)
		self.assertEqual(updated.status, "Cancelled")

		reloaded = frappe.get_doc("YRP E-Waybill Log", "TESTEWB000001")
		self.assertEqual(reloaded.is_cancelled, 1)
		self.assertEqual(reloaded.status, "Cancelled")
