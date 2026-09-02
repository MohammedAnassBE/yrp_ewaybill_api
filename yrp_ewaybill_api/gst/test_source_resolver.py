# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

"""Integration test for the config-driven GST source resolver.

Builds a REAL Delivery Challan (via yrp's own DC test helpers), points the
`YRP EWB Enabled DocType` row for Delivery Challan at the real yrp field
sources (`from_location.gstin`, `supplier.gstin`, `item_variant.item.hsn_code`),
runs `update_gst_details`, and asserts the master data is walked onto the doc
and the GST math runs (company/party GSTIN, per-line HSN + taxable value).
"""

import frappe
from frappe.tests.utils import FrappeTestCase

# Reuse yrp's proven Delivery Challan fixture builders. A DC is built from a
# Work Order (not a Purchase Order), so we lean on the DC-specific helpers in
# test_internal_unit_transfer, which themselves reuse _supplier / _warehouse /
# _process_cost from test_purchase_order_grn.
from yrp.yrp.doctype.delivery_challan.test_internal_unit_transfer import (
	_company_supplier,
	_make_dc,
	_make_wo,
	_non_company_supplier,
	_seed_stock,
)

from yrp_ewaybill_api.gst.source_resolver import update_gst_details

FROM_GSTIN = "33AAACG2115R1ZN"
TO_GSTIN = "33BBBBB0000B1Z5"
HSN_CODE = "61091000"


class TestSourceResolver(FrappeTestCase):
	def _configure_enabled_doctype(self):
		settings = frappe.get_doc("YRP E-Waybill Settings")
		# Company GSTIN in Settings is authoritative. Pin it so this test does
		# not depend on whichever credential is configured on the development site.
		settings.company_gstin = FROM_GSTIN
		settings.set("enabled_doctypes", [])
		settings.append(
			"enabled_doctypes",
			{
				"reference_doctype": "Delivery Challan",
				"enabled": 1,
				"supply_direction": "Outward",
				"from_gstin_source": "from_location.gstin",
				"to_gstin_source": "supplier.gstin",
				"item_hsn_source": "item_variant.item.hsn_code",
			},
		)
		settings.save(ignore_permissions=True)
		frappe.clear_document_cache("YRP E-Waybill Settings", "YRP E-Waybill Settings")

	def _seed_hsn_rate(self):
		frappe.db.delete("YRP HSN GST Rate", {"hsn_code": HSN_CODE})
		frappe.get_doc(
			{
				"doctype": "YRP HSN GST Rate",
				"hsn_code": HSN_CODE,
				"gst_rate": 5,
				"gst_treatment": "Taxable",
			}
		).insert(ignore_permissions=True)

	def test_update_gst_details_populates_from_masters(self):
		self._configure_enabled_doctype()
		self._seed_hsn_rate()

		# from_location = a company-location Supplier, receiver = an external
		# Supplier; both carry a GSTIN so the resolver has something to walk to.
		from_location = _company_supplier("_T_EWB_From")
		receiver = _non_company_supplier("_T_EWB_To")
		frappe.db.set_value("Supplier", from_location, "gstin", FROM_GSTIN)
		frappe.db.set_value("Supplier", receiver, "gstin", TO_GSTIN)

		wo, from_wh, to_wh, item_variant, uom = _make_wo(from_location, receiver, qty=10)
		_seed_stock(item_variant, from_wh, 50)

		# HSN lives on the parent Item (permlevel 1) — set it directly.
		parent_item = frappe.db.get_value("Item Variant", item_variant, "item")
		frappe.db.set_value("Item", parent_item, "hsn_code", HSN_CODE)

		dc = _make_dc(wo, from_wh, to_wh, item_variant, uom, qty=5)
		# Pin a deterministic line amount so taxable_value is stable regardless
		# of stock-valuation quirks; compute reads item.amount straight through.
		dc.items[0].amount = 1000

		update_gst_details(dc)

		self.assertEqual(dc.company_gstin, FROM_GSTIN)
		self.assertEqual(dc.party_gstin, TO_GSTIN)
		self.assertEqual(dc.items[0].gst_hsn_code, HSN_CODE)
		self.assertEqual(dc.items[0].taxable_value, 1000)
		self.assertTrue(dc.items[0].taxable_value)
