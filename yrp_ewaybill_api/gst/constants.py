# Copyright (c) 2026, Mohammed Anas and contributors
# For license information, please see license.txt

# GST state code -> state name.
#
# Ported from india_compliance/gst_india/constants/__init__.py, where the same
# data is stored as ``{state name: code}``; here it is inverted to
# ``{code: state name}`` so lookups are by the 2-digit code that prefixes a
# GSTIN. ``"96": "Other Countries"`` is included for overseas supplies.
STATE_NUMBERS = {
	"01": "Jammu and Kashmir",
	"02": "Himachal Pradesh",
	"03": "Punjab",
	"04": "Chandigarh",
	"05": "Uttarakhand",
	"06": "Haryana",
	"07": "Delhi",
	"08": "Rajasthan",
	"09": "Uttar Pradesh",
	"10": "Bihar",
	"11": "Sikkim",
	"12": "Arunachal Pradesh",
	"13": "Nagaland",
	"14": "Manipur",
	"15": "Mizoram",
	"16": "Tripura",
	"17": "Meghalaya",
	"18": "Assam",
	"19": "West Bengal",
	"20": "Jharkhand",
	"21": "Odisha",
	"22": "Chhattisgarh",
	"23": "Madhya Pradesh",
	"24": "Gujarat",
	"26": "Dadra and Nagar Haveli and Daman and Diu",
	"27": "Maharashtra",
	"29": "Karnataka",
	"30": "Goa",
	"31": "Lakshadweep Islands",
	"32": "Kerala",
	"33": "Tamil Nadu",
	"34": "Puducherry",
	"35": "Andaman and Nicobar Islands",
	"36": "Telangana",
	"37": "Andhra Pradesh",
	"38": "Ladakh",
	"96": "Other Countries",
	"97": "Other Territory",
}

GST_TAX_TYPES = ("cgst", "sgst", "igst", "cess", "cess_non_advol")
