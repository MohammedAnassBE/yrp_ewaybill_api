# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

"""Custom-field definitions for the e-Waybill integration.

Single source of truth shared by the field-sync code (`ewaybill.field_sync`)
and the fixture export. All fields are created with
`module = "YRP E-Waybill Integration"` so they can be filtered/exported as a set.

`EWAYBILL_GST_CUSTOM_FIELDS` — the GST tax-breakup fields on Delivery Challan
(+ item). `insert_after` anchors point at real fieldnames on the base yrp
doctypes (verified against
`apps/yrp/yrp/yrp/doctype/delivery_challan/delivery_challan.json` and
`.../delivery_challan_item.json`); custom fields later in the chain anchor on
the fieldname of the custom field created just before them.

`EWAYBILL_TRANSPORT_FIELDS` — the transport + result fields, added by the
settings-driven sync to every enabled DocType (not tied to one doctype, so they
are chained to each other rather than to a base-doctype anchor).
"""

MODULE = "YRP E-Waybill Integration"


EWAYBILL_GST_CUSTOM_FIELDS = {
	"Delivery Challan": [
		{
			"fieldname": "company_gstin",
			"label": "Company GSTIN",
			"fieldtype": "Data",
			"insert_after": "supplier",
			"module": MODULE,
		},
		{
			"fieldname": "party_gstin",
			"label": "Party GSTIN",
			"fieldtype": "Data",
			"insert_after": "company_gstin",
			"module": MODULE,
		},
		{
			"fieldname": "place_of_supply",
			"label": "Place of Supply",
			"fieldtype": "Data",
			"insert_after": "party_gstin",
			"module": MODULE,
		},
		{
			"fieldname": "gst_category",
			"label": "GST Category",
			"fieldtype": "Select",
			"options": "Registered Regular\nUnregistered\nSEZ\nOverseas",
			"default": "Registered Regular",
			"insert_after": "place_of_supply",
			"module": MODULE,
		},
		{
			"fieldname": "total_taxable_value",
			"label": "Total Taxable Value",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "total_value",
			"module": MODULE,
		},
		{
			"fieldname": "total_cgst_amount",
			"label": "Total CGST Amount",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "total_taxable_value",
			"module": MODULE,
		},
		{
			"fieldname": "total_sgst_amount",
			"label": "Total SGST Amount",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "total_cgst_amount",
			"module": MODULE,
		},
		{
			"fieldname": "total_igst_amount",
			"label": "Total IGST Amount",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "total_sgst_amount",
			"module": MODULE,
		},
		{
			"fieldname": "total_cess_amount",
			"label": "Total Cess Amount",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "total_igst_amount",
			"module": MODULE,
		},
	],
	"Delivery Challan Item": [
		{
			"fieldname": "gst_hsn_code",
			"label": "HSN/SAC",
			"fieldtype": "Data",
			"insert_after": "amount",
			"module": MODULE,
		},
		{
			"fieldname": "gst_treatment",
			"label": "GST Treatment",
			"fieldtype": "Data",
			"insert_after": "gst_hsn_code",
			"module": MODULE,
		},
		{
			"fieldname": "taxable_value",
			"label": "Taxable Value",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "gst_treatment",
			"module": MODULE,
		},
		{
			"fieldname": "cgst_rate",
			"label": "CGST Rate",
			"fieldtype": "Float",
			"read_only": 1,
			"insert_after": "taxable_value",
			"module": MODULE,
		},
		{
			"fieldname": "cgst_amount",
			"label": "CGST Amount",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "cgst_rate",
			"module": MODULE,
		},
		{
			"fieldname": "sgst_rate",
			"label": "SGST Rate",
			"fieldtype": "Float",
			"read_only": 1,
			"insert_after": "cgst_amount",
			"module": MODULE,
		},
		{
			"fieldname": "sgst_amount",
			"label": "SGST Amount",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "sgst_rate",
			"module": MODULE,
		},
		{
			"fieldname": "igst_rate",
			"label": "IGST Rate",
			"fieldtype": "Float",
			"read_only": 1,
			"insert_after": "sgst_amount",
			"module": MODULE,
		},
		{
			"fieldname": "igst_amount",
			"label": "IGST Amount",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "igst_rate",
			"module": MODULE,
		},
		{
			"fieldname": "cess_rate",
			"label": "Cess Rate",
			"fieldtype": "Float",
			"read_only": 1,
			"insert_after": "igst_amount",
			"module": MODULE,
		},
		{
			"fieldname": "cess_amount",
			"label": "Cess Amount",
			"fieldtype": "Currency",
			"read_only": 1,
			"insert_after": "cess_rate",
			"module": MODULE,
		},
	],
}


# Transport + result fields. Applied by `ewaybill.field_sync.sync_ewaybill_fields`
# to each enabled DocType. They are chained to one another (the first field is
# appended at the end of the form) so the same list works on any enabled doctype
# without depending on a doctype-specific anchor.
EWAYBILL_TRANSPORT_FIELDS = [
	{
		"fieldname": "transporter",
		"label": "Transporter",
		"fieldtype": "Link",
		"options": "Supplier",
		"module": MODULE,
	},
	{
		"fieldname": "gst_transporter_id",
		"label": "GST Transporter ID",
		"fieldtype": "Data",
		"insert_after": "transporter",
		"module": MODULE,
	},
	{
		"fieldname": "mode_of_transport",
		"label": "Mode of Transport",
		"fieldtype": "Select",
		"options": "Road\nAir\nRail\nShip",
		"insert_after": "gst_transporter_id",
		"module": MODULE,
	},
	{
		"fieldname": "vehicle_no",
		"label": "Vehicle No",
		"fieldtype": "Data",
		"insert_after": "mode_of_transport",
		"module": MODULE,
	},
	{
		"fieldname": "gst_vehicle_type",
		"label": "GST Vehicle Type",
		"fieldtype": "Select",
		"options": "Regular\nOver Dimensional Cargo (ODC)",
		"insert_after": "vehicle_no",
		"module": MODULE,
	},
	{
		"fieldname": "lr_no",
		"label": "Transport Receipt No",
		"fieldtype": "Data",
		"insert_after": "gst_vehicle_type",
		"module": MODULE,
	},
	{
		"fieldname": "lr_date",
		"label": "Transport Receipt Date",
		"fieldtype": "Date",
		"insert_after": "lr_no",
		"module": MODULE,
	},
	{
		"fieldname": "distance",
		"label": "Distance (in km)",
		"fieldtype": "Int",
		"insert_after": "lr_date",
		"module": MODULE,
	},
	{
		"fieldname": "ewaybill",
		"label": "e-Waybill No",
		"fieldtype": "Data",
		"read_only": 1,
		"allow_on_submit": 1,
		"insert_after": "distance",
		"module": MODULE,
	},
	{
		"fieldname": "e_waybill_status",
		"label": "e-Waybill Status",
		"fieldtype": "Select",
		"options": "Pending\nPart A Generated\nGenerated\nCancelled\nNot Applicable\nFailed",
		"allow_on_submit": 1,
		"insert_after": "ewaybill",
		"module": MODULE,
	},
]


# Transporter fields on Supplier: `is_transporter` marks a supplier as a
# transporter (the e-Waybill dialog lists only these), and `gst_transporter_id`
# (shown only for transporters) auto-fills the dialog when one is picked.
SUPPLIER_EWAYBILL_FIELDS = {
	"Supplier": [
		{
			"fieldname": "is_transporter",
			"label": "Is Transporter",
			"fieldtype": "Check",
			"insert_after": "gstin",
			"module": MODULE,
		},
		{
			"fieldname": "gst_transporter_id",
			"label": "GST Transporter ID",
			"fieldtype": "Data",
			"depends_on": "eval:doc.is_transporter",
			"insert_after": "is_transporter",
			"module": MODULE,
		},
	],
}
