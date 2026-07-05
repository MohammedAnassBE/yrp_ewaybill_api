// YRP E-Waybill client actions.
// Self-contained port of india_compliance/gst_india/client_scripts/e_waybill_actions.js
// (dialog shapes replicated; NO dependency on india_compliance JS globals).
//
// Usage (from a per-doctype file, e.g. delivery_challan_ewaybill.js):
//     yrp_ewaybill.setup_actions("Delivery Challan");

window.yrp_ewaybill = window.yrp_ewaybill || {};

yrp_ewaybill.setup_actions = function (doctype) {
	frappe.ui.form.on(doctype, {
		refresh(frm) {
			// Only submitted documents can carry an e-Waybill.
			if (frm.doc.docstatus !== 1) return;

			if (!frm.doc.ewaybill) {
				frm.add_custom_button(
					__("Generate e-Waybill"),
					() => yrp_ewaybill.show_generate_dialog(frm),
					__("e-Waybill"),
				);
				frm.add_custom_button(
					__("Fetch e-Waybill"),
					() => yrp_ewaybill.show_fetch_dialog(frm),
					__("e-Waybill"),
				);
				return;
			}

			// e-Waybill already generated: allow Part-B / cancel actions.
			frm.add_custom_button(
				__("Update Vehicle Info"),
				() => yrp_ewaybill.show_update_vehicle_dialog(frm),
				__("e-Waybill"),
			);

			frm.add_custom_button(
				__("Cancel e-Waybill"),
				() => yrp_ewaybill.show_cancel_dialog(frm),
				__("e-Waybill"),
			);

			frm.add_custom_button(
				__("Print e-Waybill"),
				() => yrp_ewaybill.print_ewaybill(frm),
				__("e-Waybill"),
			);
		},
	});
};

// Refresh the full e-Waybill detail on the log, then open its print view.
yrp_ewaybill.print_ewaybill = function (frm) {
	frappe.call({
		method: "yrp_ewaybill_api.ewaybill.actions.fetch_ewaybill_data",
		args: { doctype: frm.doctype, docname: frm.doc.name },
		freeze: true,
		freeze_message: __("Fetching e-Waybill for print…"),
		callback() {
			const url = frappe.urllib.get_full_url(
				"/printview?doctype=" +
					encodeURIComponent("YRP E-Waybill Log") +
					"&name=" +
					encodeURIComponent(frm.doc.ewaybill) +
					"&format=" +
					encodeURIComponent("YRP e-Waybill") +
					"&no_letterhead=1&trigger_print=1",
			);
			window.open(url);
		},
	});
};

/******************************************************************************
 * Generate e-Waybill
 *****************************************************************************/

yrp_ewaybill.show_generate_dialog = function (frm) {
	const doc = frm.doc;

	// Fields are built inline so the onchange closures below can capture the
	// dialog binding `d` (mirrors india_compliance's get_generate_e_waybill_dialog).
	const fields = [
		{
			label: __("Part A"),
			fieldname: "section_part_a",
			fieldtype: "Section Break",
		},
		{
			label: __("Transporter"),
			fieldname: "transporter",
			fieldtype: "Link",
			options: "Supplier",
			default: doc.transporter,
			// Only suppliers flagged is_transporter appear in the picker.
			get_query: () => ({ filters: { is_transporter: 1 } }),
			onchange: () => {
				const transporter = d.get_value("transporter");
				if (!transporter) return;
				// Auto-fill the GST Transporter ID from the chosen transporter.
				frappe.db.get_value("Supplier", transporter, "gst_transporter_id").then((r) => {
					const gstin = r && r.message && r.message.gst_transporter_id;
					if (gstin) d.set_value("gst_transporter_id", gstin);
				});
			},
		},
		{
			label: __("Distance (in km)"),
			fieldname: "distance",
			fieldtype: "Int",
			default: doc.distance || 0,
			description: __(
				"Set as zero to let the e-Waybill portal auto-calculate the distance (if available).",
			),
		},
		{
			fieldtype: "Column Break",
		},
		{
			label: __("GST Transporter ID"),
			fieldname: "gst_transporter_id",
			fieldtype: "Data",
			default: doc.gst_transporter_id,
		},
		{
			label: __("Part B"),
			fieldname: "section_part_b",
			fieldtype: "Section Break",
		},
		{
			label: __("Vehicle No"),
			fieldname: "vehicle_no",
			fieldtype: "Data",
			default: doc.vehicle_no,
			onchange: () => yrp_ewaybill.update_generate_label(d),
		},
		{
			label: __("Transport Receipt No"),
			fieldname: "lr_no",
			fieldtype: "Data",
			default: doc.lr_no,
			onchange: () => yrp_ewaybill.update_generate_label(d),
		},
		{
			label: __("Transport Receipt Date"),
			fieldname: "lr_date",
			fieldtype: "Date",
			default: doc.lr_date || "Today",
			mandatory_depends_on: "eval:doc.lr_no",
		},
		{
			fieldtype: "Column Break",
		},
		{
			label: __("Mode Of Transport"),
			fieldname: "mode_of_transport",
			fieldtype: "Select",
			options: "\nRoad\nAir\nRail\nShip",
			default: doc.mode_of_transport || "Road",
			onchange: () => {
				yrp_ewaybill.update_vehicle_type(d);
				yrp_ewaybill.update_generate_label(d);
			},
		},
		{
			label: __("GST Vehicle Type"),
			fieldname: "gst_vehicle_type",
			fieldtype: "Select",
			options: "Regular\nOver Dimensional Cargo (ODC)",
			depends_on: 'eval:["Road", "Ship"].includes(doc.mode_of_transport)',
			read_only_depends_on: "eval: doc.mode_of_transport == 'Ship'",
			default: doc.gst_vehicle_type || "Regular",
		},
	];

	// HACK (mirrors india_compliance): prevent double change events on inputs.
	frappe.ui.form.ControlData.trigger_change_on_input_event = false;

	const d = new frappe.ui.Dialog({
		title: __("Generate e-Waybill"),
		fields: fields,
		primary_action_label: yrp_ewaybill.get_generate_label(doc),
		primary_action(values) {
			d.hide();
			frappe.call({
				method: "yrp_ewaybill_api.ewaybill.actions.generate_e_waybill",
				args: {
					doctype: frm.doctype,
					docname: frm.doc.name,
					values: values,
				},
				callback: () => frm.refresh(),
			});
		},
	});

	frappe.ui.form.ControlData.trigger_change_on_input_event = true;

	d.show();
	// Ensure the initial label / gst_transporter_id-reqd state is consistent.
	yrp_ewaybill.update_generate_label(d);
};

// Primary-action label: "Generate" when Part-B transport details are present,
// otherwise "Generate (Part A)" (a Part-A-only e-Waybill, which needs a
// transporter / GST transporter ID).
yrp_ewaybill.get_generate_label = function (values) {
	return yrp_ewaybill.transport_details_available(values)
		? __("Generate")
		: __("Generate (Part A)");
};

// Part-B transport details are "available" when a vehicle (Road) or transport
// receipt (Air/Rail/Ship) identifies the conveyance.
yrp_ewaybill.transport_details_available = function (doc) {
	if (!doc) return false;
	return (
		(doc.mode_of_transport == "Road" && doc.vehicle_no) ||
		(["Air", "Rail"].includes(doc.mode_of_transport) && doc.lr_no) ||
		(doc.mode_of_transport == "Ship" && doc.lr_no && doc.vehicle_no)
	);
};

yrp_ewaybill.update_generate_label = function (dialog) {
	const values = dialog.get_values(true);
	const label = yrp_ewaybill.get_generate_label(values);

	// Part A only => GST Transporter ID (or transporter) is required.
	const is_part_a = label.includes("Part A");
	dialog.set_df_property("gst_transporter_id", "reqd", is_part_a ? 1 : 0);

	const btn = dialog.get_primary_btn();
	if (btn) btn.removeClass("hide").html(label);
};

yrp_ewaybill.update_vehicle_type = function (dialog) {
	dialog.set_value("gst_vehicle_type", yrp_ewaybill.get_vehicle_type(dialog.get_values(true)));
};

yrp_ewaybill.get_vehicle_type = function (doc) {
	if (doc.mode_of_transport == "Road") return "Regular";
	if (doc.mode_of_transport == "Ship") return "Over Dimensional Cargo (ODC)";
	return "";
};

/******************************************************************************
 * Update Vehicle Info (Part B on an already-generated e-Waybill)
 *****************************************************************************/

yrp_ewaybill.show_update_vehicle_dialog = function (frm) {
	const doc = frm.doc;

	const d = new frappe.ui.Dialog({
		title: __("Update Vehicle Information"),
		fields: [
			{
				label: __("e-Waybill"),
				fieldname: "ewaybill",
				fieldtype: "Data",
				read_only: 1,
				default: doc.ewaybill,
			},
			{
				label: __("Vehicle No"),
				fieldname: "vehicle_no",
				fieldtype: "Data",
				default: doc.vehicle_no,
				mandatory_depends_on:
					"eval: ['Road', 'Ship'].includes(doc.mode_of_transport)",
			},
			{
				label: __("Transport Receipt No"),
				fieldname: "lr_no",
				fieldtype: "Data",
				default: doc.lr_no,
				mandatory_depends_on:
					"eval: ['Rail', 'Air', 'Ship'].includes(doc.mode_of_transport)",
			},
			{
				fieldtype: "Column Break",
			},
			{
				label: __("Mode Of Transport"),
				fieldname: "mode_of_transport",
				fieldtype: "Select",
				options: "\nRoad\nAir\nRail\nShip",
				default: doc.mode_of_transport,
				onchange: () => yrp_ewaybill.update_vehicle_type(d),
			},
			{
				label: __("GST Vehicle Type"),
				fieldname: "gst_vehicle_type",
				fieldtype: "Select",
				options: "Regular\nOver Dimensional Cargo (ODC)",
				depends_on: 'eval:["Road", "Ship"].includes(doc.mode_of_transport)',
				read_only_depends_on: "eval: doc.mode_of_transport == 'Ship'",
				default: doc.gst_vehicle_type,
			},
			{
				label: __("Transport Receipt Date"),
				fieldname: "lr_date",
				fieldtype: "Date",
				default: doc.lr_date,
				mandatory_depends_on: "eval:doc.lr_no",
			},
			{
				fieldtype: "Section Break",
			},
			{
				label: __("Reason"),
				fieldname: "reason",
				fieldtype: "Select",
				options: [
					"Due to Break Down",
					"Due to Trans Shipment",
					"First Time",
					"Others",
				].join("\n"),
				reqd: 1,
			},
			{
				fieldtype: "Column Break",
			},
			{
				label: __("Remark"),
				fieldname: "remark",
				fieldtype: "Data",
				mandatory_depends_on: "eval: doc.reason == 'Others'",
			},
		],
		primary_action_label: __("Update"),
		primary_action(values) {
			d.hide();
			frappe.call({
				method: "yrp_ewaybill_api.ewaybill.actions.update_vehicle_info",
				args: {
					doctype: frm.doctype,
					docname: frm.doc.name,
					values: values,
				},
				callback: () => frm.refresh(),
			});
		},
	});

	d.show();
};

/******************************************************************************
 * Cancel e-Waybill
 *****************************************************************************/

yrp_ewaybill.show_cancel_dialog = function (frm) {
	const d = new frappe.ui.Dialog({
		title: __("Cancel e-Waybill"),
		fields: [
			{
				label: __("e-Waybill"),
				fieldname: "ewaybill",
				fieldtype: "Data",
				read_only: 1,
				default: frm.doc.ewaybill,
			},
			{
				label: __("Reason"),
				fieldname: "reason",
				fieldtype: "Select",
				reqd: 1,
				default: "Data Entry Mistake",
				options: [
					"Duplicate",
					"Order Cancelled",
					"Data Entry Mistake",
					"Others",
				].join("\n"),
			},
			{
				label: __("Remark"),
				fieldname: "remark",
				fieldtype: "Data",
				mandatory_depends_on: "eval: doc.reason == 'Others'",
			},
		],
		primary_action_label: __("Cancel e-Waybill"),
		primary_action(values) {
			d.hide();
			frappe.call({
				method: "yrp_ewaybill_api.ewaybill.actions.cancel_e_waybill",
				args: {
					doctype: frm.doctype,
					docname: frm.doc.name,
					values: values,
				},
				callback: () => frm.refresh(),
			});
		},
	});

	d.show();
};

/******************************************************************************
 * Fetch existing e-Waybill (recover one already generated on the portal)
 *****************************************************************************/

yrp_ewaybill.show_fetch_dialog = function (frm) {
	const d = new frappe.ui.Dialog({
		title: __("Fetch e-Waybill"),
		fields: [
			{
				label: __("e-Waybill Date"),
				fieldname: "e_waybill_date",
				fieldtype: "Date",
				default: frm.doc.posting_date || "Today",
				reqd: 1,
				description: __("The date the e-Waybill was generated on the portal."),
			},
		],
		primary_action_label: __("Fetch"),
		primary_action(values) {
			d.hide();
			frappe.call({
				method: "yrp_ewaybill_api.ewaybill.actions.fetch_e_waybill",
				args: {
					doctype: frm.doctype,
					docname: frm.doc.name,
					values: { e_waybill_date: values.e_waybill_date },
				},
				callback: () => frm.refresh(),
			});
		},
	});

	d.show();
};
