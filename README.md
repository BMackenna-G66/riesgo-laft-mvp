# Segmentación de Riesgo LA/FT/FPADM — MVP

Pipeline end-to-end de segmentación y scoring de riesgo de Lavado de Activos, Financiamiento del Terrorismo y Financiamiento de la Proliferación de Armas de Destrucción Masiva.

**Propietario:** Compliance / Global66  
**Versión:** 1.0.0  
**Última actualización:** 2026-05-26

---

## Arquitectura

```
Redshift
  ↓  queries/ (5 SQL)
scripts/extract.py         → DataFrames staging
scripts/features.py        → Feature engineering (normalización, outliers, derivadas)
scripts/model_clients.py   → KMeans k=3 → score_cliente 0–1
scripts/score_jurisdictions.py → score_jurisdiccion 0–1
scripts/score_products.py  → score_producto (portfolio ponderado)
scripts/score_channels.py  → score_canal (portfolio ponderado)
scripts/score_final.py     → score_final = 0.40C + 0.30J + 0.15P + 0.15Ca
scripts/validate.py        → validaciones + log
scripts/export.py          → Excel + resumen ejecutivo
```

## Factores de riesgo

| Factor | Método | Peso |
|--------|--------|------|
| Clientes | KMeans estadístico | 40% |
| Jurisdicciones | Tabla país + dispersión geo | 30% |
| Productos | Scoring experto parametrizable | 15% |
| Canales | Scoring experto parametrizable | 15% |

## Niveles de riesgo

| Score | Nivel |
|-------|-------|
| 0.00 – 0.33 | 🟢 Bajo |
| 0.34 – 0.66 | 🟡 Medio |
| 0.67 – 1.00 | 🔴 Alto |

---

## Instalación

```bash
# 1. Clonar y entrar al proyecto
cd riesgo_laft_mvp

# 2. Crear entorno virtual
python3 -m venv .venv
source .venv/bin/activate

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar variables de entorno
cp .env.example .env
# Editar .env con credenciales reales de Redshift
```

## Configuración

Antes de correr, revisar estos archivos:

| Archivo | Qué configura |
|---------|--------------|
| `.env` | Credenciales Redshift |
| `config/parameters.yaml` | Pesos por factor, umbrales riesgo, KMeans k |
| `config/products_risk.yaml` | Score experto por producto |
| `config/channels_risk.yaml` | Score experto por canal |
| `data/country_risk.csv` | Tabla manual riesgo país |

## Ejecución

```bash
# Correr el pipeline completo
cd scripts
python pipeline.py
```

Los resultados quedan en `outputs/`:
- `segmentacion_laft_YYYY-MM-DD_resultados.xlsx` — Excel con 6 pestañas
- `segmentacion_laft_YYYY-MM-DD_resumen_ejecutivo.txt` — Resumen ejecutivo
- `model_centroids.json` — Centroides KMeans para trazabilidad

Los logs quedan en `logs/pipeline_YYYYMMDD_HHMMSS.log`.

## Estructura del proyecto

```
riesgo_laft_mvp/
├── config/
│   ├── parameters.yaml           # pesos, umbrales, versión modelo, KMeans config
│   ├── products_risk.yaml        # scoring manual productos
│   └── channels_risk.yaml        # scoring manual canales
├── data/
│   └── country_risk.csv          # tabla riesgo país (~80 países seed)
├── queries/
│   ├── 01_clientes_kyc.sql       # customer_v2 + kyc_document + company
│   ├── 02_cash_call_metricas.sql # volumen/frecuencia 30/90/180d
│   ├── 03_beneficiarios.sql      # dispersión fondeo y métodos
│   ├── 04_transacciones.sql      # beneficiarios y destinos geográficos
│   └── 05_consolidado.sql        # CTE consolidada principal (query del pipeline)
├── scripts/
│   ├── db.py                     # helper Redshift: get_connection(), query_to_df()
│   ├── extract.py                # capa extracción
│   ├── features.py               # feature engineering
│   ├── model_clients.py          # KMeans + score_cliente
│   ├── score_jurisdictions.py    # score riesgo jurisdicción
│   ├── score_products.py         # score productos
│   ├── score_channels.py         # score canales
│   ├── score_final.py            # score consolidado final
│   ├── validate.py               # validaciones
│   ├── export.py                 # Excel + resumen ejecutivo
│   └── pipeline.py               # ORQUESTADOR — punto de entrada
├── outputs/                      # resultados (.gitignored excepto .gitkeep)
├── logs/                         # logs por corrida (.gitignored excepto .gitkeep)
├── docs/
│   └── metodologia.md            # documentación técnica metodológica
├── .github/workflows/
│   └── run_segmentation.yml      # GitHub Actions (trigger manual + cron lunes)
├── requirements.txt
├── .env.example
└── .gitignore
```

## Outputs del Excel

| Pestaña | Contenido |
|---------|-----------|
| `01_variables_clientes` | Features calculadas por cliente (incluye _norm) |
| `02_resultados_clientes` | cluster, score_cliente, nivel_riesgo_cliente, explicación |
| `03_score_final` | Score consolidado, nivel final, drivers, ordenado por score desc |
| `04_resumen_segmentos` | Distribución Bajo/Medio/Alto con estadísticas |
| `05_productos` | Scoring detallado por producto |
| `06_canales` | Scoring detallado por canal |

## Recalcular el modelo

```bash
python pipeline.py
```

Cada corrida es independiente. Los outputs se nombran con la fecha del día.

## GitHub Actions

El workflow `.github/workflows/run_segmentation.yml` permite:
- **Trigger manual:** desde GitHub → Actions → Run workflow
- **Cron automático:** lunes 06:00 UTC (desactivar si no se necesita)
- Los resultados quedan como **Artifacts** en GitHub por 30 días

### Secrets necesarios en GitHub

| Secret | Descripción |
|--------|-------------|
| `REDSHIFT_HOST` | Host del cluster Redshift |
| `REDSHIFT_PORT` | Puerto (default: 5439) |
| `REDSHIFT_DATABASE` | Base de datos |
| `REDSHIFT_USER` | Usuario |
| `REDSHIFT_PASSWORD` | Contraseña |

## Metodología completa

Ver [docs/metodologia.md](docs/metodologia.md)

## Backlog v2

| Prioridad | Mejora |
|-----------|--------|
| Alta | Score producto/canal por cliente (cruzar con tabla cliente–producto) |
| Alta | Países destino reales en score jurisdicción (Query 04) |
| Media | Incorporar flag PEP / listas restrictivas |
| Media | Modelo supervisado cuando existan etiquetas reales |
| Media | Dashboard de resultados (Streamlit o GitHub Pages) |
| Baja | API REST para scoring en tiempo real |
| Baja | Serie histórica de score por cliente |

---

## Criterios de aceptación del MVP

- [x] El proyecto corre localmente con `python pipeline.py`
- [x] Se conecta a Redshift con credenciales en `.env`
- [x] Calcula variables por cliente (features engineering)
- [x] Ejecuta segmentación KMeans inicial
- [x] Asigna nivel de riesgo (Bajo / Medio / Alto)
- [x] Genera score final ponderado 4 factores
- [x] Exporta resultados en Excel
- [x] Documenta metodología en `docs/metodologia.md`
- [x] Queda versionado en GitHub privado
- [x] Permite recalcular el modelo en cualquier momento
