-- Query 1: Base clientes + KYC + empresa
-- Fuente: customer.customer_v2 + customer.kyc_document + company.company
-- Uso: staging_clientes — datos maestros por cliente

WITH kyc_doc AS (
    SELECT
        customer_id,
        document_number,
        document_type,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY created_at DESC
        ) AS rn
    FROM "db_prod"."customer"."kyc_document"
)

SELECT
    cv2.customer_id,
    cv2.email,
    cv2.country_code,
    cv2.created_at AS customer_created_at,
    cv2.compliance_status,
    cv2.onboarding_status,
    kd.document_number,
    kd.document_type,
    c.company_id,
    c.name AS company_name,
    c.identification_number AS company_identification_number,
    c.compliance_status AS company_compliance_status,
    c.risk_level AS company_risk_level,
    c.activity,
    c.ind_activity,
    c.institutional,
    c.legal_representatives_count
FROM "db_prod"."customer"."customer_v2" cv2
LEFT JOIN kyc_doc kd
    ON cv2.customer_id = kd.customer_id
    AND kd.rn = 1
LEFT JOIN "db_prod"."company"."company" c
    ON CAST(cv2.customer_id AS VARCHAR) = CAST(c.company_id AS VARCHAR);
