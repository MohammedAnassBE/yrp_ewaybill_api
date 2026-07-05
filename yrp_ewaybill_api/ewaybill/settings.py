# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

from yrp_ewaybill_api.yrp_e_waybill_integration.doctype.yrp_e_waybill_settings.yrp_e_waybill_settings import (
	get_ewb_settings,
)

__all__ = ["get_ewb_settings", "get_credential"]


def get_credential(gstin):
	"""Return {username, password} for a company GSTIN. Raises if missing."""
	return get_ewb_settings().get_credential(gstin)
