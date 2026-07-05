# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

"""Document-lifecycle hooks that keep an e-Waybill in sync with its source doc.

`auto_cancel_ewaybill` is wired to the source doctype's `on_cancel` (via
hooks.py `doc_events`): cancelling a Delivery Challan that carries a live
e-Waybill also cancels the e-Waybill on the NIC portal. If that cancel fails it
throws — blocking the document cancel — so the two never drift out of sync.
Gated by `YRP E-Waybill Settings.auto_cancel_on_document_cancel`.
"""

import frappe
from frappe import _
from frappe.utils import add_days, get_datetime, now_datetime

from yrp_ewaybill_api.ewaybill.api import EWaybillAPI
from yrp_ewaybill_api.ewaybill.log import update_ewb_log
from yrp_ewaybill_api.ewaybill.payload import build_cancel_payload
from yrp_ewaybill_api.yrp_e_waybill_integration.doctype.yrp_e_waybill_settings.yrp_e_waybill_settings import (
	get_ewb_settings,
)

# NIC cancel reason 2 = "Order Cancelled" — the natural reason for a doc cancel.
DOCUMENT_CANCEL_REASON_CODE = "2"


def auto_cancel_ewaybill(doc, method=None):
	ewb_number = doc.get("ewaybill")
	if not ewb_number:
		return

	settings = get_ewb_settings()
	if not settings.auto_cancel_on_document_cancel:
		return

	# NIC only allows cancellation within 24h of generation. Past that window,
	# skip auto-cancel and let the document cancel proceed (leaving the stale
	# e-Waybill) — otherwise a >24h-old DC could never be cancelled again.
	# Mirrors india_compliance auto_cancel_e_waybill.
	created_on = frappe.db.get_value("YRP E-Waybill Log", str(ewb_number), "created_on")
	if created_on and add_days(get_datetime(created_on), 1) < now_datetime():
		return

	data = build_cancel_payload(ewb_number, DOCUMENT_CANCEL_REASON_CODE, _("Document cancelled"))
	result = EWaybillAPI(doc.get("company_gstin")).cancel(data)

	if not result.get("success"):
		# Block the document cancel so doc + e-Waybill stay consistent.
		frappe.throw(
			_("Could not auto-cancel e-Waybill {0}: {1}. Cancel the e-Waybill first, then cancel this document.").format(
				frappe.bold(ewb_number), result.get("error")
			),
			title=_("e-Waybill Still Active"),
		)

	doc.db_set({"ewaybill": "", "e_waybill_status": "Cancelled"})
	if frappe.db.exists("YRP E-Waybill Log", str(ewb_number)):
		update_ewb_log(
			str(ewb_number), is_cancelled=1, cancelled_on=now_datetime(), status="Cancelled"
		)
