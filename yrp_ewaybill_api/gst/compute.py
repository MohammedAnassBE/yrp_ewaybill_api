from frappe.utils import flt

from yrp_ewaybill_api.gst.place_of_supply import get_place_of_supply, is_inter_state
from yrp_ewaybill_api.gst.rates import get_gst_rate

TAXABLE = ("Taxable", "Zero-Rated")


def compute_gst_details(doc):
	doc.place_of_supply = get_place_of_supply(
		party_gstin=doc.get("party_gstin"),
		company_gstin=doc.get("company_gstin"),
		party_state_code=doc.get("party_state_code"),
		gst_category=doc.get("gst_category") or "Registered Regular",
	)
	inter = is_inter_state(
		doc.get("company_gstin"),
		doc.place_of_supply,
		doc.get("gst_category") or "Registered Regular",
	)
	totals = {"taxable_value": 0, "cgst": 0, "sgst": 0, "igst": 0, "cess": 0}
	for item in doc.get("items"):
		rate_info = get_gst_rate(item.get("gst_hsn_code"))
		rate = rate_info["gst_rate"]
		cess_rate = rate_info["cess_rate"]
		treatment = rate_info["gst_treatment"]
		item.gst_treatment = treatment
		item.taxable_value = flt(item.amount, 2)
		for f in (
			"cgst_rate",
			"cgst_amount",
			"sgst_rate",
			"sgst_amount",
			"igst_rate",
			"igst_amount",
			"cess_rate",
			"cess_amount",
		):
			setattr(item, f, 0)
		base = item.taxable_value / 100
		if treatment in TAXABLE and rate:
			if inter:
				item.igst_rate = rate
				item.igst_amount = flt(rate * base, 2)
			else:
				half = rate / 2
				item.cgst_rate = item.sgst_rate = half
				item.cgst_amount = flt(half * base, 2)
				item.sgst_amount = flt(half * base, 2)
		if treatment in TAXABLE and cess_rate:
			item.cess_rate = cess_rate
			item.cess_amount = flt(cess_rate * base, 2)
		# The consignment total (NIC totalValue) covers EVERY line's value,
		# regardless of GST treatment — only the tax-AMOUNT math above is gated
		# by treatment. This keeps totalValue == sum(itemList.taxableAmount)
		# (matches india_compliance transaction_data.py; a mismatch is a NIC reject).
		totals["taxable_value"] += item.taxable_value
		for t in ("cgst", "sgst", "igst", "cess"):
			totals[t] += item.get(f"{t}_amount") or 0
	doc.total_taxable_value = flt(totals["taxable_value"], 2)
	doc.total_cgst_amount = flt(totals["cgst"], 2)
	doc.total_sgst_amount = flt(totals["sgst"], 2)
	doc.total_igst_amount = flt(totals["igst"], 2)
	doc.total_cess_amount = flt(totals["cess"], 2)
