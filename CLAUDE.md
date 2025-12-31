# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

A Python CLI tool that exports Grab receipt emails from iCloud Mail to CSV format. It connects via IMAP, parses receipt emails to extract transaction details (order ID, amount in THB), and appends results to a CSV file. Uses UID-based state tracking to only process new emails on subsequent runs.

## Development Commands

```bash
# Install dependencies (uses Poetry)
poetry install

# Run the CLI
poetry run grab-export

# Run with custom options
poetry run grab-export --mailbox "INBOX/Grab" --csv-path data/grab_receipts.csv --state-path state/last_uid.txt

# Run tests
poetry run pytest

# Run a single test
poetry run pytest tests/test_file.py::test_name
```

## Environment Configuration

Set these environment variables (or use a `.env` file):
- `ICLOUD_USER` - iCloud email address
- `ICLOUD_PASS` - App-specific password for iCloud
- `ICLOUD_IMAP_HOST` - IMAP host (defaults to `imap.mail.me.com`)

## Architecture

Single-module CLI application in `src/grab_receipts_exporter/cli.py`:

- **IMAP connection**: Connects to iCloud IMAP, searches mailbox for UIDs greater than last processed
- **Email parsing**: Extracts text from multipart emails, uses regex patterns to find THB amounts and order IDs
- **State management**: Stores last processed UID in a text file to enable incremental processing
- **CSV output**: Appends rows with fields: uid, message_id, date, from, to, subject, order_id, currency, total_amount
