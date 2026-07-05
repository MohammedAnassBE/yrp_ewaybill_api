# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

"""Whitelisted e-Waybill actions: generate / cancel / update-vehicle.

These are the endpoints the Delivery Challan client script calls. They build a
NIC payload from a computed document (`ewaybill.payload`), POST it via the
self-contained GSP client (`ewaybill.api.EWaybillAPI`, which never raises) and
persist a `YRP E-Waybill Log` row for every outcome.

Failure policy (mirrors Frappe's SMS-notification path): on a GSP failure we
`msgprint(indicator="red")` and write a **Failed** log — we do NOT throw, so the
Failed log persists and the user sees the NIC error instead of a stack trace.
`YRP E-Waybill Log` autonames on `e_waybill_number`, so a failed attempt (which
has no e-Waybill number) is logged under a generated placeholder hash.
"""

import frappe
from frappe import _
from frappe.utils import now_datetime

from yrp_ewaybill_api.ewaybill.api import EWaybillAPI
from yrp_ewaybill_api.ewaybill.log import create_ewb_log, update_ewb_log
from yrp_ewaybill_api.ewaybill.payload import (
	build_cancel_payload,
	build_generate_payload,
	build_vehicle_payload,
)
from yrp_ewaybill_api.yrp_e_waybill_integration.doctype.yrp_e_waybill_settings.yrp_e_waybill_settings import (
	get_ewb_settings,
)


# NIC reason-code maps (ported from india_compliance constants/e_waybill.py) —
# the dialogs send human labels; NIC requires the numeric codes.
CANCEL_REASON_CODES = {
	"Duplicate": "1",
	"Order Cancelled": "2",
	"Data Entry Mistake": "3",
	"Others": "4",
}
UPDATE_VEHICLE_REASON_CODES = {
	"Due to Break Down": "1",
	"Due to Trans Shipment": "2",
	"First Time": "4",
	"Others": "3",
}


# --- helpers ------------------------------------------------------------


def _parse_values(values):
	"""Normalise the dialog `values` arg (JSON string or dict) into a dict."""
	if isinstance(values, str):
		values = frappe.parse_json(values)
	return values or {}


def _ensure_gst_resolved(doc):
	"""Resolve company_gstin / party_gstin (+ the GST breakup) at action time.

	The validate hook that normally fills these does NOT run on an already-
	submitted document, so a submit-time action must resolve them itself.
	Runs unconditionally (not just when blank) so the company GSTIN is always
	refreshed from Settings — correcting any stale value cached on an old doc
	(e.g. one that previously read the from-location instead of the company)."""
	from yrp_ewaybill_api.gst.source_resolver import update_gst_details

	update_gst_details(doc)
	updates = {}
	if doc.get("company_gstin"):
		updates["company_gstin"] = doc.get("company_gstin")
	if doc.get("party_gstin"):
		updates["party_gstin"] = doc.get("party_gstin")
	if updates:
		doc.db_set(updates)


def _coerce_datetime(value):
	"""Best-effort convert a NIC date string into a datetime for the log.

	NIC returns validity as day-first `dd/mm/yyyy hh:mm:ss` (e.g. 13/07/2026),
	which `frappe.utils.get_datetime` would misread as month-first. Parse with
	`dayfirst=True`. Never raises: an unparseable value logs as None rather than
	breaking an otherwise successful generation.
	"""
	if not value:
		return None
	try:
		from dateutil import parser as _dateparser

		return _dateparser.parse(str(value), dayfirst=True)
	except Exception:
		return None


def _placeholder_ewb_number():
	"""Unique key for a Failed log row (no NIC number exists yet).

	`YRP E-Waybill Log` autonames on `e_waybill_number`, so the value must be
	unique — a generated hash keeps the audit row insertable.
	"""
	return frappe.generate_hash(length=20)


# --- generate -----------------------------------------------------------


@frappe.whitelist()
def generate_e_waybill(doctype, docname, values=None):
	"""Generate a NIC e-Waybill for `docname` and log the outcome.

	Returns `{"ewaybill", "status"}`. On GSP failure: red msgprint + Failed log,
	no exception (the doc's `ewaybill` stays unset).
	"""
	frappe.has_permission(doctype, "submit", doc=docname, throw=True)
	doc = frappe.get_doc(doctype, docname)

	if doc.get("ewaybill"):
		frappe.throw(
			_("e-Waybill has already been generated for {0} {1}").format(
				_(doctype), frappe.bold(docname)
			)
		)

	_ensure_gst_resolved(doc)
	values = _parse_values(values)
	data = build_generate_payload(doc, values)

	settings = get_ewb_settings()
	result = EWaybillAPI(doc.get("company_gstin")).generate(data)

	nic = result.get("result") or {}
	ewb_number = None
	if result.get("success"):
		ewb_number = nic.get("ewayBillNo") or nic.get("EwbNo")

	if not ewb_number:
		# Failure: persist a Failed log under a placeholder key, toast, don't throw.
		error = result.get("error") or _("e-Waybill generation failed")
		create_ewb_log(
			e_waybill_number=_placeholder_ewb_number(),
			reference_doctype=doctype,
			reference_name=docname,
			created_on=now_datetime(),
			is_sandbox=settings.sandbox_mode,
			data=frappe.as_json(result),
			status="Failed",
			error=error,
		)
		frappe.msgprint(
			_("e-Waybill generation failed:<br>{0}").format(error),
			title=_("e-Waybill Failed"),
			indicator="red",
		)
		return {"ewaybill": None, "status": "Failed", "error": error}

	# Success: Part A (no validity yet) vs fully generated (validity returned).
	ewb_number = str(ewb_number)
	valid_upto = nic.get("validUpto") or nic.get("EwbValidTill")
	status = "Generated" if valid_upto else "Part A Generated"

	doc.db_set({"ewaybill": ewb_number, "e_waybill_status": status})

	create_ewb_log(
		e_waybill_number=ewb_number,
		reference_doctype=doctype,
		reference_name=docname,
		created_on=now_datetime(),
		valid_upto=_coerce_datetime(valid_upto),
		is_sandbox=settings.sandbox_mode,
		data=frappe.as_json(nic),
		status=status,
		is_cancelled=0,
	)

	# Pull the full e-Waybill detail so it can be printed (best-effort).
	_store_full_ewaybill_data(doc.get("company_gstin"), ewb_number)

	frappe.msgprint(
		_("e-Waybill generated successfully")
		if status == "Generated"
		else _("e-Waybill (Part A) generated successfully"),
		indicator="green",
		alert=True,
	)

	return {"ewaybill": ewb_number, "status": status}


# --- full data (for printing) -------------------------------------------


def _store_full_ewaybill_data(company_gstin, ewb_number):
	"""Best-effort: fetch the full e-Waybill detail and store it on the log so it
	can be printed. Never raises — a print-data fetch must not fail generation."""
	try:
		result = EWaybillAPI(company_gstin).get_ewaybill(ewb_number)
		if result.get("success") and result.get("result") and frappe.db.exists(
			"YRP E-Waybill Log", str(ewb_number)
		):
			update_ewb_log(str(ewb_number), data=frappe.as_json(result.get("result")))
			return True
	except Exception:
		frappe.log_error(frappe.get_traceback(), "e-Waybill full-data fetch failed")
	return False


@frappe.whitelist()
def fetch_ewaybill_data(doctype, docname):
	"""Refresh the full e-Waybill detail on the log (for an up-to-date print)."""
	frappe.has_permission(doctype, "read", doc=docname, throw=True)
	doc = frappe.get_doc(doctype, docname)
	ewb = doc.get("ewaybill")
	if not ewb:
		frappe.throw(_("No e-Waybill on {0} {1}").format(_(doctype), frappe.bold(docname)))
	_ensure_gst_resolved(doc)
	_store_full_ewaybill_data(doc.get("company_gstin"), ewb)
	return ewb


# --- fetch existing -----------------------------------------------------


def _find_matching_ewb(result, docname):
	"""Locate the ACTIVE e-Waybill entry whose docNo matches this document in a
	GetEwayBillsByDate response (a list, or a dict wrapping a list). Cancelled
	(status != "ACT") entries are skipped so we never link a dead number
	(mirrors india_compliance find_matching_e_waybill)."""
	if isinstance(result, dict):
		for key in ("ewayBills", "ewbList", "data", "eWayBills"):
			if isinstance(result.get(key), list):
				result = result[key]
				break
		else:
			result = [result] if result.get("docNo") else []
	if not isinstance(result, list):
		return None
	for entry in result:
		if not isinstance(entry, dict) or str(entry.get("docNo")) != str(docname):
			continue
		# Only an active e-Waybill; day-lists include cancelled ones (status CNL).
		if entry.get("status") and str(entry.get("status")).upper() != "ACT":
			continue
		return entry
	return None


@frappe.whitelist()
def fetch_e_waybill(doctype, docname, values=None):
	"""Recover an e-Waybill already generated on the portal for `docname` and
	link it (GetEwayBillsByDate, matched by docNo). Never throws on GSP errors."""
	frappe.has_permission(doctype, "submit", doc=docname, throw=True)
	doc = frappe.get_doc(doctype, docname)
	if doc.get("ewaybill"):
		frappe.throw(
			_("{0} {1} already has e-Waybill {2}").format(_(doctype), frappe.bold(docname), doc.get("ewaybill"))
		)

	_ensure_gst_resolved(doc)
	values = _parse_values(values)
	date = frappe.utils.format_date(values.get("e_waybill_date") or frappe.utils.today(), "dd/mm/yyyy")
	settings = get_ewb_settings()

	result = EWaybillAPI(doc.get("company_gstin")).get_ewaybills_by_date(date)
	if not result.get("success"):
		frappe.msgprint(
			_("Could not fetch e-Waybills:<br>{0}").format(result.get("error")),
			title=_("Fetch Failed"), indicator="red",
		)
		return {"ewaybill": None, "error": result.get("error") or _("Could not fetch e-Waybills")}

	match = _find_matching_ewb(result.get("result"), docname)
	if not match:
		frappe.msgprint(
			_("No e-Waybill found for {0} on {1}").format(frappe.bold(docname), date),
			indicator="orange", alert=True,
		)
		return {"ewaybill": None}

	raw_number = match.get("ewbNo") or match.get("ewayBillNo")
	if not raw_number:
		frappe.msgprint(
			_("Matched an e-Waybill entry for {0} but it carried no number").format(frappe.bold(docname)),
			indicator="orange", alert=True,
		)
		return {"ewaybill": None}
	ewb_number = str(raw_number)
	valid_upto = _coerce_datetime(match.get("validUpto") or match.get("EwbValidTill"))
	# A matched entry is ACTIVE (filtered above), so it is fully Generated; the
	# day-list rarely carries validUpto, so don't downgrade to Part A on its absence.
	status = "Generated"
	doc.db_set({"ewaybill": ewb_number, "e_waybill_status": status})

	if not frappe.db.exists("YRP E-Waybill Log", ewb_number):
		create_ewb_log(
			e_waybill_number=ewb_number, reference_doctype=doctype, reference_name=docname,
			created_on=now_datetime(), valid_upto=valid_upto, is_sandbox=settings.sandbox_mode,
			data=frappe.as_json(match), status=status,
		)

	frappe.msgprint(_("Fetched e-Waybill {0}").format(ewb_number), indicator="green", alert=True)
	return {"ewaybill": ewb_number, "status": status}


# --- cancel -------------------------------------------------------------


@frappe.whitelist()
def cancel_e_waybill(doctype, docname, values=None):
	"""Cancel the e-Waybill on `docname`. Same never-throw failure policy."""
	frappe.has_permission(doctype, "cancel", doc=docname, throw=True)
	doc = frappe.get_doc(doctype, docname)

	ewb_number = doc.get("ewaybill")
	if not ewb_number:
		frappe.throw(
			_("No e-Waybill found on {0} {1} to cancel").format(_(doctype), frappe.bold(docname))
		)

	_ensure_gst_resolved(doc)
	values = _parse_values(values)
	settings = get_ewb_settings()

	# The dialog sends a label ("Data Entry Mistake"); NIC needs the numeric code.
	reason_code = values.get("reason_code") or CANCEL_REASON_CODES.get(values.get("reason"))
	remark = values.get("remark")
	data = build_cancel_payload(ewb_number, reason_code, remark)

	result = EWaybillAPI(doc.get("company_gstin")).cancel(data)

	if not result.get("success"):
		error = result.get("error") or _("e-Waybill cancellation failed")
		create_ewb_log(
			e_waybill_number=_placeholder_ewb_number(),
			reference_doctype=doctype,
			reference_name=docname,
			created_on=now_datetime(),
			is_sandbox=settings.sandbox_mode,
			data=frappe.as_json(result),
			status="Failed",
			error=error,
		)
		frappe.msgprint(
			_("e-Waybill cancellation failed:<br>{0}").format(error),
			title=_("e-Waybill Failed"),
			indicator="red",
		)
		return {"ewaybill": ewb_number, "status": "Failed", "error": error}

	doc.db_set({"ewaybill": "", "e_waybill_status": "Cancelled"})

	log_updates = {
		"is_cancelled": 1,
		"cancelled_on": now_datetime(),
		"status": "Cancelled",
	}
	if frappe.db.exists("YRP E-Waybill Log", str(ewb_number)):
		update_ewb_log(str(ewb_number), **log_updates)
	else:
		create_ewb_log(
			e_waybill_number=str(ewb_number),
			reference_doctype=doctype,
			reference_name=docname,
			created_on=now_datetime(),
			is_sandbox=settings.sandbox_mode,
			data=frappe.as_json(result.get("result") or {}),
			**log_updates,
		)

	frappe.msgprint(_("e-Waybill cancelled successfully"), indicator="green", alert=True)

	return {"ewaybill": "", "status": "Cancelled"}


# --- update vehicle (Part B) -------------------------------------------


@frappe.whitelist()
def update_vehicle_info(doctype, docname, values=None):
	"""Add / update Part-B transport info on an existing e-Waybill."""
	frappe.has_permission(doctype, "submit", doc=docname, throw=True)
	doc = frappe.get_doc(doctype, docname)

	ewb_number = doc.get("ewaybill")
	if not ewb_number:
		frappe.throw(
			_("No e-Waybill found on {0} {1} to update").format(_(doctype), frappe.bold(docname))
		)

	_ensure_gst_resolved(doc)
	values = _parse_values(values)
	# The dialog sends a reason label; NIC needs the numeric update-vehicle code.
	if not values.get("reason_code"):
		values["reason_code"] = UPDATE_VEHICLE_REASON_CODES.get(values.get("reason"))
	settings = get_ewb_settings()

	data = build_vehicle_payload(ewb_number, values)
	result = EWaybillAPI(doc.get("company_gstin")).update_vehicle(data)

	if not result.get("success"):
		error = result.get("error") or _("Vehicle info update failed")
		create_ewb_log(
			e_waybill_number=_placeholder_ewb_number(),
			reference_doctype=doctype,
			reference_name=docname,
			created_on=now_datetime(),
			is_sandbox=settings.sandbox_mode,
			data=frappe.as_json(result),
			status="Failed",
			error=error,
		)
		frappe.msgprint(
			_("Vehicle info update failed:<br>{0}").format(error),
			title=_("e-Waybill Failed"),
			indicator="red",
		)
		return {"ewaybill": ewb_number, "status": "Failed", "error": error}

	# Persist the transport fields the user entered on the doc.
	transport_fields = {}
	for fieldname in ("vehicle_no", "lr_no", "lr_date", "mode_of_transport", "gst_vehicle_type"):
		if values.get(fieldname) is not None:
			transport_fields[fieldname] = values.get(fieldname)
	if transport_fields:
		doc.db_set(transport_fields)

	# Adding Part B (vehicle) makes a Part-A-only bill fully valid → flip status.
	nic = result.get("result") or {}
	valid_upto = _coerce_datetime(nic.get("validUpto") or nic.get("EwbValidTill"))
	if valid_upto:
		if doc.get("e_waybill_status") != "Generated":
			doc.db_set("e_waybill_status", "Generated")
		if frappe.db.exists("YRP E-Waybill Log", str(ewb_number)):
			update_ewb_log(str(ewb_number), valid_upto=valid_upto, status="Generated")

	frappe.msgprint(_("Vehicle Info updated successfully"), indicator="green", alert=True)

	return {"ewaybill": ewb_number, "status": doc.get("e_waybill_status")}
