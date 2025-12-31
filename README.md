# Grab Receipts Exporter

A Python CLI tool that exports Grab receipt emails from iCloud Mail to CSV format. It connects via IMAP, parses receipt emails to extract transaction details, and appends results to a CSV file. Uses UID-based state tracking to only process new emails on subsequent runs.

## Features

- Connects to iCloud Mail via IMAP
- Automatically detects receipt type: **GrabFood**, **GrabTransport**, or **GrabTip**
- Extracts order ID, total amount (THB), and service-specific metadata
- Incremental processing - only fetches new emails since last run
- Outputs to CSV with JSON metadata column

## Installation

Requires Python 3.11+ and [Poetry](https://python-poetry.org/).

```bash
# Clone the repository
git clone https://github.com/yourusername/grab-receipts-exporter.git
cd grab-receipts-exporter

# Install dependencies
poetry install
```

## Configuration

Create a `.env` file in the project root:

```env
ICLOUD_USER=your.email@icloud.com
ICLOUD_PASS=your-app-specific-password
ICLOUD_MAILBOX=INBOX/Grab
```

> **Note**: You need to generate an [app-specific password](https://support.apple.com/en-us/HT204397) for iCloud Mail.

## Usage

```bash
# Run the exporter
poetry run grab-export

# Run with custom options
poetry run grab-export --mailbox "INBOX/Grab" --csv-path data/receipts.csv --state-path state/last_uid.txt
```

### Options

| Option | Default | Description |
|--------|---------|-------------|
| `--mailbox` | `INBOX/Grab` | IMAP mailbox containing Grab receipts |
| `--csv-path` | `data/grab_receipts.csv` | Output CSV file path |
| `--state-path` | `state/last_uid.txt` | State file for tracking last processed UID |

## CSV Output Schema

| Field | Description |
|-------|-------------|
| `uid` | Email UID |
| `date` | Email date (ISO format) |
| `type` | Service type: GrabFood, GrabTransport, or GrabTip |
| `order_id` | Grab order ID (e.g., A-7PPCC7TGW4P8AV) |
| `currency` | Currency code (THB) |
| `total_amount` | Total amount charged |
| `metadata` | JSON string with service-specific details |

### Metadata by Service Type

**GrabFood:**
- `restaurant`, `delivery_address`, `items`, `subtotal`, `delivery_fee`, `platform_fee`, `payment_method`

**GrabTransport:**
- `service_class`, `pickup`, `pickup_time`, `dropoff`, `dropoff_time`, `distance_km`, `duration_min`, `fare`, `toll`, `platform_fee`, `payment_method`

**GrabTip:**
- `driver_name`, `payment_method`

## Development

```bash
# Run tests
poetry run pytest

# Run tests with verbose output
poetry run pytest -v
```

## How It Works

1. Connects to iCloud IMAP server
2. Searches for emails with subject "Your Grab E-Receipt" newer than last processed UID
3. For each email:
   - Detects service type using infrastructure markers (S3 domains, URL parameters)
   - Extracts order ID, total amount, and date
   - Extracts service-specific metadata from HTML content
4. Appends rows to CSV file
5. Saves last processed UID for incremental processing

## License

MIT
