-- Query 5: Consolidada principal — alimenta directamente el pipeline MVP
-- Fuente: db_prod.customer.customer_v2 + db_prod.treasury.cash_call + db_prod.transaction.transaction
-- Uso: staging principal → features → modelo
-- Nota: solo incluye clientes con actividad en los últimos 180 días (INNER JOIN cash_metrics)

WITH clientes AS (
    SELECT
        cv2.customer_id,
        cv2.email,
        cv2.country_code,
        cv2.created_date                             AS customer_created_at,
        UPPER(TRIM(COALESCE(cv2.risk_level, 'BAJO'))) AS compliance_status,
        cv2.is_company
    FROM "db_prod"."customer"."customer_v2" cv2
),

cash_metrics AS (
    SELECT
        customer_id,
        COUNT(*)                                                             AS trx_180d,
        SUM(destiny_amount_usd)                                              AS volume_usd_180d,
        AVG(destiny_amount_usd)                                              AS avg_ticket_usd_180d,
        MAX(destiny_amount_usd)                                              AS max_ticket_usd_180d,
        COUNT(CASE WHEN status = 'paid'     THEN 1 END)                      AS paid_180d,
        COUNT(CASE WHEN status = 'rejected' THEN 1 END)                      AS rejected_180d,
        CASE
            WHEN COUNT(*) = 0 THEN 0
            ELSE COUNT(CASE WHEN status = 'rejected' THEN 1 END)::DECIMAL / COUNT(*)
        END                                                                   AS rejection_rate_180d,
        COUNT(DISTINCT persona_dni)                                          AS unique_external_funders_180d,
        COUNT(DISTINCT currency_code)                                        AS unique_currencies_180d,
        COUNT(DISTINCT payment_method)                                       AS unique_payment_methods_180d,
        MIN(creation_date)                                                    AS first_operation_date,
        MAX(creation_date)                                                    AS last_operation_date
    FROM "db_prod"."treasury"."cash_call"
    WHERE creation_date >= DATEADD(day, -180, CURRENT_DATE)
    GROUP BY customer_id
),

tx_metrics AS (
    SELECT
        customer_id,
        COUNT(DISTINCT beneficiary_id)    AS unique_beneficiaries_180d,
        COUNT(DISTINCT destiny_country)   AS unique_destiny_countries_180d,
        COUNT(DISTINCT origin_country)    AS unique_origin_countries_180d
    FROM "db_prod"."transaction"."transaction"
    WHERE start_date >= DATEADD(day, -180, CURRENT_DATE)
    GROUP BY customer_id
)

SELECT
    c.customer_id,
    c.email,
    c.country_code,
    c.customer_created_at,
    c.compliance_status,
    c.is_company,

    -- Métricas transaccionales 180d
    cm.trx_180d,
    COALESCE(cm.volume_usd_180d,              0) AS volume_usd_180d,
    COALESCE(cm.avg_ticket_usd_180d,          0) AS avg_ticket_usd_180d,
    COALESCE(cm.max_ticket_usd_180d,          0) AS max_ticket_usd_180d,
    cm.paid_180d,
    cm.rejected_180d,
    COALESCE(cm.rejection_rate_180d,          0) AS rejection_rate_180d,
    COALESCE(cm.unique_external_funders_180d, 0) AS unique_external_funders_180d,
    COALESCE(cm.unique_currencies_180d,       0) AS unique_currencies_180d,
    COALESCE(cm.unique_payment_methods_180d,  0) AS unique_payment_methods_180d,

    -- Métricas de transacciones destino/beneficiario
    COALESCE(tm.unique_beneficiaries_180d,     0) AS unique_beneficiaries_180d,
    COALESCE(tm.unique_destiny_countries_180d, 0) AS unique_destiny_countries_180d,
    COALESCE(tm.unique_origin_countries_180d,  0) AS unique_origin_countries_180d,

    cm.first_operation_date,
    cm.last_operation_date

FROM clientes c
-- Solo clientes activos en 180 días (descarta inactivos sin riesgo transaccional)
INNER JOIN cash_metrics cm
    ON CAST(c.customer_id AS VARCHAR) = CAST(cm.customer_id AS VARCHAR)
LEFT JOIN tx_metrics tm
    ON CAST(c.customer_id AS VARCHAR) = CAST(tm.customer_id AS VARCHAR)

-- Descomentar para pruebas con dataset reducido:
-- ORDER BY cm.volume_usd_180d DESC LIMIT 50000
