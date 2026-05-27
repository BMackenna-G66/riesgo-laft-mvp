-- Query 5: Consolidada principal — alimenta directamente el pipeline MVP
-- Fuente: compliance.bbdd_clientes + compliance.bbdd_delitos + compliance.alerts
-- Uso: staging principal → features → modelo

WITH clientes_raw AS (
    SELECT
        customer_id,
        CAST(rut AS VARCHAR) AS rut,
        compliance_status,
        UPPER(TRIM(risk_level))  AS risk_level_raw,
        COALESCE(total_delitos, 0) AS total_delitos,
        CASE WHEN UPPER(TRIM(con_info)) = 'SI' THEN 1 ELSE 0 END AS con_info,
        grupo,
        -- Desduplicar por customer_id: conservar el registro con mayor riesgo
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY
                CASE UPPER(TRIM(risk_level))
                    WHEN 'ALTO' THEN 1
                    WHEN 'MEDIO' THEN 2
                    WHEN 'BAJO'  THEN 3
                    ELSE 4
                END ASC,
                loaded_at DESC
        ) AS rn
    FROM compliance.bbdd_clientes
    WHERE customer_id IS NOT NULL
),

clientes AS (
    SELECT customer_id, rut, compliance_status, risk_level_raw,
           total_delitos, con_info, grupo
    FROM clientes_raw
    WHERE rn = 1
),

delitos_agg AS (
    SELECT
        customer_id,
        COUNT(*)                                                         AS delitos_count,
        COUNT(CASE WHEN LOWER(riesgo) = 'high'   THEN 1 END)            AS high_crimes,
        COUNT(CASE WHEN LOWER(riesgo) = 'medium' THEN 1 END)            AS medium_crimes,
        COUNT(CASE WHEN LOWER(riesgo) = 'low'    THEN 1 END)            AS low_crimes,
        COUNT(DISTINCT crimen)                                           AS crime_type_diversity,
        COUNT(CASE WHEN LOWER(estado) NOT LIKE '%concluida%' THEN 1 END) AS active_crimes,
        MIN(fecha)                                                       AS first_crime_date,
        MAX(fecha)                                                       AS last_crime_date
    FROM compliance.bbdd_delitos
    WHERE customer_id IS NOT NULL
    GROUP BY 1
),

alerts_agg AS (
    SELECT
        CAST(entity_value AS INTEGER) AS customer_id,
        COUNT(*)                      AS alert_count,
        1                             AS has_alerts
    FROM compliance.alerts
    WHERE entity_field = 'customer_id'
      AND status       = 'active'
    GROUP BY 1
)

SELECT
    c.customer_id,
    c.rut,
    c.compliance_status,
    c.risk_level_raw,
    c.total_delitos,
    c.con_info,
    c.grupo,

    -- Delitos agregados
    COALESCE(d.delitos_count,        0) AS delitos_count,
    COALESCE(d.high_crimes,          0) AS high_crimes,
    COALESCE(d.medium_crimes,        0) AS medium_crimes,
    COALESCE(d.low_crimes,           0) AS low_crimes,
    COALESCE(d.crime_type_diversity, 0) AS crime_type_diversity,
    COALESCE(d.active_crimes,        0) AS active_crimes,
    d.first_crime_date,
    d.last_crime_date,

    -- Alertas
    COALESCE(a.alert_count, 0) AS alert_count,
    COALESCE(a.has_alerts,  0) AS has_alerts,

    -- Flags de compliance derivados
    CASE WHEN c.compliance_status IN ('BLOCKED','FULLY_BLOCKED') THEN 1 ELSE 0 END AS is_blocked,
    CASE WHEN c.compliance_status LIKE 'UNDER_COMPLIANCE_REVIEW%'  THEN 1 ELSE 0 END AS under_review,
    CASE WHEN c.compliance_status = 'WARNING'                       THEN 1 ELSE 0 END AS has_warning,

    CURRENT_TIMESTAMP AS extracted_at

FROM clientes c
LEFT JOIN delitos_agg d USING (customer_id)
LEFT JOIN alerts_agg  a USING (customer_id)
