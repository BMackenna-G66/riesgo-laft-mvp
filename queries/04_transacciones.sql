-- Query 4: Transacciones con destino / beneficiario desde transaction.transaction
-- Fuente: transaction.transaction
-- Uso: staging_tx_metrics — dispersión geográfica, beneficiarios únicos

SELECT
    customer_id,

    COUNT(*) AS tx_total_180d,

    COUNT(DISTINCT beneficiary_id) AS unique_beneficiaries_180d,
    COUNT(DISTINCT beneficiary_country_code) AS unique_beneficiary_countries_180d,

    COUNT(DISTINCT origin_country) AS unique_origin_countries_180d,
    COUNT(DISTINCT destiny_country) AS unique_destiny_countries_180d,

    SUM(destiny_amount_usd) AS tx_volume_usd_180d,
    AVG(destiny_amount_usd) AS tx_avg_ticket_usd_180d,
    MAX(destiny_amount_usd) AS tx_max_ticket_usd_180d,

    COUNT(CASE WHEN tx_status = 'transferencia exitosa' THEN 1 END) AS tx_success_180d,
    COUNT(CASE WHEN tx_status = 'devuelto' THEN 1 END) AS tx_returned_180d,
    COUNT(CASE WHEN tx_status = 'datos verificados' THEN 1 END) AS tx_pending_180d,

    MIN(start_date) AS first_tx_date,
    MAX(start_date) AS last_tx_date

FROM "db_prod"."transaction"."transaction"
WHERE start_date >= DATEADD(day, -180, CURRENT_DATE)
GROUP BY customer_id;
