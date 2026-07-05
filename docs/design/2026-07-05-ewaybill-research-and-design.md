# YRP E-Waybill Integration — Research & Design (2026-07-05)

Self-contained e-way bill generation for yrp's **Delivery Challan, Stock Entry, Goods Received Note**.

## Hard constraint

The app must run on `essdee_yrp.site`, which does **not** install `erpnext` or
`india_compliance`. Therefore this app **re-implements** the e-way bill engine
natively. We read `india_compliance` / `erpnext` / the F15 `ewb_api_integration`
app **only as reference** — never import from them at runtime.

## How e-way bill generation works (from india_compliance)

- **One API call** (`GENEWAYBILL`) creates the bill. Whether it's "Part A only"
  or "Part A + Part B" depends purely on what transport data is in that payload.
  - **Part A** = consignment: from/to GSTIN + trade name + addresses (line1/2,
    city, pincode, state code), the HSN `itemList` (hsn, qty, uom, taxable value,
    CGST/SGST/IGST/cess rates), invoice values, doc type/no/date, `transDistance`,
    `transporterId`. A Part-A-only bill needs a **GST Transporter ID** (no vehicle)
    and has **no validity** until Part B is added.
  - **Part B** = movement: `transMode`, `vehicleNo`, `vehicleType`,
    `transDocNo` (LR no), `transDocDate` (LR date).
- **Add Part B later** via a separate `VEHEWB` call (update vehicle info) → sets
  validity.
- **Other actions** (separate API verbs): `CANEWB` (cancel, ≤24h of creation),
  `UPDATETRANSPORTER`, `VEHEWB` (update vehicle), `EXTENDVALIDITY` (within ±8h of
  expiry).
- **Record-keeping:** a generated bill's number + validity + full JSON live in an
  **e-Waybill Log**-style doctype; the source document stores the `ewaybill`
  number + an `e_waybill_status` (Pending / Generated / Cancelled / Not
  Applicable / Failed …).

### Payload fields (Part A) the source doc must supply
Header: `userGstin` (company GSTIN), `supplyType` (I/O), `subSupplyType`,
`docType`, `docNo`, `docDate`, `transactionType`.
From/To: trade name, GSTIN, addr1/2, place (city), pincode, state code (×2 for
dispatch vs bill).
Values: `totalValue` (taxable), `cgstValue`/`sgstValue`/`igstValue`/`cessValue`,
`totInvValue`.
Items (per row): `hsnCode`, `productDesc`, `qtyUnit` (GST UOM), `quantity`,
`taxableAmount`, `cgstRate`/`sgstRate`/`igstRate`/`cessRate`.
Transport: `transMode`, `transDistance`, `transporterId`, `transDocNo`,
`transDocDate`, `vehicleNo`, `vehicleType`.

## API / auth options (user must pick the GSP)

The NIC e-way bill system is reached through a GSP/ASP. Two proven contracts:

1. **Resilient Tech** (`https://asp.resilient.tech`) — what india_compliance uses.
   Header `x-api-key` = an India-Compliance API secret; per-GSTIN NIC portal
   login (username/password) in a credentials table; `sandbox_mode` → `/test`.
   Standard (direct-NIC) mode adds AES/RSA session-key encryption + HMAC.
2. **Adaequare** (`https://gsp.adaequare.com`) — what the F15 app used. OAuth
   app token (`gspappid`/`gspappsecret`) + per-request NIC `username`/`password`/
   `gstin` headers; staging/live toggle.

Either way we implement the client natively (requests + our own Settings +
per-GSTIN credential doctype, passwords **encrypted**).

## Custom fields to add per source doctype (settings-driven)

A **YRP E-Waybill Settings** doctype lists which DocTypes are e-way-bill-enabled;
on save it creates (as Custom Fields) on each listed doctype:

Transport (Part A/B inputs): `transporter` (Link Supplier), `gst_transporter_id`,
`mode_of_transport` (Road/Air/Rail/Ship), `vehicle_no`, `gst_vehicle_type`
(Regular/ODC), `lr_no`, `lr_date`, `distance`.
Result: `ewaybill` (read-only), `e_waybill_status` (Select).
Plus a **"Generate e-Waybill"** custom button (+ Cancel / Update Vehicle /
Extend, gated by status & permissions), replicating india_compliance's
`e_waybill_actions.js` UX (button group "e-Waybill").

## The core challenge: yrp movement docs lack the GST tax layer

`Delivery Challan`, `Goods Received Note`, `Stock Entry` are stock/production
docs — **not** ERPNext GST docs. Gap analysis:

| EWB need | Status on DC / GRN / Stock Entry |
|---|---|
| Item HSN | reachable: `item_variant → Item → item.hsn_code` (permlevel 1) |
| Qty | present |
| **Taxable value per row** | **missing** (only `amount`/`rate`) |
| **CGST/SGST/IGST rate & amount per row + doc totals** | **missing (no tax table at all)** |
| **place_of_supply** | **missing** |
| Company GSTIN | reachable via `from_warehouse.supplier` (`is_company_location`) `.gstin` |
| Party GSTIN | reachable via supplier/`to_warehouse.supplier` `.gstin` |
| From/To address (line/city/pincode/state code) | reachable via Supplier/Warehouse → Address **if those Address records carry gstin + gst_state_number** |
| Transport (transporter id, mode, LR, distance, vehicle type) | missing except `vehicle_no` |

So besides the transport fields, the dominant work is **manufacturing the GST
tax breakup** on these docs. Options (need user decision):
- **(a)** Add a small tax mechanism (Item GST rate / HSN-based) and compute
  taxable value + CGST/SGST/IGST per row at generate time.
- **(b)** For GRN, pull tax data from the linked **Purchase Invoice** if one exists.
- **(c)** Enter the tax/value data manually in the generate dialog for v1.

## Config the user must provide

**One-time (account / credentials):**
1. GSP/ASP provider + **API secret / app credentials** (Resilient Tech key, or
   Adaequare `gspappid`/`gspappsecret`).
2. **Sandbox vs production.**
3. Per-GSTIN **e-Way Bill portal login** (GSTIN + username + password), registered
   on the NIC portal.
4. The **company GSTIN** (and that the company-location Supplier + its Address
   carry GSTIN + state code).

**Per-document (each transaction):** transporter and/or GST Transporter ID, mode
of transport, vehicle no (Road) or LR no + date, GST vehicle type, distance
(0 = let portal compute).

## Decisions (user, 2026-07-05)
1. **GSP / API:** replicate the **erpnext + india_compliance** engine + NIC/GSP
   contract natively. **Do NOT reuse the F15 `ewb_api_integration` (Adaequare) app.**
   Provider specifics + credentials the user will supply later.
2. **GST tax breakup:** replicate **how erpnext + india_compliance manage it** —
   Item Tax Template / GST accounts / taxes computation producing per-line
   taxable value + CGST/SGST/IGST + place_of_supply. (Not manual entry, not PI-pull.)
3. **Scope:** implement on **ONE doctype first — Delivery Challan** — prove the full
   flow, then extend to **Stock Entry + Goods Received Note**.

## Status
Research on the e-way bill engine complete. App scaffolded + pushed. Next: a focused
research pass on the erpnext/india_compliance **GST tax-computation layer** (how
per-line taxable value + CGST/SGST/IGST + place_of_supply are produced), then a
detailed implementation plan for the Delivery Challan v1 — before writing engine code.
