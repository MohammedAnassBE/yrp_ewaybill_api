# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

"""Print-format Jinja helpers for the e-Waybill (QR code, barcode, formatting).

Self-contained port of the india_compliance e-Waybill print helpers — QR via
pyqrcode, barcode via python-barcode (both already in the bench env). Registered
in hooks.py `jinja.methods` so the print format can call them."""

import base64
from io import BytesIO

import pyqrcode
from barcode import Code128
from barcode.writer import ImageWriter

from yrp_ewaybill_api.gst.constants import STATE_NUMBERS

TRANSACTION_TYPES = {
	1: "Regular",
	2: "Bill To - Ship To",
	3: "Bill From - Dispatch From",
	4: "Combination of 2 and 3",
}
SUPPLY_TYPES = {"O": "Outward", "I": "Inward"}
SUB_SUPPLY_TYPES = {
	1: "Supply", 2: "Import", 3: "Export", 4: "Job Work", 5: "For Own Use",
	6: "Job Work Returns", 7: "Sales Return", 8: "Others", 9: "SKD/CKD/Lots",
	10: "Line Sales", 11: "Recipient Not Known", 12: "Exhibition or Fairs",
}


def get_qr_code(qr_text, scale=4):
	return pyqrcode.create(qr_text).png_as_base64_str(scale=scale, quiet_zone=1)


def get_e_waybill_qr_code(ewb_no, gstin, ewaybill_date):
	qr_text = "/".join((str(ewb_no), str(gstin or ""), str(ewaybill_date or "")))
	return get_qr_code(qr_text)


def get_ewaybill_barcode(ewb_no):
	stream = BytesIO()
	Code128(str(ewb_no), writer=ImageWriter()).write(
		stream,
		{"module_width": 0.5, "module_height": 16.0, "text_distance": 6, "font_size": 12},
	)
	encoded = base64.b64encode(stream.getbuffer()).decode()
	stream.close()
	return encoded


def add_spacing(value, n):
	"""Group a string every `n` chars with a space, e.g. add_spacing('301010810473', 4)
	-> '3010 1081 0473'."""
	value = str(value or "").strip()
	return " ".join(value[i : i + n] for i in range(0, len(value), n))


def get_state_name(code):
	if code in (None, ""):
		return ""
	return STATE_NUMBERS.get(str(code).zfill(2), str(code))


def ewb_transaction_type(t):
	try:
		return TRANSACTION_TYPES.get(int(t), str(t or ""))
	except (TypeError, ValueError):
		return str(t or "")


def ewb_supply_type(s):
	return SUPPLY_TYPES.get(s, str(s or ""))


def ewb_sub_supply_type(n):
	try:
		return SUB_SUPPLY_TYPES.get(int(str(n).strip()), str(n or ""))
	except (TypeError, ValueError):
		return str(n or "")
