# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

"""Unit tests for the e-Waybill enhancements: fetch-existing (match by docNo) and
auto-cancel-on-document-cancel. All mocked (no site / DB / network)."""

import contextlib
import unittest
from unittest.mock import MagicMock, patch

import frappe

from yrp_ewaybill_api.ewaybill import actions as actions_module
from yrp_ewaybill_api.ewaybill import api as api_module
from yrp_ewaybill_api.ewaybill import lifecycle as lifecycle_module
from yrp_ewaybill_api.ewaybill.actions import _ensure_gst_resolved, _find_matching_ewb, fetch_e_waybill
from yrp_ewaybill_api.ewaybill.lifecycle import auto_cancel_ewaybill

COMPANY_GSTIN = "33AAACG2115R1ZN"


class _FakeDoc:
	def __init__(self, ewaybill=None):
		self.doctype = "Delivery Challan"
		self.name = "DC-0001"
		self.company_gstin = COMPANY_GSTIN
		self.ewaybill = ewaybill
		self.e_waybill_status = None

	def get(self, key, default=None):
		return getattr(self, key, default)

	def db_set(self, fieldname, value=None, **kwargs):
		if isinstance(fieldname, dict):
			for k, v in fieldname.items():
				setattr(self, k, v)
		else:
			setattr(self, fieldname, value)


def _settings(auto_cancel=1):
	s = MagicMock()
	s.sandbox_mode = 1
	s.auto_cancel_on_document_cancel = auto_cancel
	s.get_credential.return_value = {"username": "u", "password": "p"}
	return s


class TestFindMatchingEwb(unittest.TestCase):
	def test_plain_list_match(self):
		rows = [{"docNo": "DC-0002", "ewbNo": 1}, {"docNo": "DC-0001", "ewbNo": 2}]
		self.assertEqual(_find_matching_ewb(rows, "DC-0001")["ewbNo"], 2)

	def test_dict_wrapped_list(self):
		wrapped = {"ewayBills": [{"docNo": "DC-0001", "ewbNo": 9}]}
		self.assertEqual(_find_matching_ewb(wrapped, "DC-0001")["ewbNo"], 9)

	def test_no_match_returns_none(self):
		self.assertIsNone(_find_matching_ewb([{"docNo": "DC-9999"}], "DC-0001"))

	def test_cancelled_entry_is_skipped(self):
		rows = [
			{"docNo": "DC-0001", "ewbNo": 1, "status": "CNL"},
			{"docNo": "DC-0001", "ewbNo": 2, "status": "ACT"},
		]
		self.assertEqual(_find_matching_ewb(rows, "DC-0001")["ewbNo"], 2)

	def test_only_cancelled_match_returns_none(self):
		self.assertIsNone(_find_matching_ewb([{"docNo": "DC-0001", "ewbNo": 1, "status": "CNL"}], "DC-0001"))


class TestFetchEWaybill(unittest.TestCase):
	def setUp(self):
		self.doc = _FakeDoc()
		self._patchers = [
			patch.object(api_module, "get_ewb_settings", return_value=_settings()),
			patch.object(actions_module, "get_ewb_settings", return_value=_settings()),
			patch.object(actions_module, "create_ewb_log"),
			# fetch calls _ensure_gst_resolved → update_gst_details; stub it.
			patch("yrp_ewaybill_api.gst.source_resolver.update_gst_details"),
			patch("frappe.has_permission", return_value=True),
			patch("frappe.get_doc", return_value=self.doc),
			patch("frappe.db.exists", return_value=False),
			patch("frappe.msgprint"),
		]
		for p in self._patchers:
			p.start()
			self.addCleanup(p.stop)
		self.create_ewb_log = actions_module.create_ewb_log

	def test_fetch_links_matching_ewb(self):
		api_result = {"success": True, "result": [
			{"docNo": "DC-0001", "ewbNo": 331234567890, "validUpto": "05/07/2026 23:59:00"}]}
		with patch.object(api_module.EWaybillAPI, "get_ewaybills_by_date", return_value=api_result):
			out = fetch_e_waybill("Delivery Challan", "DC-0001", {"e_waybill_date": "2026-07-05"})
		self.assertEqual(self.doc.ewaybill, "331234567890")
		self.assertEqual(self.doc.e_waybill_status, "Generated")
		self.assertEqual(out["ewaybill"], "331234567890")
		self.create_ewb_log.assert_called_once()

	def test_fetch_no_match_leaves_doc_untouched(self):
		api_result = {"success": True, "result": [{"docNo": "DC-9999", "ewbNo": 1}]}
		with patch.object(api_module.EWaybillAPI, "get_ewaybills_by_date", return_value=api_result):
			out = fetch_e_waybill("Delivery Challan", "DC-0001", {})
		self.assertIsNone(self.doc.ewaybill)
		self.assertIsNone(out["ewaybill"])
		self.create_ewb_log.assert_not_called()


class TestAutoCancelEWaybill(unittest.TestCase):
	def _run(self, doc, cancel_result, auto_cancel=1, created_on=None):
		# created_on=None → the log lookup hits the real (empty) DB → None →
		# within-window path. Pass an old date to exercise the >24h guard; patch
		# get_value SURGICALLY (only the log query) so frappe internals still work.
		with contextlib.ExitStack() as stack:
			stack.enter_context(patch.object(lifecycle_module, "get_ewb_settings", return_value=_settings(auto_cancel)))
			stack.enter_context(patch.object(api_module, "get_ewb_settings", return_value=_settings(auto_cancel)))
			stack.enter_context(patch.object(lifecycle_module, "update_ewb_log"))
			stack.enter_context(patch("frappe.db.exists", return_value=True))
			cancel = stack.enter_context(patch.object(api_module.EWaybillAPI, "cancel", return_value=cancel_result))
			if created_on is not None:
				real_get_value = frappe.db.get_value

				def _gv(doctype, *args, **kwargs):
					if doctype == "YRP E-Waybill Log":
						return created_on
					return real_get_value(doctype, *args, **kwargs)

				stack.enter_context(patch("frappe.db.get_value", side_effect=_gv))
			auto_cancel_ewaybill(doc)
			return cancel

	def test_past_24h_window_is_noop(self):
		doc = _FakeDoc(ewaybill="331234567890")
		cancel = self._run(doc, {"success": True}, created_on="2020-01-01 10:00:00")
		cancel.assert_not_called()
		self.assertEqual(doc.ewaybill, "331234567890")  # left intact, DC cancel proceeds

	def test_success_clears_ewaybill(self):
		doc = _FakeDoc(ewaybill="331234567890")
		self._run(doc, {"success": True, "result": {}})
		self.assertEqual(doc.ewaybill, "")
		self.assertEqual(doc.e_waybill_status, "Cancelled")

	def test_failure_blocks_document_cancel(self):
		doc = _FakeDoc(ewaybill="331234567890")
		with self.assertRaises(frappe.ValidationError):
			self._run(doc, {"success": False, "error": "GSP down"})
		# ewaybill NOT cleared because the throw rolled the cancel back
		self.assertEqual(doc.ewaybill, "331234567890")

	def test_disabled_is_noop(self):
		doc = _FakeDoc(ewaybill="331234567890")
		cancel = self._run(doc, {"success": True}, auto_cancel=0)
		cancel.assert_not_called()
		self.assertEqual(doc.ewaybill, "331234567890")

	def test_no_ewaybill_is_noop(self):
		doc = _FakeDoc(ewaybill=None)
		# no settings/api access expected
		with patch.object(lifecycle_module, "get_ewb_settings") as gs:
			auto_cancel_ewaybill(doc)
			gs.assert_not_called()


class TestEnsureGstResolved(unittest.TestCase):
	def test_resolves_and_persists_when_blank(self):
		doc = _FakeDoc()
		doc.company_gstin = None  # simulate an already-submitted doc (validate never ran)

		def fake_update(d, method=None):
			d.company_gstin = "33AAAAA0000A1Z5"
			d.party_gstin = "29BBBBB0000B1Z5"

		with patch("yrp_ewaybill_api.gst.source_resolver.update_gst_details", side_effect=fake_update):
			_ensure_gst_resolved(doc)
		self.assertEqual(doc.company_gstin, "33AAAAA0000A1Z5")
		self.assertEqual(doc.party_gstin, "29BBBBB0000B1Z5")

	def test_refreshes_company_gstin_even_when_already_set(self):
		# company GSTIN is authoritative from Settings, so a stale cached value
		# on an already-submitted doc must be OVERWRITTEN, not kept.
		doc = _FakeDoc()
		doc.company_gstin = "08STALE0000A1Z5"  # e.g. an old from-location GSTIN

		def fake_update(d, method=None):
			d.company_gstin = "33AAECE7034R1ZA"  # the Settings company GSTIN

		with patch("yrp_ewaybill_api.gst.source_resolver.update_gst_details", side_effect=fake_update) as u:
			_ensure_gst_resolved(doc)
			u.assert_called_once()
		self.assertEqual(doc.company_gstin, "33AAECE7034R1ZA")


class TestGetCompanyGstin(unittest.TestCase):
	def _settings_stub(self, company_gstin, cred_gstins):
		from yrp_ewaybill_api.yrp_e_waybill_integration.doctype.yrp_e_waybill_settings.yrp_e_waybill_settings import (
			YRPEWaybillSettings,
		)

		s = YRPEWaybillSettings.__new__(YRPEWaybillSettings)
		s.company_gstin = company_gstin
		s.credentials = [frappe._dict(gstin=g) for g in cred_gstins]
		return s

	def test_explicit_company_gstin_wins(self):
		s = self._settings_stub("33AAECE7034R1ZA", ["09OTHER0000A1Z5"])
		self.assertEqual(s.get_company_gstin(), "33AAECE7034R1ZA")

	def test_single_credential_used_when_no_explicit(self):
		s = self._settings_stub(None, ["33AAECE7034R1ZA"])
		self.assertEqual(s.get_company_gstin(), "33AAECE7034R1ZA")

	def test_multiple_credentials_no_explicit_returns_none(self):
		s = self._settings_stub(None, ["33AAECE7034R1ZA", "09OTHER0000A1Z5"])
		self.assertIsNone(s.get_company_gstin())


if __name__ == "__main__":
	unittest.main()
