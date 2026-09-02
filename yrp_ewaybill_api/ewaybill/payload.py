# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

"""NIC e-Way Bill payload builders for a computed Delivery Challan.

Ported (self-contained, no runtime import of erpnext / india_compliance) from
`india_compliance/gst_india/utils/transaction_data.py` +
`.../utils/e_waybill.py:1813-1906`. Reads exactly the fields that the GST
compute layer writes onto the doc (per-line `taxable_value` + `*_rate`/`*_amount`,
`gst_hsn_code`, and the doc-level `company_gstin`/`party_gstin`/`total_*`).
"""

import frappe
from frappe import _
from frappe.utils import flt, format_date

from yrp_ewaybill_api.yrp_e_waybill_integration.doctype.yrp_e_waybill_settings.yrp_e_waybill_settings import (
	get_ewb_settings,
)

# NIC document type for a Delivery Challan.
DOC_TYPE = "CHL"

# Sub-supply type when the dialog does not pin one. 8 = "Others" (safe generic
# for a stock-movement delivery challan; see india_compliance SUB_SUPPLY_TYPES).
DEFAULT_SUB_SUPPLY_TYPE = 8

# NIC master codes (ported from india_compliance constants/e_waybill.py).
TRANSPORT_MODES = {"Road": 1, "Rail": 2, "Air": 3, "Ship": 4, "In Transit": 5}
VEHICLE_TYPES = {"Regular": "R", "Over Dimensional Cargo (ODC)": "O"}

# ERPNext UOM -> NIC UQC (Unit Quantity Code). Unknowns fall back to "OTH".
# Ported subset of india_compliance's UOM_MAP (constants/e_waybill.py).
UOM_TO_UQC = {
	"Bag": "BAG", "Bags": "BAG", "Bale": "BAL", "Bottle": "BTL", "Box": "BOX",
	"Bundle": "BDL", "Bundles": "BDL", "Can": "CAN", "Carton": "CTN", "Dozen": "DOZ",
	"Gram": "GMS", "Grams": "GMS", "Kg": "KGS", "Kgs": "KGS", "Kilogram": "KGS",
	"Litre": "LTR", "Meter": "MTR", "Metre": "MTR", "Meters": "MTR", "Nos": "NOS",
	"No": "NOS", "Number": "NOS", "Pack": "PAC", "Packet": "PAC", "Pair": "PRS",
	"Piece": "PCS", "Pieces": "PCS", "Pcs": "PCS", "Roll": "ROL", "Rolls": "ROL",
	"Set": "SET", "Sets": "SET", "Sq Meter": "SQM", "Square Meter": "SQM",
	"Ton": "TON", "Tonne": "TON", "Unit": "UNT", "Units": "UNT",
}


def _gst_uom(uom):
	if not uom:
		return "OTH"
	return UOM_TO_UQC.get(uom) or UOM_TO_UQC.get(str(uom).strip().title()) or "OTH"


def build_generate_payload(doc, values):
	"""Build the GENEWAYBILL request dict from a computed doc + transport `values`.

	`values` carries the dialog inputs: transporter_id, mode_of_transport,
	vehicle_no, gst_vehicle_type, lr_no, lr_date, distance.

	Part A vs A+B: `vehicleNo`/`transMode`/`vehicleType` are included only when a
	vehicle number is supplied; otherwise a Part-A bill is built and a
	transporter id is mandatory.
	"""
	values = values or {}

	addresses = resolve_addresses(doc)
	from_addr = addresses.get("from") or {}
	to_addr = addresses.get("to") or {}

	total_taxable = flt(doc.get("total_taxable_value"), 2)
	total_cgst = flt(doc.get("total_cgst_amount"), 2)
	total_sgst = flt(doc.get("total_sgst_amount"), 2)
	total_igst = flt(doc.get("total_igst_amount"), 2)
	total_cess = flt(doc.get("total_cess_amount"), 2)
	tot_inv_value = flt(total_taxable + total_cgst + total_sgst + total_igst + total_cess, 2)

	sub_supply_type = values.get("sub_supply_type") or DEFAULT_SUB_SUPPLY_TYPE
	# NIC requires a description when subSupplyType is 8 (Others).
	sub_supply_desc = values.get("sub_supply_desc") or ("Others" if str(sub_supply_type) == "8" else "")

	data = {
		"userGstin": doc.get("company_gstin"),
		"supplyType": _get_supply_type(doc),
		"subSupplyType": sub_supply_type,
		"subSupplyDesc": sub_supply_desc,
		"docType": DOC_TYPE,
		"docNo": doc.get("name"),
		"docDate": _format_date(doc.get("posting_date")),
		"transactionType": values.get("transaction_type") or 1,
		"fromGstin": doc.get("company_gstin"),
		"fromTrdName": from_addr.get("trade_name"),
		"fromAddr1": from_addr.get("addr1"),
		"fromPlace": from_addr.get("city"),
		"fromPincode": from_addr.get("pincode"),
		"fromStateCode": from_addr.get("state_code"),
		"actFromStateCode": from_addr.get("state_code"),
		"toGstin": doc.get("party_gstin"),
		"toTrdName": to_addr.get("trade_name"),
		"toAddr1": to_addr.get("addr1"),
		"toPlace": to_addr.get("city"),
		"toPincode": to_addr.get("pincode"),
		"toStateCode": to_addr.get("state_code"),
		"actToStateCode": to_addr.get("state_code"),
		"totalValue": total_taxable,
		"cgstValue": total_cgst,
		"sgstValue": total_sgst,
		"igstValue": total_igst,
		"cessValue": total_cess,
		"totInvValue": tot_inv_value,
		# Both dialogs send `gst_transporter_id`; older callers may send
		# `transporter_id` — accept either (2026-07-10 fix: the mismatch made
		# Part-A-only generation throw even with the ID filled in).
		"transporterId": values.get("gst_transporter_id") or values.get("transporter_id") or "",
		"transDistance": values.get("distance") or 0,
		"transDocNo": values.get("lr_no") or "",
		"transDocDate": _format_date(values.get("lr_date")) if values.get("lr_date") else "",
		"itemList": _build_item_list(doc),
	}

	vehicle_no = (values.get("vehicle_no") or "").strip()
	if vehicle_no:
		# Part A + B
		data["vehicleNo"] = vehicle_no.upper()
		data["transMode"] = TRANSPORT_MODES.get(values.get("mode_of_transport")) or 1
		data["vehicleType"] = VEHICLE_TYPES.get(values.get("gst_vehicle_type")) or "R"
	elif not (values.get("gst_transporter_id") or values.get("transporter_id")):
		# Part A only requires a transporter id.
		frappe.throw(
			_(
				"Transporter ID is required to generate a Part-A e-Way Bill"
				" (no vehicle number provided)."
			),
			title=_("Invalid Transporter Details"),
		)

	if get_ewb_settings().sandbox_mode:
		_apply_sandbox_identity(data)

	return data


def _apply_sandbox_identity(data):
	"""The GSP sandbox authenticates as a fixed test GSTIN and requires the
	payload's from-party to match the authenticated user. Substitute a
	self-consistent state-05 test identity: from = the test GSTIN, to =
	unregistered (URP), both intra-state so the already-computed CGST/SGST stays
	valid. Sandbox only — production sends the real parties/GSTINs untouched."""
	from yrp_ewaybill_api.ewaybill.api import SANDBOX_GSTIN

	data["userGstin"] = SANDBOX_GSTIN
	data["fromGstin"] = SANDBOX_GSTIN
	data["fromTrdName"] = "Sandbox Dispatch"
	data["fromAddr1"] = "Test Dispatch Address"
	data["fromPlace"] = "Dehradun"
	data["fromPincode"] = 248001
	data["fromStateCode"] = "05"
	data["actFromStateCode"] = "05"
	data["toGstin"] = "URP"
	data["toTrdName"] = "Sandbox Recipient"
	data["toAddr1"] = "Test Ship Address"
	data["toPlace"] = "Dehradun"
	data["toPincode"] = 248001
	data["toStateCode"] = "05"
	data["actToStateCode"] = "05"
	# NIC can't PIN-to-PIN compute for the same test pincode; supply a distance.
	if not data.get("transDistance"):
		data["transDistance"] = 100


def build_cancel_payload(ewb_no, reason_code, remark):
	"""CANEWB request dict. `reason_code` is the already-mapped NIC code."""
	return {
		"ewbNo": ewb_no,
		"cancelRsnCode": reason_code,
		"cancelRmrk": remark or "",
	}


def build_vehicle_payload(ewb_no, values):
	"""VEHEWB (Part-B / update-vehicle) request dict from transport `values`."""
	values = values or {}

	payload = {
		"ewbNo": ewb_no,
		"vehicleNo": (values.get("vehicle_no") or "").strip().upper(),
		"fromPlace": values.get("from_place") or values.get("place_of_change") or "",
		"reasonCode": values.get("reason_code") or "1",
		"reasonRem": values.get("remark") or "",
		"transDocNo": values.get("lr_no") or "",
		"transDocDate": _format_date(values.get("lr_date")) if values.get("lr_date") else "",
		"transMode": TRANSPORT_MODES.get(values.get("mode_of_transport")) or "",
		"vehicleType": VEHICLE_TYPES.get(values.get("gst_vehicle_type")) or "R",
	}

	from_state = values.get("from_state_code") or values.get("from_state")
	if from_state:
		try:
			payload["fromState"] = int(str(from_state)[:2])
		except (TypeError, ValueError):
			payload["fromState"] = from_state

	return payload


def resolve_addresses(doc):
	"""Resolve dispatch (from = company) + destination (to = recipient) party
	details, keyed by GSTIN so the trade name / address / state code all belong
	to that GSTIN's own Supplier record. The state code is derived from the GSTIN
	itself (authoritative), so it always matches. Never raises on missing data.
	"""
	return {
		"from": _resolve_side_by_gstin(doc.get("company_gstin")),
		"to": _resolve_side_by_gstin(doc.get("party_gstin")),
	}


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------


def _build_item_list(doc):
	item_list = []
	for idx, item in enumerate(doc.get("items") or [], start=1):
		item_list.append(
			{
				"itemNo": item.get("idx") or idx,
				"productDesc": item.get("item_name") or "",
				"hsnCode": item.get("gst_hsn_code"),
				"quantity": flt(item.get("qty"), 3),
				"qtyUnit": _gst_uom(item.get("uom")),
				"taxableAmount": flt(item.get("taxable_value"), 2),
				"cgstRate": flt(item.get("cgst_rate"), 3),
				"sgstRate": flt(item.get("sgst_rate"), 3),
				"igstRate": flt(item.get("igst_rate"), 3),
				"cessRate": flt(item.get("cess_rate"), 3),
			}
		)
	return item_list


def _get_supply_type(doc):
	"""NIC supplyType code: "O" (Outward) / "I" (Inward), mapped from the
	enabled-doctype row's `supply_direction` ("Outward"/"Inward"); default "O"."""
	try:
		row = get_ewb_settings().get_enabled_config(doc.get("doctype"))
	except Exception:
		row = None
	direction = (row.get("supply_direction") if row else "") or "Outward"
	return "I" if direction == "Inward" else "O"


def _format_date(value):
	if not value:
		return ""
	return format_date(value, "dd/mm/yyyy")


def _resolve_side_by_gstin(gstin):
	"""Trade name + address for a party, found via the Supplier whose `gstin`
	matches. State code is derived from the GSTIN (authoritative — always matches
	the GSTIN)."""
	side = {
		"gstin": gstin,
		"trade_name": None,
		"addr1": None,
		"city": None,
		"pincode": None,
		"state_code": _state_code_from_gstin(gstin),
	}
	if not gstin:
		return side

	supplier = frappe.db.get_value("Supplier", {"gstin": gstin}, "name")
	if not supplier:
		return side

	side["trade_name"] = frappe.db.get_value("Supplier", supplier, "supplier_name")

	address_name = _get_primary_address(supplier)
	if not address_name:
		return side

	addr = frappe.db.get_value(
		"Address", address_name, ["address_line1", "city", "pincode", "address_title"], as_dict=True
	) or frappe._dict()
	side["addr1"] = addr.get("address_line1")
	side["city"] = addr.get("city")
	# NIC wants a numeric pincode; Address.pincode is a Data (string) field.
	side["pincode"] = _to_pincode(addr.get("pincode"))
	if not side["trade_name"]:
		side["trade_name"] = addr.get("address_title")

	return side


def _get_primary_address(supplier):
	"""Primary (else any non-disabled) Address linked to the Supplier."""
	base_filters = [
		["Dynamic Link", "link_doctype", "=", "Supplier"],
		["Dynamic Link", "link_name", "=", supplier],
		["Dynamic Link", "parenttype", "=", "Address"],
		["Address", "disabled", "=", 0],
	]

	primary = frappe.get_all(
		"Address",
		filters=base_filters + [["Address", "is_primary_address", "=", 1]],
		pluck="name",
		limit=1,
	)
	if primary:
		return primary[0]

	fallback = frappe.get_all("Address", filters=base_filters, pluck="name", limit=1)
	return fallback[0] if fallback else None


def _state_code_from_gstin(gstin):
	gstin = (gstin or "").strip()
	return gstin[:2] if len(gstin) >= 2 else None


def _to_pincode(value):
	"""Coerce an Address pincode (Data/string) to the int NIC expects."""
	if not value:
		return None
	try:
		return int(str(value).strip())
	except (TypeError, ValueError):
		return None
