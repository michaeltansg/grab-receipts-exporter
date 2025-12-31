"""Unit tests for grab_receipts_exporter.cli module."""

from grab_receipts_exporter.cli import (
    extract_total_amount,
    extract_order_id,
    strip_html,
    parse_amount,
    detect_service_type,
    extract_food_metadata,
    extract_transport_metadata,
    extract_tip_metadata,
    extract_metadata,
)


class TestExtractTotalAmount:
    """Tests for extract_total_amount function."""

    def test_thai_baht_symbol_integer(self):
        """Test extraction with Thai Baht symbol and integer."""
        assert extract_total_amount("Total: ฿ 191") == 191.0
        assert extract_total_amount("฿191") == 191.0

    def test_thai_baht_symbol_with_comma(self):
        """Test extraction with comma separator."""
        assert extract_total_amount("฿ 1,234") == 1234.0
        assert extract_total_amount("฿1,234,567") == 1234567.0

    def test_thai_baht_symbol_with_decimals(self):
        """Test extraction with decimal amounts."""
        assert extract_total_amount("฿ 245.00") == 245.0
        assert extract_total_amount("฿1,234.50") == 1234.5

    def test_thb_prefix(self):
        """Test extraction with THB prefix."""
        assert extract_total_amount("THB 245.00") == 245.0
        assert extract_total_amount("Amount: THB 1,234.00") == 1234.0

    def test_thb_suffix(self):
        """Test extraction with THB suffix."""
        assert extract_total_amount("245.00 THB") == 245.0

    def test_no_amount_found(self):
        """Test when no amount is found."""
        assert extract_total_amount("No amount here") is None
        assert extract_total_amount("") is None


class TestExtractOrderId:
    """Tests for extract_order_id function."""

    def test_valid_order_id(self):
        """Test extraction of valid Grab order IDs."""
        assert extract_order_id("Order: A-8Q34JAIGWGQMAV") == "A-8Q34JAIGWGQMAV"
        assert extract_order_id("A-7PPCC7TGW4P8AV is your order") == "A-7PPCC7TGW4P8AV"

    def test_order_id_in_html(self):
        """Test extraction from HTML content."""
        html = '<div>Order ID: A-8DT2W4UG4SNGAV</div>'
        assert extract_order_id(html) == "A-8DT2W4UG4SNGAV"

    def test_no_order_id(self):
        """Test when no order ID is found."""
        assert extract_order_id("No order here") is None
        assert extract_order_id("") is None

    def test_invalid_format(self):
        """Test that invalid formats are not matched."""
        assert extract_order_id("B-1234567890") is None  # Wrong prefix
        assert extract_order_id("A-SHORT") is None  # Too short


class TestStripHtml:
    """Tests for strip_html function."""

    def test_removes_tags(self):
        """Test that HTML tags are removed."""
        assert "Hello World" in strip_html("<p>Hello World</p>")

    def test_removes_style_tags(self):
        """Test that style tags and content are removed."""
        html = "<style>.class { color: red; }</style><p>Content</p>"
        result = strip_html(html)
        assert "color" not in result
        assert "Content" in result

    def test_unescapes_entities(self):
        """Test that HTML entities are unescaped."""
        assert "&" in strip_html("&amp;")
        assert "<" in strip_html("&lt;")

    def test_collapses_whitespace(self):
        """Test that multiple whitespaces are collapsed."""
        result = strip_html("<p>Hello</p>   <p>World</p>")
        assert "  " not in result  # No double spaces


class TestParseAmount:
    """Tests for parse_amount function."""

    def test_simple_number(self):
        """Test parsing simple numbers."""
        assert parse_amount("123") == 123.0
        assert parse_amount("123.45") == 123.45

    def test_with_commas(self):
        """Test parsing numbers with comma separators."""
        assert parse_amount("1,234") == 1234.0
        assert parse_amount("1,234,567.89") == 1234567.89

    def test_invalid_input(self):
        """Test invalid inputs return None."""
        assert parse_amount("abc") is None
        assert parse_amount("") is None


class TestDetectServiceType:
    """Tests for detect_service_type function."""

    def test_grabfood_primary_marker(self):
        """Test GrabFood detection with primary marker."""
        body = "some content SOURCE_GRABFOOD more content"
        assert detect_service_type(body) == "GrabFood"

    def test_grabtransport_primary_marker(self):
        """Test GrabTransport detection with S3 marker."""
        body = "img src='https://myteksi.s3.ap-southeast-1.amazonaws.com/image.png'"
        assert detect_service_type(body) == "GrabTransport"

    def test_grabtip_detection(self):
        """Test GrabTip detection."""
        assert detect_service_type("Tips E-Receipt content") == "GrabTip"
        assert detect_service_type("ทิปเพื่อเป็นกำลังใจ") == "GrabTip"
        assert detect_service_type("Grab Tips E-Receipt") == "GrabTip"

    def test_grabfood_secondary_marker(self):
        """Test GrabFood detection with secondary markers."""
        assert detect_service_type("url?ratingStar%3D5") == "GrabFood"
        # Pattern: orderID%3D00 followed by 9 digits
        assert detect_service_type("orderID%3D00123456789") == "GrabFood"

    def test_grabtransport_secondary_marker(self):
        """Test GrabTransport detection with secondary markers."""
        assert detect_service_type("pick up location: ABC") == "GrabTransport"
        assert detect_service_type("Drop Off Location here") == "GrabTransport"

    def test_unknown_type(self):
        """Test Unknown when no markers found."""
        assert detect_service_type("generic email content") == "Unknown"
        assert detect_service_type("") == "Unknown"

    def test_tip_takes_priority(self):
        """Test that GrabTip detection takes priority over other types."""
        # Has both tip marker and food marker
        body = "Tips E-Receipt SOURCE_GRABFOOD"
        assert detect_service_type(body) == "GrabTip"


class TestExtractFoodMetadata:
    """Tests for extract_food_metadata function."""

    def test_extracts_items(self):
        """Test item extraction."""
        body = "1x ข้าวผัด ฿ 80 2x ต้มยำ ฿ 120"
        metadata = extract_food_metadata(body)
        assert "items" in metadata
        assert "1x ข้าวผัด @80.0" in metadata["items"]
        assert "2x ต้มยำ @120.0" in metadata["items"]

    def test_extracts_subtotal(self):
        """Test subtotal extraction."""
        body = "ค่าอาหาร ฿ 260"
        metadata = extract_food_metadata(body)
        assert metadata.get("subtotal") == 260.0

    def test_extracts_delivery_fee(self):
        """Test delivery fee extraction."""
        body = "ค่าจัดส่ง ฿ 36"
        metadata = extract_food_metadata(body)
        assert metadata.get("delivery_fee") == 36.0

    def test_extracts_platform_fee(self):
        """Test platform fee extraction."""
        body = "คำสั่งซื้อพิเศษ ฿ 15"
        metadata = extract_food_metadata(body)
        assert metadata.get("platform_fee") == 15.0

    def test_extracts_payment_method(self):
        """Test payment method extraction."""
        body = "รูปแบบการชำระเงิน MasterCard 1234"
        metadata = extract_food_metadata(body)
        assert metadata.get("payment_method") == "MasterCard 1234"


class TestExtractTransportMetadata:
    """Tests for extract_transport_metadata function."""

    def test_extracts_service_class(self):
        """Test service class extraction."""
        assert extract_transport_metadata("GrabCar Premium ride").get("service_class") == "GrabCar Premium"
        assert extract_transport_metadata("Standard (JustGrab) service").get("service_class") == "Standard (JustGrab)"

    def test_extracts_distance_and_duration(self):
        """Test distance and duration extraction."""
        body = "Trip: 17.18 km • 38 mins"
        metadata = extract_transport_metadata(body)
        assert metadata.get("distance_km") == 17.18
        assert metadata.get("duration_min") == 38

    def test_extracts_fare(self):
        """Test fare extraction."""
        body = "Fare ฿ 556"
        metadata = extract_transport_metadata(body)
        assert metadata.get("fare") == 556.0

    def test_extracts_toll(self):
        """Test toll extraction."""
        body = "Toll ฿ 50"
        metadata = extract_transport_metadata(body)
        assert metadata.get("toll") == 50.0

    def test_extracts_platform_fee(self):
        """Test platform fee extraction."""
        body = "Platform Fee ฿ 20"
        metadata = extract_transport_metadata(body)
        assert metadata.get("platform_fee") == 20.0


class TestExtractTipMetadata:
    """Tests for extract_tip_metadata function."""

    def test_extracts_payment_method(self):
        """Test payment method extraction from tip receipt."""
        body = "ชำระโดย MasterCard 5276"
        metadata = extract_tip_metadata(body)
        assert metadata.get("payment_method") == "MasterCard 5276"


class TestExtractMetadata:
    """Tests for extract_metadata dispatcher function."""

    def test_dispatches_to_food(self):
        """Test that GrabFood type dispatches correctly."""
        body = "ค่าอาหาร ฿ 100"
        metadata = extract_metadata(body, "GrabFood")
        assert "subtotal" in metadata

    def test_dispatches_to_transport(self):
        """Test that GrabTransport type dispatches correctly."""
        body = "Fare ฿ 200"
        metadata = extract_metadata(body, "GrabTransport")
        assert "fare" in metadata

    def test_dispatches_to_tip(self):
        """Test that GrabTip type dispatches correctly."""
        body = "ชำระโดย Visa 1234"
        metadata = extract_metadata(body, "GrabTip")
        assert "payment_method" in metadata

    def test_unknown_returns_empty(self):
        """Test that Unknown type returns empty dict."""
        metadata = extract_metadata("some body", "Unknown")
        assert metadata == {}
