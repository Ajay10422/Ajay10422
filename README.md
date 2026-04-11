<!-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->
<!--  AJAY KRISHNA AYYAPPAN · GitHub Profile README         -->
<!-- ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ -->

<div align="center">

```
 █████╗      ██╗ █████╗ ██╗   ██╗    ██╗  ██╗██████╗ ██╗███████╗██╗  ██╗███╗   ██╗ █████╗
██╔══██╗     ██║██╔══██╗╚██╗ ██╔╝    ██║ ██╔╝██╔══██╗██║██╔════╝██║  ██║████╗  ██║██╔══██╗
███████║     ██║███████║ ╚████╔╝     █████╔╝ ██████╔╝██║███████╗███████║██╔██╗ ██║███████║
██╔══██║██   ██║██╔══██║  ╚██╔╝      ██╔═██╗ ██╔══██╗██║╚════██║██╔══██║██║╚██╗██║██╔══██║
██║  ██║╚█████╔╝██║  ██║   ██║       ██║  ██╗██║  ██║██║███████║██║  ██║██║ ╚████║██║  ██║
╚═╝  ╚═╝ ╚════╝ ╚═╝  ╚═╝   ╚═╝       ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝
```

[![Typing SVG](https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=22&pause=1000&color=0078D4&center=true&vCenter=true&width=700&lines=AI+%26+GenAI+Engineer;RAG+Systems+%7C+Multi-Agent+Architectures;Azure+AI+%7C+Python+%7C+Production+LLM+Systems;Building+AI+that+Reasons%2C+Cites%2C+and+Audits)](https://git.io/typing-svg)

<br/>

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/ajay-krishna-952848159)
[![Email](https://img.shields.io/badge/Gmail-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:ajaykrishna10422@gmail.com)
[![Azure AI-102](https://img.shields.io/badge/Azure_AI--102-Exam_Ready-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white)](https://learn.microsoft.com/en-us/credentials/certifications/azure-ai-engineer/)
[![Location](https://img.shields.io/badge/Ontario_Canada-Open_to_Opportunities-00D4A1?style=for-the-badge)](https://github.com/Ajay10422)

</div>

---

## 💡 Who I Am

> **3 years building enterprise data pipelines for Samsung, Google, and Xbox.**
> Then LLMs arrived — and I never looked back.

I build AI systems that don't just retrieve — they **reconcile conflicting information, cite their sources, and explain every decision** with an audit trail.

I come from enterprise data engineering: 5M+ records/day, multi-cloud ETL, Snowflake Medallion Architecture, Kafka streaming. Now I apply those production instincts to **GenAI systems** — RAG pipelines, multi-agent orchestration, and AI governance platforms deployed on Azure and AWS.

|  |  |
|---|---|
| 🏗️ **Built** | Enterprise ETL pipelines · 5M+ records/day · Samsung · Google · Xbox |
| 🧠 **Now** | Production LLM systems · RAG · Multi-Agent AI · Azure AI + AWS |
| 🔨 **Shipped** | AIRES™ — AI governance SaaS (ISO 42001 · NIST AI RMF · EU AI Act) · PolicyIntel RAG |
| 🔜 **Building** | Multi-Agent Customer Support Triage · Invoice Intelligence Pipeline |
| 💬 **Belief** | The best AI doesn't summarise. It reconciles, cites, and audits. |

---

## 🚀 Featured Projects

---

### 🔴 PolicyIntel — Multi-Document Policy RAG Engine

> *"Not just answers — conflict detection with a full audit trail."*

**The problem:** HR and compliance teams manually cross-reference handbooks, insurance policies, and renters coverage. They miss conflicts. Claims get denied.

```
┌──────────────────────────────────────────────────────────────┐
│  ⚠️  CONFLICT DETECTED — Risk Level: HIGH                    │
├──────────────────────────────────────────────────────────────┤
│  📄 Employee Handbook  →  Benefits eligibility from Day 1    │
│  🛡️  Principal Life    →  Requires 30 days active work       │
│                                                              │
│  Impact : Claim denial risk in disputed onboarding period    │
│  Source : Handbook p.12 §3.1  ·  Policy p.47 §8.2.A         │
└──────────────────────────────────────────────────────────────┘
```

**Full Azure AI Stack:**

| Layer | Service | What It Does |
|---|---|---|
| 📦 Storage | Azure Blob Storage | Policy versioning for audit-grade queries |
| 📐 Extraction | Azure Document Intelligence | Layout model preserves page numbers + section headers |
| 🔎 Retrieval | Azure AI Search | BM25 + HNSW vector + Semantic Reranker · 800-token chunks |
| 🧠 Reasoning | Azure OpenAI o4-mini | Strict JSON: `summary · findings · gaps · risk_level · comparison` |
| 🛡️ Guardrails | Azure AI Content Safety | Input + output moderation · fails open by design |
| 🔏 Privacy | Azure AI Language — PII | Redacts SIN, DOB, policy numbers · PIPEDA-compliant |
| 📊 Audit | Application Insights | Every query, conflict, and PII event logged |

**Engineering decisions that matter:**

| Decision | Why It Matters |
|---|---|
| 800-token chunks with 100-token overlap | Larger chunks caused table-of-contents to dominate every result |
| DI quality gate ≥ 150 tokens/page | Falls back to pypdf for scanned/multi-column layouts automatically |
| Content-hash deduplication | Same chunk appeared 5× in top-K results without it |
| `cross_document_comparison` typed as `string` not `anyOf[string, null]` | Forces model to always compare — never returns null |
| Fails open on Content Safety | Missing service never breaks production queries |

**Query Modes:**

| Mode | Sources | Findings | Use Case |
|---|---|---|---|
| ⚡ Fast | 5 | 3 | Quick eligibility checks |
| ⚖️ Balanced | 10 | 5 | Standard compliance queries |
| 🔬 Deep | 20 | 8 | Full audit-grade analysis |

[![Repo](https://img.shields.io/badge/GitHub-PolicyIntel--RAG-181717?style=for-the-badge&logo=github)](https://github.com/Ajay10422/PolicyIntel-RAG)
[![Demo](https://img.shields.io/badge/Demo-Loom_Video-00D4A1?style=for-the-badge)](https://www.loom.com/share/9110ef07fcbb47e2991d8fd50724ef79)

---

### 🟡 Cloud-Native Fuel Efficiency Forecasting — Azure + Snowflake

> *"End-to-end ETL + ML pipeline from raw government data to live predictions in production."*

**The problem:** Canada's EnerGuide fuel consumption data sits in static CSVs. Consumers, manufacturers, and policy teams have no interactive way to forecast carbon tax impact, compare models dynamically, or detect fleet inefficiencies.

```
Government CSVs + Synthetic IoT Stream
         │
         ▼
  Apache Airflow DAGs ──► Azure ADLS Gen2
         │                      │
  Azure Event Hubs ─────────────┘
                                │
                           Snowpipe
                                │
                    ┌──────────────────────┐
                    │   Snowflake DWH       │
                    │  Bronze/Silver/Gold   │
                    └──────────────────────┘
                                │
              ┌─────────────────┴────────────────┐
              │                                  │
        ML Models                          Tableau / Streamlit
   (Ridge · XGBoost)                       (Live Dashboards)
              │
         FastAPI → Render
```

| Component | Technology | Detail |
|---|---|---|
| 🎼 Orchestration | Apache Airflow | DAG-based batch + streaming pipeline |
| ⚡ Streaming | Azure Event Hubs | Synthetic IoT vehicle sensor ingestion |
| 🏔️ Warehouse | Snowflake + Snowpipe | Medallion Architecture — Bronze / Silver / Gold |
| 🤖 ML Models | Ridge · XGBoost via FastAPI | City / Highway / Combined / CO₂ / Smog predictions |
| ☁️ Storage | Azure ADLS Gen2 | Scalable data lake for raw and curated datasets |
| 📊 Dashboard | Streamlit · Tableau | Live monitoring, forecasting, and comparison UI |

**Key results:** `99.5% data integrity` · `Multi-target prediction` (5 fuel/emissions metrics) · `Live at forecasting-fuel-efficiency-4.onrender.com`

[![Repo](https://img.shields.io/badge/GitHub-Forecasting--Fuel--Efficiency-181717?style=for-the-badge&logo=github)](https://github.com/Ajay10422/Forecasting-Fuel-Efficiency)
[![Live Demo](https://img.shields.io/badge/Live_Demo-Render-46E3B7?style=for-the-badge)](https://forecasting-fuel-efficiency-4.onrender.com)

---

### 🔵 Real-Time Event Streaming Pipeline — Kafka + Medallion Architecture

> *"Fault-tolerant streaming ML pipeline with continuous model retraining on data drift."*

```
Raw Events (Kafka / Redpanda)
        │
        ▼
  ┌─────────────────────────────────────────┐
  │         Medallion Architecture           │
  │  🥉 Bronze → 🥈 Silver → 🥇 Gold        │
  │  (raw)      (clean)     (features)       │
  └─────────────────────────────────────────┘
        │                        │
  Drift Detection           ML Retraining
        │                        │
  Streamlit Live Dashboard ◄──────┘
```

| Component | Technology |
|---|---|
| 📡 Streaming | Apache Kafka (Redpanda) |
| ⚙️ Processing | Python · Docker |
| 🏔️ Architecture | Medallion — Bronze / Silver / Gold |
| 🔁 Retraining | Triggered on data drift detection |
| 📊 Monitoring | Streamlit live dashboard |

[![Repo](https://img.shields.io/badge/GitHub-Real--Time--Event--Streaming-181717?style=for-the-badge&logo=github)](https://github.com/Ajay10422/Real-Time-Event-Streaming)

---

### 🟢 Geospatial Intelligence Map — Location Data Platform

> *"Multi-source geospatial fusion built as a foundation for natural-language spatial queries."*

| Component | Technology | Detail |
|---|---|---|
| 🗺️ Mapping | Folium · Leaflet.js | Interactive choropleth + marker clusters |
| ⚙️ Processing | Python · GeoPandas | Multi-source data fusion and normalization |
| 🖥️ Frontend | Streamlit | Responsive UI for non-technical exploration |
| 🔍 Features | Radius search · Dynamic clustering | Location-based filtering at scale |

Built as a foundation for **LLM + geospatial query integration** — ask natural-language questions against location data.

[![Repo](https://img.shields.io/badge/GitHub-Map_Application-181717?style=for-the-badge&logo=github)](https://github.com/Ajay10422/Map_Application)

---

## 🛠️ Technical Stack

### 🤖 AI & GenAI

| Capability | Technologies |
|---|---|
| LLM Orchestration | Azure OpenAI · GPT-4o · GPT-4o-mini · o4-mini · Prompt Engineering |
| RAG Systems | Azure AI Search · Hybrid Search · Semantic Reranking · FAISS · LangChain |
| Document AI | Azure Document Intelligence · Layout Model · Form Recognition |
| Agent Systems | Azure AI Foundry Agent Service · Function Tools · Multi-Agent Orchestration |
| Safety & Governance | Azure AI Content Safety · PII Detection · Key Vault · PIPEDA · ISO 42001 · NIST AI RMF |
| Evaluation | Faithfulness · Relevance scoring · Custom eval pipelines |

### ⚙️ Data Engineering & Backend

| Category | Technologies |
|---|---|
| Languages | Python · SQL · Bash |
| Backend | FastAPI · SQLAlchemy (async) · PostgreSQL · Docker · REST APIs · JWT |
| Cloud — Azure | Blob Storage · ADLS Gen2 · AI Foundry · Key Vault · App Insights · Managed Identity |
| Cloud — AWS | ECS Fargate · RDS · S3 · Lambda · Glue · ALB · WAF · IAM Identity Center |
| Data Engineering | Apache Kafka · Apache Airflow · Snowflake · dbt · PySpark · Azure Data Factory |
| Streaming | Snowpipe · Azure Event Hubs · Redpanda |
| Visualization | Streamlit · Tableau · Power BI · Folium |
| CI/CD | GitHub Actions · Docker · Render |

---

## 💼 Background

| Period | Where | What |
|---|---|---|
| 2026 | **The Bizcom Group Inc.** *(Contract)* | Sole technical consultant — AIRES™ AI governance SaaS on AWS (ECS · RDS · ALB · WAF · IAM) |
| 2020–2023 | **Gameopedia** | Data Operations & Quality Lead · 5M+ records/day · Samsung · Google · Xbox · Azure Data Factory · Airflow · Snowflake · Kafka |
| 2024–2025 | **Durham College, Ontario** | Postgrad Certificate — AI & Data Analytics · GPA **4.56 / 5.0** · Graduated 2025 |
| 2016–2020 | **K Ramakrishnan College of Technology** | B.E. Computer Science Engineering |

---

## 🎯 About AIRES™ — Production AI Governance SaaS

> *Built solo as the sole technical consultant for The Bizcom Group Inc.*

AIRES™ (AI Risk Evaluation System) is a fully deployed AI governance platform aligned with **ISO 42001, NIST AI RMF, EU AI Act, and GDPR**.

```
┌─────────────────────────────────────────────────────────┐
│                   AIRES™ Architecture                    │
├─────────────────────────────────────────────────────────┤
│  Frontend (React + Vite / Nginx)                        │
│       │                                                 │
│  ALB Path Routing ──► /checkout · /webhook · /api/*    │
│       │                                                 │
│  Backend (Node.js / FastAPI)                            │
│       ├── JWT Auth · 30-day sessions · idle timeout     │
│       ├── Cognito user pools (3 role groups)            │
│       ├── RDS PostgreSQL · 5 normalized tables          │
│       └── S3 policy snapshots                           │
│                                                         │
│  AWS Infra: ECS Fargate · ALB · ACM · WAF (SQLi/XSS)  │
│  CI/CD: GitHub Actions → ECR → ECS                     │
└─────────────────────────────────────────────────────────┘
```

**Live:** `aires-risk.com` · **Region:** `ca-central-1`

---

## 📬 Let's Connect

I'm actively looking for **GenAI Engineer / AI Engineer / LLM Engineer** roles in Ontario (open to Toronto hybrid / remote across Canada).

If you're building something interesting with RAG, agents, or AI governance — let's talk.

[![LinkedIn](https://img.shields.io/badge/LinkedIn-Let's_Connect-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/ajay-krishna-952848159)
[![Email](https://img.shields.io/badge/Email-ajaykrishna10422%40gmail.com-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:ajaykrishna10422@gmail.com)

`📍 Oshawa → Toronto · July 2026`

---

<div align="center">

*Building AI that doesn't just answer — it reasons, cites, and audits.*

</div>
