# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

from yrp_ewaybill_api.gst.constants import STATE_NUMBERS


def get_state(code):
	return STATE_NUMBERS.get(code)


def state_code_from_gstin(gstin):
	gstin = (gstin or "").strip()
	return gstin[:2] if len(gstin) >= 2 else None


def get_place_of_supply(*, party_gstin, company_gstin, party_state_code=None,
		gst_category="Registered Regular"):
	if gst_category == "Overseas":
		return "96-Other Countries"
	code = state_code_from_gstin(party_gstin) or (party_state_code or "").strip() \
		or state_code_from_gstin(company_gstin)
	return f"{code}-{get_state(code)}" if code else ""


def is_inter_state(company_gstin, place_of_supply, gst_category):
	if gst_category in ("SEZ", "Overseas"):
		return True
	pos_code = (place_of_supply or "")[:2]
	return pos_code != (state_code_from_gstin(company_gstin) or "")
