### YRP E-Waybill Integration

E-way bill generation for yrp (Delivery Challan, Stock Entry, Goods Received Note); replicated from india_compliance

### Installation

You can install this app using the [bench](https://github.com/frappe/bench) CLI:

```bash
cd $PATH_TO_YOUR_BENCH
bench get-app $URL_OF_THIS_REPO --branch develop
bench install-app yrp_ewaybill_api
```

### Custom fields

Fields added to upstream DocTypes are owned as `Custom Field` records and exported in
`yrp_ewaybill_api/fixtures/custom_field.json` through the module-scoped fixture in
`hooks.py`. Do not duplicate their schema in Python or recreate them from migration
hooks.

### Contributing

This app uses `pre-commit` for code formatting and linting. Please [install pre-commit](https://pre-commit.com/#installation) and enable it for this repository:

```bash
cd apps/yrp_ewaybill_api
pre-commit install
```

Pre-commit is configured to use the following tools for checking and formatting your code:

- ruff
- eslint
- prettier
- pyupgrade

### License

mit
