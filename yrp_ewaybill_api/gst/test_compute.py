import frappe
from frappe.tests.utils import FrappeTestCase

from yrp_ewaybill_api.gst.compute import compute_gst_details


class TestComputeGSTDetails(FrappeTestCase):
	def setUp(self):
		frappe.db.delete("YRP HSN GST Rate", {"hsn_code": "61091000"})
		frappe.get_doc(
			{
				"doctype": "YRP HSN GST Rate",
				"hsn_code": "61091000",
				"gst_rate": 18,
				"gst_treatment": "Taxable",
			}
		).insert(ignore_permissions=True)

	def _fake_doc(self, party_gstin):
		# frappe._dict fake doc + item rows (no DB record needed for the math).
		# NOTE: read the rows via doc.get("items") — on a frappe._dict, `doc.items`
		# resolves to the built-in dict.items method, not the seeded list.
		return frappe._dict(
			company_gstin="33AAAAA0000A1Z5",
			party_gstin=party_gstin,
			gst_category="Registered Regular",
			items=[
				frappe._dict(amount=1000, qty=10, gst_hsn_code="61091000"),
				frappe._dict(amount=500, qty=5, gst_hsn_code="61091000"),
			],
		)

	def test_intra_state_splits_into_cgst_sgst(self):
		# company & place-of-supply both state 33 -> CGST + SGST, no IGST
		doc = self._fake_doc(party_gstin="33BBBBB0000B1Z5")
		compute_gst_details(doc)
		rows = doc.get("items")
		self.assertEqual(doc.place_of_supply, "33-Tamil Nadu")
		self.assertEqual(rows[0].taxable_value, 1000)
		self.assertEqual(rows[0].cgst_rate, 9)
		self.assertEqual(rows[0].cgst_amount, 90)
		self.assertEqual(rows[0].sgst_amount, 90)
		self.assertEqual(rows[0].igst_amount, 0)
		self.assertEqual(doc.total_cgst_amount, 135)  # 90 + 45
		self.assertEqual(doc.total_sgst_amount, 135)
		self.assertEqual(doc.total_igst_amount, 0)
		self.assertEqual(doc.total_taxable_value, 1500)

	def test_total_value_includes_untaxed_lines(self):
		# A line whose HSN is not in YRP HSN GST Rate -> Nil-Rated (0 tax) but its
		# value MUST still count toward total_taxable_value, else the NIC totalValue
		# won't reconcile with the emitted item list (a reject / understated bill).
		doc = frappe._dict(
			company_gstin="33AAAAA0000A1Z5",
			party_gstin="33BBBBB0000B1Z5",
			gst_category="Registered Regular",
			items=[
				frappe._dict(amount=1000, qty=10, gst_hsn_code="61091000"),  # 18% taxable
				frappe._dict(amount=500, qty=5, gst_hsn_code="99999999"),  # unmapped -> Nil-Rated
			],
		)
		compute_gst_details(doc)
		rows = doc.get("items")
		self.assertEqual(rows[1].gst_treatment, "Nil-Rated")
		self.assertEqual(rows[1].taxable_value, 500)
		self.assertEqual(rows[1].cgst_amount, 0)
		# total includes BOTH lines' value; tax only from the taxable line
		self.assertEqual(doc.total_taxable_value, 1500)
		self.assertEqual(doc.total_cgst_amount, 90)
		self.assertEqual(doc.total_sgst_amount, 90)

	def test_inter_state_uses_igst(self):
		# party in state 29, company in 33 -> IGST only
		doc = self._fake_doc(party_gstin="29CCCCC0000C1Z5")
		compute_gst_details(doc)
		rows = doc.get("items")
		self.assertEqual(doc.place_of_supply, "29-Karnataka")
		self.assertEqual(rows[0].igst_rate, 18)
		self.assertEqual(rows[0].igst_amount, 180)
		self.assertEqual(rows[0].cgst_amount, 0)
		self.assertEqual(rows[0].sgst_amount, 0)
		self.assertEqual(doc.total_igst_amount, 270)  # 180 + 90
		self.assertEqual(doc.total_cgst_amount, 0)
		self.assertEqual(doc.total_taxable_value, 1500)
