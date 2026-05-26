-- Query 3: Beneficiarios / terceros / dispersión desde treasury.cash_call
-- Fuente: treasury.cash_call
-- Uso: staging_beneficiarios — diversificación de fondeo, monedas, métodos

SELECT
    customer_id,

    COUNT(DISTINCT persona_DNI) AS unique_external_funders_180d,
    COUNT(DISTINCT remitter_Dni) AS unique_internal_remitters_180d,

    COUNT(DISTINCT currency_code) AS unique_currencies_180d,
    COUNT(DISTINCT payment_method) AS unique_payment_methods_180d,

    MAX(destiny_amount_usd) AS max_amount_usd_180d,
    SUM(destiny_amount_usd) AS total_amount_usd_180d,

    COUNT(*) AS total_cash_calls_180d

FROM "db_prod"."treasury"."cash_call"
WHERE creation_date >= DATEADD(day, -180, CURRENT_DATE)
GROUP BY customer_id;
