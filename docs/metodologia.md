# Documentación Técnica — Metodología de Segmentación LA/FT/FPADM

**Versión:** 1.0.0  
**Fecha:** 2026-05-26  
**Propietario:** Compliance / Global66

---

## 1. Marco metodológico

El modelo implementa la metodología de **segmentación de factores de riesgo LA/FT/FPADM** basada en 4 factores de riesgo estructurales:

| Factor | Método | Peso inicial |
|--------|--------|-------------|
| Clientes | Segmentación estadística (KMeans) | 40% |
| Jurisdicciones | Tabla parametrizable + dispersión geográfica | 30% |
| Productos | Scoring ponderado / juicio experto | 15% |
| Canales | Scoring ponderado / juicio experto | 15% |

**Los pesos son configurables** en `config/parameters.yaml` sin modificar código.

---

## 2. Factor 1 — Clientes

### 2.1 Fuente de datos

- `customer.customer_v2` — datos maestros del cliente
- `customer.kyc_document` — documento de identidad más reciente
- `company.company` — datos de empresa B2B
- `treasury.cash_call` — métricas de operaciones (ventana 180 días)
- `transaction.transaction` — beneficiarios y destinos geográficos (ventana 180 días)

### 2.2 Variables usadas en el modelo

| Variable | Descripción | Tipo |
|----------|-------------|------|
| `trx_180d` | Cantidad de operaciones en 180 días | Cuantitativa |
| `volume_usd_180d` | Volumen total USD en 180 días | Cuantitativa |
| `avg_ticket_usd_180d` | Ticket promedio USD | Cuantitativa |
| `max_ticket_usd_180d` | Ticket máximo USD | Cuantitativa |
| `rejection_rate_180d` | Porcentaje de rechazo | Cuantitativa |
| `unique_external_funders_180d` | Fondos externos distintos | Cuantitativa |
| `unique_beneficiaries_180d` | Beneficiarios únicos | Cuantitativa |
| `unique_destiny_countries_180d` | Países destino únicos | Cuantitativa |
| `unique_currencies_180d` | Monedas distintas | Cuantitativa |
| `unique_payment_methods_180d` | Métodos de pago distintos | Cuantitativa |
| `customer_age_days` | Antigüedad del cliente (variable derivada) | Cuantitativa |
| `compliance_risk_flag` | Flag revisión compliance (variable derivada) | Binaria |

### 2.3 Tratamiento de datos

1. **Nulos:** valores numéricos → 0; categóricos → `"UNKNOWN"`
2. **Outliers:** tope por IQR × factor (configurable, default = 3.0)
3. **Normalización:** min-max al rango [0, 1] por variable
4. **Estandarización:** StandardScaler antes del KMeans (media 0, desviación 1)

### 2.4 Modelo KMeans

- **Algoritmo:** KMeans
- **k:** 3 (configurable en `parameters.yaml`)
- **Semilla:** 42 (reproducibilidad)
- **Asignación de niveles:** los clusters se ordenan por score compuesto de centroide (promedio de features normalizadas). El cluster de menor score → Bajo; el de mayor score → Alto.

### 2.5 Score de cliente

```
score_cliente = f(cluster, distancia_al_centroide_alto_riesgo)
- Cluster Alto:  score ∈ [0.67, 1.00]
- Cluster Medio: score ∈ [0.34, 0.66]
- Cluster Bajo:  score ∈ [0.00, 0.33]
```

### 2.6 Trazabilidad

- Centroides guardados en `outputs/model_centroids.json`
- Cada resultado incluye `cluster_id`, `cluster_label`, `principales_features`, `dist_centroide_alto`, `fecha_modelo`, `version_modelo`

---

## 3. Factor 2 — Jurisdicciones

### 3.1 Fuente de datos

- `data/country_risk.csv` — tabla manual parametrizable
- `unique_destiny_countries_180d` — proxy de dispersión geográfica del cliente

### 3.2 Columnas de la tabla país

| Columna | Descripción |
|---------|-------------|
| `country_code` | Código ISO 3166-1 alpha-2 |
| `fatf_flag` | 1 si está en lista GAFI/FATF de jurisdicciones de alto riesgo |
| `sanctions_flag` | 1 si tiene sanciones internacionales vigentes |
| `corruption_score` | Índice de percepción de corrupción (0=bajo, 1=alto) |
| `basel_index` | Índice de riesgo AML de Basel (0=bajo, 1=alto) |
| `manual_risk_score` | Score manual del equipo de Compliance |
| `final_country_risk` | Score final del país [0,1] |

### 3.3 Cálculo del score jurisdicción

```
score_jurisdiccion = 0.50 × score_pais_origen + 0.50 × dest_diversity_norm
```

- `score_pais_origen`: `final_country_risk` del país de registro del cliente
- `dest_diversity_norm`: `unique_destiny_countries / max_unique_destiny_countries`

> **Nota de extensión:** cuando se integre la lista de países destino por transacción (query 04), se puede calcular el máximo `final_country_risk` entre los países destino reales del cliente, reemplazando el proxy de diversidad.

---

## 4. Factor 3 — Productos

### 4.1 Fuente de datos

- `config/products_risk.yaml` — tabla parametrizable de scoring

### 4.2 Cálculo MVP

```
score_producto_portfolio = Σ(score_experto_i × ponderacion_i) / Σ(ponderacion_i)
```

Score único por MVP (mismo para todos los clientes). Se extiende a nivel cliente cuando exista tabla cliente–producto.

---

## 5. Factor 4 — Canales

### 5.1 Fuente de datos

- `config/channels_risk.yaml` — tabla parametrizable de scoring

### 5.2 Cálculo MVP

```
score_canal_portfolio = Σ(score_experto_i × ponderacion_i) / Σ(ponderacion_i)
```

Score único por MVP. Se extiende cuando exista tabla cliente–canal.

---

## 6. Score final consolidado

```
score_final = score_cliente      × 0.40
            + score_jurisdiccion × 0.30
            + score_producto     × 0.15
            + score_canal        × 0.15
```

### Clasificación de riesgo

| Rango | Nivel |
|-------|-------|
| 0.00 – 0.33 | Bajo |
| 0.34 – 0.66 | Medio |
| 0.67 – 1.00 | Alto |

---

## 7. Outputs generados

| Archivo | Descripción |
|---------|-------------|
| `outputs/segmentacion_laft_YYYY-MM-DD_resultados.xlsx` | Excel 6 pestañas |
| `outputs/segmentacion_laft_YYYY-MM-DD_resumen_ejecutivo.txt` | Resumen ejecutivo |
| `outputs/model_centroids.json` | Centroides KMeans para trazabilidad |
| `logs/pipeline_YYYYMMDD_HHMMSS.log` | Log completo de la corrida |

---

## 8. Actualización periódica

El pipeline está diseñado para recalcularse completamente en cada ejecución:
- No hay estado persistente entre corridas (excepto centroides para referencia)
- Se puede programar via GitHub Actions (`.github/workflows/run_segmentation.yml`)
- Para recalibrar los pesos, modificar `config/parameters.yaml`
- Para actualizar scores expertos de productos/canales, modificar los YAML correspondientes
- Para actualizar la tabla de riesgo país, reemplazar `data/country_risk.csv`

---

## 9. Backlog de mejoras (v2+)

| Prioridad | Mejora | Descripción |
|-----------|--------|-------------|
| Alta | Score producto por cliente | Cruzar con tabla cliente–producto para score individual |
| Alta | Score canal por cliente | Cruzar con tabla cliente–canal para score individual |
| Alta | Países destino reales | Reemplazar proxy de diversidad por máximo riesgo real de países destino |
| Alta | Ventanas 30d y 90d | Activar scoring en ventanas más cortas para tendencia |
| Media | PEP / listas restrictivas | Incorporar flag PEP desde API externa (Nosis u otra) |
| Media | Modelo supervisado | Migrar de KMeans a modelo supervisado cuando haya etiquetas reales |
| Media | API REST | Exponer el pipeline como endpoint para scoring en tiempo real |
| Media | Dashboard | Dashboard interactivo (Streamlit o GitHub Pages) para visualizar distribución |
| Baja | Alertas automáticas | Notificación cuando un cliente sube de Bajo a Alto |
| Baja | Score histórico | Mantener serie de tiempo de score por cliente para detectar tendencias |

---

## 10. Glosario

| Término | Definición |
|---------|------------|
| LA/FT/FPADM | Lavado de Activos / Financiamiento del Terrorismo / Financiamiento de la Proliferación de Armas de Destrucción Masiva |
| FATF/GAFI | Financial Action Task Force — lista de jurisdicciones de alto riesgo |
| KYC | Know Your Customer — proceso de debida diligencia de clientes |
| PEP | Persona Expuesta Políticamente |
| KMeans | Algoritmo de clustering no supervisado que agrupa datos en k clusters |
| Score compuesto | Promedio de las variables normalizadas de un centroide |
| Centroide | Punto central de un cluster en el espacio de features |
