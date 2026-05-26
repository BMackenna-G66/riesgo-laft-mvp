-- Query 2: Métricas transaccionales 30/90/180 días desde treasury.cash_call
-- Fuente: treasury.cash_call
-- Uso: staging_cash_metrics — volumen, frecuencia, rechazo por cliente

SELECT
    customer_id,

    COUNT(*) AS trx_total_180d,

    COUNT(CASE WHEN creation_date >= DATEADD(day, -30, CURRENT_DATE) THEN 1 END) AS trx_30d,
    COUNT(CASE WHEN creation_date >= DATEADD(day, -90, CURRENT_DATE) THEN 1 END) AS trx_90d,
    COUNT(CASE WHEN creation_date >= DATEADD(day, -180, CURRENT_DATE) THEN 1 END) AS trx_180d,

    SUM(CASE WHEN creation_date >= DATEADD(day, -30, CURRENT_DATE) THEN destiny_amount_usd ELSE 0 END) AS volume_usd_30d,
    SUM(CASE WHEN creation_date >= DATEADD(day, -90, CURRENT_DATE) THEN destiny_amount_usd ELSE 0 END) AS volume_usd_90d,
    SUM(CASE WHEN creation_date >= DATEADD(day, -180, CURRENT_DATE) THEN destiny_amount_usd ELSE 0 END) AS volume_usd_180d,

    AVG(CASE WHEN creation_date >= DATEADD(day, -30, CURRENT_DATE) THEN destiny_amount_usd END) AS avg_ticket_usd_30d,
    AVG(CASE WHEN creation_date >= DATEADD(day, -90, CURRENT_DATE) THEN destiny_amount_usd END) AS avg_ticket_usd_90d,
    AVG(CASE WHEN creation_date >= DATEADD(day, -180, CURRENT_DATE) THEN destiny_amount_usd END) AS avg_ticket_usd_180d,

    MAX(destiny_amount_usd) AS max_ticket_usd_180d,

    COUNT(CASE WHEN status = 'paid' THEN 1 END) AS trx_paid_180d,
    COUNT(CASE WHEN status = 'rejected' THEN 1 END) AS trx_rejected_180d,
    COUNT(CASE WHEN status = 'pending_verification' THEN 1 END) AS trx_pending_verification_180d,
    COUNT(CASE WHEN status = 'released' THEN 1 END) AS trx_released_180d,

    CASE
        WHEN COUNT(*) = 0 THEN 0
        ELSE COUNT(CASE WHEN status = 'rejected' THEN 1 END)::DECIMAL / COUNT(*)
    END AS rejection_rate_180d,

    MIN(creation_date) AS first_cash_call_date,
    MAX(creation_date) AS last_cash_call_date

FROM "db_prod"."treasury"."cash_call"
WHERE creation_date >= DATEADD(day, -180, CURRENT_DATE)
GROUP BY customer_id;
