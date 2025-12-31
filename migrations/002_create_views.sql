-- Views for each service type with flattened metadata

-- GrabFood view
CREATE OR REPLACE VIEW v_grab_food AS
SELECT
    uid,
    date,
    order_id,
    currency,
    total_amount,
    metadata->>'restaurant' AS restaurant,
    metadata->>'delivery_address' AS delivery_address,
    metadata->>'items' AS items,
    (metadata->>'subtotal')::DECIMAL(10,2) AS subtotal,
    (metadata->>'delivery_fee')::DECIMAL(10,2) AS delivery_fee,
    (metadata->>'platform_fee')::DECIMAL(10,2) AS platform_fee,
    metadata->>'payment_method' AS payment_method,
    created_at
FROM grab_receipts
WHERE type = 'GrabFood';

COMMENT ON VIEW v_grab_food IS 'Flattened view of GrabFood receipts';

-- GrabTransport view
CREATE OR REPLACE VIEW v_grab_transport AS
SELECT
    uid,
    date,
    order_id,
    currency,
    total_amount,
    metadata->>'service_class' AS service_class,
    metadata->>'pickup' AS pickup,
    metadata->>'pickup_time' AS pickup_time,
    metadata->>'dropoff' AS dropoff,
    metadata->>'dropoff_time' AS dropoff_time,
    (metadata->>'distance_km')::DECIMAL(10,2) AS distance_km,
    (metadata->>'duration_min')::INTEGER AS duration_min,
    (metadata->>'fare')::DECIMAL(10,2) AS fare,
    (metadata->>'toll')::DECIMAL(10,2) AS toll,
    (metadata->>'platform_fee')::DECIMAL(10,2) AS platform_fee,
    metadata->>'payment_method' AS payment_method,
    created_at
FROM grab_receipts
WHERE type = 'GrabTransport';

COMMENT ON VIEW v_grab_transport IS 'Flattened view of GrabTransport receipts';

-- GrabTip view
CREATE OR REPLACE VIEW v_grab_tip AS
SELECT
    uid,
    date,
    order_id,
    currency,
    total_amount AS tip_amount,
    metadata->>'driver_name' AS driver_name,
    metadata->>'payment_method' AS payment_method,
    created_at
FROM grab_receipts
WHERE type = 'GrabTip';

COMMENT ON VIEW v_grab_tip IS 'Flattened view of GrabTip receipts';

-- Summary view for quick stats
CREATE OR REPLACE VIEW v_grab_summary AS
SELECT
    type,
    COUNT(*) AS receipt_count,
    SUM(total_amount) AS total_spent,
    MIN(date) AS first_receipt,
    MAX(date) AS last_receipt
FROM grab_receipts
GROUP BY type
ORDER BY type;

COMMENT ON VIEW v_grab_summary IS 'Summary statistics by service type';
