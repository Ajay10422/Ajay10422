<div align="center">

```
 █████╗      ██╗ █████╗ ██╗   ██╗    ██╗  ██╗██████╗ ██╗███████╗██╗  ██╗███╗   ██╗ █████╗
██╔══██╗     ██║██╔══██╗╚██╗ ██╔╝    ██║ ██╔╝██╔══██╗██║██╔════╝██║  ██║████╗  ██║██╔══██╗
███████║     ██║███████║ ╚████╔╝     █████╔╝ ██████╔╝██║███████╗███████║██╔██╗ ██║███████║
██╔══██║██   ██║██╔══██║  ╚██╔╝      ██╔═██╗ ██╔══██╗██║╚════██║██╔══██║██║╚██╗██║██╔══██║
██║  ██║╚█████╔╝██║  ██║   ██║       ██║  ██╗██║  ██║██║███████║██║  ██║██║ ╚████║██║  ██║
╚═╝  ╚═╝ ╚════╝ ╚═╝  ╚═╝   ╚═╝       ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝╚══════╝╚═╝  ╚═╝╚═╝  ╚═══╝╚═╝  ╚═╝
```

<img src="https://readme-typing-svg.demolab.com?font=Fira+Code&weight=600&size=22&pause=1000&color=0078D4&center=true&vCenter=true&width=700&lines=AI+%26+GenAI+Engineer;RAG+Systems+%7C+Multi-Agent+Architectures;Azure+AI+%7C+Python+%7C+Production+LLM+Systems;Building+AI+that+Reasons%2C+Not+Just+Retrieves" alt="Typing SVG" />

<br/>

[![LinkedIn](https://img.shields.io/badge/LinkedIn-0A66C2?style=for-the-badge&logo=linkedin&logoColor=white)](https://www.linkedin.com/in/ajay-krishna-952848159)
[![Email](https://img.shields.io/badge/Gmail-EA4335?style=for-the-badge&logo=gmail&logoColor=white)](mailto:ajaykrishna10422@gmail.com)
[![Azure AI-102](https://img.shields.io/badge/Azure_AI--102-Exam_Ready-0078D4?style=for-the-badge&logo=microsoft-azure&logoColor=white)](https://learn.microsoft.com/en-us/credentials/certifications/azure-ai-engineer/)
![Ontario](https://img.shields.io/badge/Ontario_Canada-Open_to_Opportunities-00D4A1?style=for-the-badge)

</div>

---

<div align="center">

### 💡 I engineer AI systems that **reason across documents**, **detect conflicts**, and **explain their decisions** — not just chatbots that summarise text.

</div>

---

## 🧬 Who I Am

> 3 years building enterprise data pipelines for Samsung, Google, and Xbox.
> Then LLMs arrived — and I never looked back.
>
> I build AI systems that don't just retrieve — they reconcile conflicting information,
> cite their sources, and explain every decision with an audit trail.

| | |
|---|---|
| 🏗️ **Built** | Enterprise pipelines · 5M+ records/day · Samsung · Google · Xbox |
| 🧠 **Now** | Production LLM systems · RAG · Multi-Agent AI · Azure AI Stack |
| 🔨 **Building** | PolicyIntel — compliance RAG that detects conflicts across policy documents |
| 🔜 **Next** | Multi-Agent Triage · Invoice Intelligence Pipeline |
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
|-------|---------|-------------|
| 📦 Storage | Azure Blob Storage + Versioning | Query March vs June policy — critical for claims audits |
| 📐 Extraction | Azure Document Intelligence | Layout model preserves page numbers + section headers |
| 🔎 Retrieval | Azure AI Search | BM25 + HNSW vector + Semantic Reranker · 800-token chunks |
| 🧠 Reasoning | Azure OpenAI o4-mini | Strict JSON: `summary · findings · gaps · risk_level · comparison` |
| 🛡️ Guardrails | Azure AI Content Safety | Input + output moderation · fails open by design |
| 🔏 Privacy | Azure AI Language — PII | Redacts SIN, DOB, policy numbers · PIPEDA-compliant |
| 🔑 Secrets | Azure Key Vault + Managed Identity | Zero hardcoded credentials anywhere |
| 📊 Audit | Application Insights | Every query, conflict, and PII event logged |

**Engineering decisions that matter:**

| Decision | Why It Matters |
|----------|---------------|
| 800-token chunks with 100-token overlap | Larger chunks caused table-of-contents to dominate every result |
| DI quality gate ≥ 150 tokens/page | Falls back to pypdf for scanned/multi-column layouts automatically |
| Content-hash deduplication | Same chunk appeared 5× in top-K results without it |
| `cross_document_comparison` typed as `string` not `anyOf[string, null]` | Forces model to always compare — never returns null |
| Fails open on Content Safety | Missing service never breaks production queries |

**Query Modes:**

| Mode | Sources | Findings | Use Case |
|------|---------|----------|----------|
| ⚡ Fast | 5 | 3 | Quick eligibility checks |
| ⚖️ Balanced | 10 | 5 | Standard compliance queries |
| 🔬 Deep | 20 | 8 | Full audit-grade analysis |

[![PolicyIntel](https://img.shields.io/badge/GitHub-PolicyIntel-181717?style=for-the-badge&logo=github)](https://github.com/Ajay10422/policyintel)

---

### 🟡 Cloud-Native Fuel Efficiency Forecasting — AWS

> *"End-to-end ML pipeline from raw sensor data to <200ms predictions in production."*

| Component | Technology | Detail |
|-----------|------------|--------|
| 🎼 Orchestration | Apache Airflow | DAG-based batch + streaming pipeline |
| ⚡ Streaming | Azure Event Hubs | Real-time vehicle sensor ingestion |
| 🏔️ Warehouse | Snowflake | Medallion Architecture — Bronze / Silver / Gold |
| 🤖 ML Model | XGBoost via FastAPI | <200ms prediction latency in production |
| ☁️ Cloud | AWS S3 · Lambda · Glue | Serverless processing and storage |
| 📊 Dashboard | Streamlit · Tableau | Live monitoring and forecasting UI |

**Key results:** `99.5% data integrity` · `<200ms latency` · `25% reduction in manual processing`

[![Fuel Forecasting](https://img.shields.io/badge/GitHub-Fuel_Forecasting-181717?style=for-the-badge&logo=github)](https://github.com/Ajay10422/Forecasting-Fuel-Efficiency)

---

### 🟢 Geospatial Intelligence Map — Location Data Platform

> *"Multi-source geospatial data fused into an interactive, queryable map layer."*

| Component | Technology | Detail |
|-----------|------------|--------|
| 🗺️ Mapping Engine | Folium · Leaflet.js | Interactive choropleth + marker clusters |
| ⚙️ Processing | Python · Pandas · GeoPandas | Multi-source data fusion and normalization |
| 🖥️ Frontend | Streamlit | Responsive UI for non-technical data exploration |
| 🔍 Features | Radius search · Dynamic clustering | Location-based filtering at scale |

Built as a foundation for **LLM + geospatial query integration** — ask natural language questions against location data.

[![Map App](https://img.shields.io/badge/GitHub-Map_Application-181717?style=for-the-badge&logo=github)](https://github.com/Ajay10422/Map_Application)

---

### 🔵 Real-Time Event Streaming Pipeline

> *"Fault-tolerant Kafka pipeline with continuous model retraining on data drift."*

| Component | Technology |
|-----------|------------|
| 📡 Streaming | Apache Kafka (Redpanda) |
| ⚙️ Processing | Python · Docker |
| 🏔️ Architecture | Medallion — Bronze / Silver / Gold |
| 📊 Monitoring | Streamlit live dashboard |

[![Streaming](https://img.shields.io/badge/GitHub-Event_Streaming-181717?style=for-the-badge&logo=github)](https://github.com/Ajay10422/Real-Time-Event-Streaming)

---

## 🛠 Technical Stack

### 🤖 AI & GenAI

| Capability | Technologies |
|------------|-------------|
| LLM Orchestration | Azure OpenAI · gpt-4o · gpt-4o-mini · o4-mini · Prompt Engineering |
| RAG Systems | Azure AI Search · Hybrid Search · Semantic Reranking · FAISS · LangChain |
| Document AI | Azure Document Intelligence · Layout Model · Form Recognition |
| Agent Systems | Azure AI Foundry Agent Service · Function Tools · Multi-Agent Orchestration |
| Safety & Governance | Azure AI Content Safety · PII Detection · Key Vault · PIPEDA compliance |
| Evaluation | Faithfulness · Relevance scoring · Custom eval pipelines · CSV output |

### ⚙️ Engineering

| Category | Technologies |
|----------|-------------|
| Languages | Python · SQL · Bash |
| Backend | FastAPI · SQLAlchemy · PostgreSQL · Docker |
| Cloud — Azure | Blob Storage · AI Foundry · Key Vault · App Insights · Managed Identity |
| Cloud — AWS | ECS Fargate · RDS · S3 · Lambda · Glue · ALB · WAF |
| Data Engineering | Apache Kafka · Apache Airflow · Snowflake · dbt · PySpark |
| Frontend / Viz | Streamlit · Folium · Tableau · Power BI |

---

## 💼 Background

| Period | Where | What |
|--------|-------|------|
| 2026 | The Bizcom Group Inc. *(Contract)* | Built AI governance SaaS — production AWS deployment |
| 2020–2023 | Gameopedia | Data Operations Lead · 5M+ records/day · Samsung · Google · Xbox |
| 2024–2025 | Durham College, Ontario | AI & Data Analytics · Postgraduate Certificate · GPA **4.56** |

<div align="center">

**Targeting** `GenAI Engineer` · `AI Engineer` · `LLM Engineer` · `Applied AI Engineer` **roles in Ontario**

*Building AI that doesn't just answer — it reasons, cites, and audits.*

</div>
