import argparse
import csv
import email
import email.message
import email.utils
import imaplib
import json
import os
import re
from datetime import timezone, timedelta
from html import unescape
from typing import Any, Dict, List, Optional, Tuple

from dotenv import load_dotenv

# Bangkok timezone (UTC+7)
BANGKOK_TZ = timezone(timedelta(hours=7))


def log(level: str, message: str) -> None:
    """Print a log message."""
    print(f"[{level}] {message}")

load_dotenv(override=True)

IMAP_HOST = os.environ.get("ICLOUD_IMAP_HOST", "imap.mail.me.com")
IMAP_PORT = 993

ICLOUD_USER = os.environ.get("ICLOUD_USER")
ICLOUD_PASS = os.environ.get("ICLOUD_PASS")
ICLOUD_MAILBOX = os.environ.get("ICLOUD_MAILBOX", "INBOX/Grab")


def get_email_text(msg: email.message.Message) -> str:
    """
    Combine text/plain and text/html into one big string for regex parsing.
    """
    parts: List[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype in ("text/plain", "text/html"):
                try:
                    payload = part.get_payload(decode=True)
                    if payload is None:
                        continue
                    charset = part.get_content_charset() or "utf-8"
                    parts.append(payload.decode(charset, errors="replace"))
                except Exception:
                    continue
    else:
        ctype = msg.get_content_type()
        if ctype in ("text/plain", "text/html"):
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                parts.append(payload.decode(charset, errors="replace"))
    return "\n".join(parts)


def extract_total_amount(body: str) -> Optional[float]:
    """
    Extract total amount from Grab receipts.
    Formats found in actual emails:
    - ฿ 191 (Thai Baht symbol with integer, most common)
    - ฿ 1,234 (with comma separator)
    - THB 245.00 (with decimals, less common)
    """
    patterns = [
        # Thai Baht symbol - integer or with optional decimals
        r"฿\s*([\d,]+(?:\.\d{2})?)",
        # THB prefix with decimals
        r"THB\s*([\d,]+\.\d{2})",
        # THB suffix
        r"([\d,]+\.\d{2})\s*THB",
    ]
    for pat in patterns:
        m = re.search(pat, body)
        if m:
            val = m.group(1).replace(",", "")
            try:
                return float(val)
            except ValueError:
                pass
    return None


def extract_order_id(body: str) -> Optional[str]:
    """
    Extract order/booking ID from Grab receipts.
    All Grab order IDs follow the pattern: A-XXXXXXXXXXXXXX (A- followed by alphanumeric)
    Examples: A-8Q34JAIGWGQMAV, A-7PPCC7TGW4P8AV
    """
    # Direct pattern match for Grab order IDs
    m = re.search(r"A-[A-Z0-9]{10,}", body)
    if m:
        return m.group(0)
    return None


def strip_html(html: str) -> str:
    """Remove HTML tags but keep text content."""
    text = re.sub(r"<style[^>]*>.*?</style>", "", html, flags=re.DOTALL | re.IGNORECASE)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text)
    return unescape(text)


def parse_amount(val: str) -> Optional[float]:
    """Parse a string amount to float, handling commas."""
    try:
        return float(val.replace(",", ""))
    except (ValueError, AttributeError):
        return None


def extract_food_metadata(body: str) -> Dict[str, Any]:
    """
    Extract metadata from GrabFood receipts.
    Returns: restaurant, delivery_address, items (flattened), subtotal, delivery_fee, platform_fee, payment_method
    """
    text = strip_html(body)
    metadata: Dict[str, Any] = {}

    # Restaurant name - appears after "สถานที่เริ่มต้นการเดินทาง:" (Thai)
    m = re.search(r"สถานที่เริ่มต้นการเดินทาง:\s*(.+?)\s*สถานที่ปลายทาง", text)
    if m:
        metadata["restaurant"] = m.group(1).strip()

    # Delivery address - appears after "สถานที่ปลายทาง:" (Thai)
    m = re.search(r"สถานที่ปลายทาง:\s*(.+?)\s*โปรไฟล์", text)
    if m:
        metadata["delivery_address"] = m.group(1).strip()

    # Items - pattern: "1x item_name ฿ price" (flattened as "qty x name @ price")
    items = []
    for match in re.finditer(r"(\d+)x\s+(.+?)\s+฿\s*([\d,]+)", text):
        qty = int(match.group(1))
        name = match.group(2).strip()
        price = parse_amount(match.group(3))
        items.append(f"{qty}x {name} @{price}")
    if items:
        metadata["items"] = "; ".join(items)

    # Subtotal (ค่าอาหาร)
    m = re.search(r"ค่าอาหาร\s+฿\s*([\d,]+)", text)
    if m:
        metadata["subtotal"] = parse_amount(m.group(1))

    # Delivery fee (ค่าจัดส่ง)
    m = re.search(r"ค่าจัดส่ง\s+฿\s*([\d,]+)", text)
    if m:
        metadata["delivery_fee"] = parse_amount(m.group(1))

    # Platform fee (คำสั่งซื้อพิเศษ or small order fee)
    m = re.search(r"(?:คำสั่งซื้อพิเศษ|Platform Fee|Small Order Fee)\s*\d*\s*฿\s*([\d,]+)", text)
    if m:
        metadata["platform_fee"] = parse_amount(m.group(1))

    # Payment method
    m = re.search(r"(?:รูปแบบการชำระเงิน|Paid by|Payment)[:\s]*(MasterCard|Visa|Cash|GrabPay|เงินสด)\s*(\d{4})?", text, re.IGNORECASE)
    if m:
        method = m.group(1)
        last4 = m.group(2) or ""
        metadata["payment_method"] = f"{method} {last4}".strip()

    return metadata


def extract_transport_metadata(body: str) -> Dict[str, Any]:
    """
    Extract metadata from GrabTransport receipts.
    Returns: service_class, pickup, dropoff, distance_km, duration_min, fare, toll, platform_fee, payment_method
    """
    text = strip_html(body)
    metadata: Dict[str, Any] = {}

    # Service class - appears at the top (e.g., "GrabCar Premium", "Standard (JustGrab)")
    m = re.search(r"(GrabCar\s*Premium|Standard\s*\(JustGrab\)|JustGrab|GrabBike)", text, re.IGNORECASE)
    if m:
        metadata["service_class"] = m.group(1).strip()

    # Distance and duration - pattern: "17.18 km • 38 mins" or "17 km • 38 min"
    m = re.search(r"([\d.]+)\s*km\s*[•·]\s*(\d+)\s*min", text)
    if m:
        metadata["distance_km"] = float(m.group(1))
        metadata["duration_min"] = int(m.group(2))

    # Pickup and dropoff - format is "Location TIME Location TIME"
    # e.g., "The River Condominium North Tower 8:13AM SCB Park Plaza West (Main Entrance) 8:52AM"
    locations_times = re.findall(r"([^⋮]+?)\s+(\d{1,2}:\d{2}[AP]M)", text)
    if len(locations_times) >= 2:
        metadata["pickup"] = locations_times[0][0].strip()
        metadata["pickup_time"] = locations_times[0][1]
        metadata["dropoff"] = locations_times[1][0].strip()
        metadata["dropoff_time"] = locations_times[1][1]

    # Fare breakdown
    # Base fare
    m = re.search(r"(?:Fare|ค่าโดยสาร)\s+(?:฿\s*)?([\d,]+)", text)
    if m:
        metadata["fare"] = parse_amount(m.group(1))

    # Toll
    m = re.search(r"Toll\s+(?:฿\s*)?([\d,]+)", text, re.IGNORECASE)
    if m:
        metadata["toll"] = parse_amount(m.group(1))

    # Platform fee
    m = re.search(r"Platform Fee\s+(?:฿\s*)?([\d,]+)", text, re.IGNORECASE)
    if m:
        metadata["platform_fee"] = parse_amount(m.group(1))

    # Payment method
    m = re.search(r"(?:Paid by|Payment)[:\s]*(?:.*?)(\d{4})\s*(?:฿|THB)", text, re.IGNORECASE)
    if m:
        metadata["payment_method"] = f"Card ending {m.group(1)}"
    else:
        m = re.search(r"(MasterCard|Visa|Cash|GrabPay)\s*(\d{4})?", text, re.IGNORECASE)
        if m:
            method = m.group(1)
            last4 = m.group(2) or ""
            metadata["payment_method"] = f"{method} {last4}".strip()

    return metadata


def extract_tip_metadata(body: str) -> Dict[str, Any]:
    """
    Extract metadata from GrabTip receipts.
    Returns: driver_name, payment_method
    Note: order_id is already in the main CSV row, so not duplicated here.
    """
    text = strip_html(body)
    metadata: Dict[str, Any] = {}

    # Driver name (ชื่อผู้ขับ)
    m = re.search(r"(?:ชื่อผู้ขับ|Driver)[:\s]*(?:\(GB\))?\s*([^\n]+?)(?:\s*ชื่อผู้เดินทาง|$)", text)
    if m:
        metadata["driver_name"] = m.group(1).strip()

    # Payment method
    m = re.search(r"(?:ชำระโดย|Paid by|Payment)[:\s]*(MasterCard|Visa|Cash|GrabPay)\s*(\d{4})?", text, re.IGNORECASE)
    if m:
        method = m.group(1)
        last4 = m.group(2) or ""
        metadata["payment_method"] = f"{method} {last4}".strip()

    return metadata


def detect_service_type(body: str) -> str:
    """
    Detect whether the receipt is from GrabFood, GrabTransport, or GrabTip.
    """
    # Check for tip receipt first (has specific markers)
    # Thai: "ทิปเพื่อเป็นกำลังใจ" or "ค่าทิป"
    # English: "Tips E-Receipt" or title contains "Tip"
    if re.search(r"Tips E-Receipt|ทิปเพื่อเป็นกำลังใจ|Grab Tips E-Receipt", body):
        return "GrabTip"

    # Primary markers (100% reliable)
    if "SOURCE_GRABFOOD" in body:
        return "GrabFood"
    if re.search(r"myteksi\.s3.*?\.amazonaws\.com", body):
        return "GrabTransport"

    # Secondary markers (fallback)
    if re.search(r"ratingStar%3D|orderID%3D00\d{9}", body):
        return "GrabFood"
    if re.search(r"(?i)pick.{0,5}up\s+location|drop.{0,5}off\s+location", body):
        return "GrabTransport"

    return "Unknown"


def extract_metadata(body: str, service_type: str) -> Dict[str, Any]:
    """
    Extract metadata based on service type.
    """
    if service_type == "GrabFood":
        return extract_food_metadata(body)
    elif service_type == "GrabTransport":
        return extract_transport_metadata(body)
    elif service_type == "GrabTip":
        return extract_tip_metadata(body)
    return {}


def parse_email_to_row(uid: int, msg: email.message.Message) -> Dict[str, str]:
    """
    Convert one email into a CSV row (all values are strings).
    """
    date_raw = msg.get("Date", "")

    try:
        dt = email.utils.parsedate_to_datetime(date_raw)
        date_iso = dt.isoformat()
    except Exception:
        date_iso = date_raw

    body_text = get_email_text(msg)

    total = extract_total_amount(body_text)
    order_id = extract_order_id(body_text)
    service_type = detect_service_type(body_text)
    metadata = extract_metadata(body_text, service_type)

    row = {
        "uid": str(uid),
        "date": date_iso,
        "type": service_type,
        "order_id": order_id or "",
        "currency": "THB" if total is not None else "",
        "total_amount": f"{total:.2f}" if total is not None else "",
        "metadata": json.dumps(metadata, ensure_ascii=False) if metadata else "",
    }
    return row


def load_last_uid(path: str) -> int:
    if not os.path.exists(path):
        return 0
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        return int(content) if content else 0
    except Exception:
        return 0


def save_last_uid(path: str, uid: int) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(str(uid))


def ensure_csv_with_header(path: str, fieldnames: List[str]) -> Tuple[csv.DictWriter, bool]:
    """
    Open CSV file in append mode, ensure header exists exactly once.
    Returns (writer, is_new_file).
    """
    is_new = not os.path.exists(path) or os.path.getsize(path) == 0

    f = open(path, "a", newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=fieldnames)

    if is_new:
        writer.writeheader()

    # We return writer and leave the file attached (caller must close via writer.writerows + writer.writer)
    # But we need the underlying file object, so let's attach for convenience.
    writer._file = f  # type: ignore[attr-defined]
    return writer, is_new


def close_csv_writer(writer: csv.DictWriter) -> None:
    f = getattr(writer, "_file", None)
    if f is not None:
        f.close()


def fetch_new_uids(
    imap: imaplib.IMAP4_SSL, mailbox: str, last_uid: int, subject_filter: Optional[str] = None
) -> List[int]:
    typ, _ = imap.select(f'"{mailbox}"', readonly=True)
    if typ != "OK":
        raise RuntimeError(f"Could not select mailbox {mailbox!r}")

    # Build search criteria
    criteria: List[str] = []
    if last_uid > 0:
        criteria.append(f"UID {last_uid+1}:*")
    if subject_filter:
        criteria.append(f'SUBJECT "{subject_filter}"')

    if not criteria:
        search_str = "ALL"
    else:
        search_str = " ".join(criteria)

    typ, data = imap.uid("SEARCH", None, search_str)

    if typ != "OK":
        raise RuntimeError("IMAP UID SEARCH failed")

    if not data or not data[0]:
        return []

    uids = [int(u) for u in data[0].split() if u]
    return sorted(uids)


GRAB_SUBJECT_FILTER = "Your Grab E-Receipt"


def process_mailbox_to_csv(
    mailbox: str,
    csv_path: str,
    state_path: str,
) -> None:
    if not ICLOUD_USER or not ICLOUD_PASS:
        raise SystemExit("Please set ICLOUD_USER and ICLOUD_PASS environment variables.")

    last_uid = load_last_uid(state_path)
    log("INFO", f"Last processed UID: {last_uid}")

    log("INFO", f"Connecting to {IMAP_HOST}...")
    imap = imaplib.IMAP4_SSL(IMAP_HOST, IMAP_PORT)
    imap.login(ICLOUD_USER, ICLOUD_PASS)
    log("INFO", "Logged in successfully")

    try:
        uids = fetch_new_uids(imap, mailbox, last_uid, subject_filter=GRAB_SUBJECT_FILTER)
        if not uids:
            log("INFO", "No new messages.")
            return

        log("INFO", f"Found {len(uids)} new message(s) in {mailbox!r}.")

        fieldnames = [
            "uid",
            "date",
            "type",
            "order_id",
            "currency",
            "total_amount",
            "metadata",
        ]
        writer, _ = ensure_csv_with_header(csv_path, fieldnames)

        max_uid = last_uid
        processed_count = 0

        try:
            for uid in uids:
                if uid > max_uid:
                    max_uid = uid

                typ, msg_data = imap.uid("FETCH", str(uid), "(BODY[])")
                if typ != "OK" or not msg_data:
                    log("WARN", f"Failed to fetch UID {uid}")
                    continue

                # msg_data can have extra items (e.g., FLAGS from previous fetch)
                # Find the tuple that contains the email body
                raw_email = None
                for item in msg_data:
                    if isinstance(item, tuple) and len(item) >= 2:
                        if isinstance(item[1], bytes) and len(item[1]) > 100:
                            raw_email = item[1]
                            break
                if not raw_email:
                    log("WARN", f"No email body for UID {uid}")
                    continue
                msg = email.message_from_bytes(raw_email)

                row = parse_email_to_row(uid, msg)
                writer.writerow(row)
                # Format date for display: "2025-04-24T05:26:59+00:00" -> "2025-04-24 @ 05:26:59"
                date_display = row['date'][:10] + " @ " + row['date'][11:19] if row['date'] else "unknown"
                log("INFO", f"UID {uid} | [{date_display}] | {row['type']} | {row['order_id']} | ฿{row['total_amount']}")
                processed_count += 1
        finally:
            close_csv_writer(writer)

        save_last_uid(state_path, max_uid)
        log("INFO", f"Exported {processed_count} receipts to {csv_path}")

    finally:
        try:
            imap.logout()
        except Exception:
            pass


def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Export Grab receipts from an iCloud Mail folder to CSV."
    )
    p.add_argument(
        "--mailbox",
        default=ICLOUD_MAILBOX,
        help="IMAP mailbox/folder containing Grab receipts (default: INBOX/Grab, or ICLOUD_MAILBOX env var)",
    )
    p.add_argument(
        "--csv-path",
        default="data/grab_receipts.csv",
        help="Path to output CSV file (default: data/grab_receipts.csv)",
    )
    p.add_argument(
        "--state-path",
        default="state/last_uid.txt",
        help="Path to state file storing last processed UID (default: state/last_uid.txt)",
    )
    return p


def main() -> None:
    parser = build_arg_parser()
    args = parser.parse_args()
    os.makedirs(os.path.dirname(args.csv_path), exist_ok=True)
    os.makedirs(os.path.dirname(args.state_path), exist_ok=True)

    process_mailbox_to_csv(
        mailbox=args.mailbox,
        csv_path=args.csv_path,
        state_path=args.state_path,
    )


if __name__ == "__main__":
    main()