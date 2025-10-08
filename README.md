# Promodeagro Packer CLI (Production)

A production-ready, menu-driven CLI for packer workflows using DynamoDB as the backend. It organizes features by the provided OpenAPI structure (Auth, Orders, Profile, Notifications) but performs actions directly against AWS DynamoDB (no HTTP server required).

## Features
- Secure email + password login (bcrypt) using `dev-promodeagro-admin-promodeagroUsers`
  - Reads `passwordHash` (preferred) with fallback to `password_hash`
- Orders
  - Realtime counts (Unpacked/Packed)
  - Browse unpacked/packed with interactive pagination
  - Show ALL unpacked/packed (paged)
  - Get order by `order_id`
  - Start order (completion): requires `photo_url`, `video_url`, `packed_by`
  - Complete ALL unpacked (bulk)
  - Per-item packing: mark each item Available/Unavailable and save `items[].availability` + `packing_summary`
  - Show packing summary (available/unavailable lists and totals)
- Profile (Packers)
  - Get packer by `packer_id`
  - Update packer `username`/`email`
- Notifications
  - List all (scan) or by `user_id` (if GSI exists)

## Requirements
- Python 3.10+
- AWS credentials configured with access to DynamoDB in `ap-south-1`
- Python packages: `boto3`, `rich`, `pyyaml`, `bcrypt`

Install:
```bash
python3 -m venv venv
. venv/bin/activate
pip install boto3 rich pyyaml bcrypt
```

## Configuration
Default region: `ap-south-1`. Tables used:
- `dev-promodeagro-admin-promodeagroUsers` (Auth)
- `dev-promodeagro-admin-OrdersTable` (Orders)
- `dev-promodeagro-admin-PackersTable` (Profile)
- `dev-promodeagro-admin-notificationsTable` (Notifications)

To switch to production tables, edit the `DDB` class constants in `promodeagro_packer_cli.py` (or ask me to add env-config).

## Run
```bash
python3 promodeagro_packer_cli.py
```
Flow:
1) Welcome → `1 Login` → email/password
2) Then choose: Orders, Profile, Notifications

Tips:
- Menu is numbers-only; invalid choices show friendly errors
- Orders menu shows real-time counts in the title and options

## Test Credentials
Shown on the login screen for convenience:
- Email: `sohailpacker@gmail.com`
- Password: `Packer@123`

Set or change password:
```bash
python3 promodeagro_password_tool.py EMAIL NEW_PASSWORD
```

## Security Notes
- Store only bcrypt hashes (`passwordHash`), never plaintext
- Use least-privilege IAM for the CLI’s AWS credentials
- Keep PITR enabled on critical tables (OrdersTable has it enabled)
- Prefer SSE at rest (DynamoDB default)

## Operational Notes
- JSON view converts DynamoDB `Decimal` to JSON-safe types
- Bulk completion caps to 100 items (tunable)
- Per-item packing saves availability and a summary on the order

## Troubleshooting
- Missing module errors: `pip install bcrypt boto3 rich pyyaml`
- EOFError: run interactively in a terminal
- AccessDenied/Validation: verify AWS credentials, region, table names/GSIs

## Repository Layout
- `promodeagro_packer_cli.py` → Main CLI
- `promodeagro_password_tool.py` → Admin utility to set `passwordHash`
- `generate_design.py` → Generates `design.png` ER-style diagram
- `design.png` → Visual database relationships around `OrdersTable`

## Roadmap
- Session file to auto-fill `packed_by` from logged-in user
- Env-based configuration for region/table names
- Validate `packed_by` exists in `PackersTable`
- Export packing summary (CSV/JSON)
