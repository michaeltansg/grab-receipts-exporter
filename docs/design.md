# Decision: Differentiating GrabFood vs GrabTransport Receipts

## Problem
Grab sends receipts for two types of services (GrabFood and GrabTransport) with the same subject line "Your Grab E-Receipt". We need to identify the service type for each receipt.

## Analysis
Analyzed 15+ email samples and identified consistent markers in the HTML content.

## Decision: Use Infrastructure-Based Markers

### Primary Markers (100% reliable)

| Service Type | Marker | Why It Works |
|--------------|--------|--------------|
| **GrabFood** | `SOURCE_GRABFOOD` | URL parameter in rating/review links unique to food orders |
| **GrabTransport** | `myteksi.s3.amazonaws.com` | Legacy AWS S3 bucket domain used only for transport assets |

### Fallback Markers (if primary fails)

| Service Type | Marker |
|--------------|--------|
| GrabFood | `ratingStar%3D` or `orderID%3D00\d{9}` |
| GrabTransport | `pick up location` or `drop off location` text |

## Implementation

```python
def detect_service_type(body: str) -> str:
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
```

## Test Results
- 15 emails tested: 6 GrabFood, 9 GrabTransport, 0 Unknown
- 100% classification accuracy

## Rationale
- **Infrastructure markers are stable**: CDN/S3 domains rarely change
- **Simple string matching**: `SOURCE_GRABFOOD` is a simple `in` check, very fast
- **Fallback provides safety**: Secondary markers catch edge cases if infrastructure changes

---

# Proposal: Metadata Fields for Each Service Type

## Analysis of Sample Emails

Analyzed 5 sample emails:
- 2 GrabFood receipts (regular food orders)
- 2 GrabTransport receipts (ride receipts)
- 1 GrabFood tip receipt

## Proposed Metadata Schema

### GrabFood Metadata

| Field | Description | Example |
|-------|-------------|---------|
| `restaurant` | Restaurant name | "ร้านอาหารตัวอย่าง - สาขา 1" |
| `delivery_address` | Delivery destination | "Home" |
| `items` | Array of ordered items | `[{"qty": 1, "name": "ก๋วยเตี๋ยว", "price": 140}]` |
| `subtotal` | Food cost before fees | 140 |
| `delivery_fee` | Delivery charge | 36 |
| `platform_fee` | Platform/small order fee | 15 |
| `payment_method` | Payment method used | "MasterCard ****" |

### GrabTransport Metadata

| Field | Description | Example |
|-------|-------------|---------|
| `service_class` | Type of ride | "GrabCar Premium", "Standard (JustGrab)" |
| `pickup` | Pickup location | "Location A" |
| `pickup_time` | Time of pickup | "8:13AM" |
| `dropoff` | Dropoff location | "Location B" |
| `dropoff_time` | Time of dropoff | "8:52AM" |
| `distance_km` | Trip distance | 17.18 |
| `duration_min` | Trip duration | 38 |
| `fare` | Base fare | 556 |
| `toll` | Toll charges | 50 |
| `platform_fee` | Platform fee | 20 |
| `payment_method` | Payment method used | "MasterCard ****" |

## Sample Output

```json
// GrabFood
{
  "restaurant": "ร้านอาหารตัวอย่าง",
  "delivery_address": "Home",
  "items": [
    {"qty": 1, "name": "ข้าวผัด", "price": 80},
    {"qty": 1, "name": "ต้มยำกุ้ง", "price": 120},
    {"qty": 1, "name": "ผัดไทย", "price": 60}
  ],
  "subtotal": 260,
  "delivery_fee": 23,
  "platform_fee": 12,
  "payment_method": "MasterCard ****"
}

// GrabTransport
{
  "service_class": "GrabCar Premium",
  "pickup": "Location A",
  "dropoff": "Location B",
  "distance_km": 17.18,
  "duration_min": 38,
  "fare": 556,
  "toll": 50,
  "platform_fee": null,
  "payment_method": "MasterCard ****"
}
```

## Notes

1. **Thai language**: Most food receipts are in Thai. Restaurant names and item names will be in Thai.

2. **Item parsing**: Items are flattened to string format: `"1x Item Name @price; 2x Other Item @price"`

---

# Implementation: Metadata Extraction (Completed)

## Changes Made

Added metadata extraction for all three service types:

### GrabTip Detection
Tip receipts are detected first using: `Tips E-Receipt|ทิปเพื่อเป็นกำลังใจ|Grab Tips E-Receipt`

### GrabTip Metadata
| Field | Description | Example |
|-------|-------------|---------|
| `driver_name` | Driver who received tip | "สมชาย ใจดี" |
| `payment_method` | Payment method | "MasterCard ****" |

Note: `order_id` and `total_amount` (tip amount) are in the main CSV row, not duplicated in metadata.

### Final CSV Schema
```
uid, date, type, order_id, currency, total_amount, metadata
```

Where `metadata` is a JSON string containing service-specific fields.

## Test Results (5 sample emails)

| File | Type | Metadata Extracted |
|------|------|-------------------|
| Food.eml | GrabFood | restaurant, delivery_address, items, subtotal, delivery_fee, platform_fee, payment_method |
| Food2.eml | GrabTip | driver_name, payment_method |
| Food3.eml | GrabFood | restaurant, delivery_address, items (3 items), subtotal, delivery_fee, platform_fee, payment_method |
| Transport.eml | GrabTransport | service_class, pickup, pickup_time, dropoff, dropoff_time, distance_km, duration_min, fare, toll, payment_method |
| Transport2.eml | GrabTransport | service_class, pickup, pickup_time, dropoff, dropoff_time, distance_km, duration_min, fare, platform_fee, payment_method |
