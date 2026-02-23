# Databricks Apps Workshop

## Workshop Summary

This hands-on workshop demonstrates how to build and deploy secure data and AI applications directly on the Databricks Data Intelligence Platform. Databricks Apps provides serverless hosting with deep integration across Unity Catalog, Databricks SQL, Model Serving, and Lakeflow Jobs—eliminating separate infrastructure while providing built-in governance, identity, and observability.

**Key Benefits:**
- **Simple Development**: Support for Python frameworks (Streamlit, Dash, Gradio) and Node.js; develop locally or in-workspace
- **Built-in Security**: Unity Catalog permissions, managed service principals, OAuth 2.0 SSO, and optional on-behalf-of (OBO) user authorization
- **Production-Ready**: Serverless compute with unique URLs, Git/CI-CD support, and no infrastructure management

**Use Cases Unlocked:**
- Intuitive data explorations with governed access controls
- Secure GenAI chat applications with hosted models
- Operational forms and analytics interfaces
- Model endpoint exposure through secure UIs with consistent governance

---

## Workshop Overview

Participants will complete three progressive demos showcasing different Databricks Apps capabilities:

### Demo 1: PDF Text Extraction with Vision AI
**Framework**: Streamlit  
**Duration**: 15-20 minutes  
**Focus**: Model Serving integration and basic app deployment

Build a PDF text extraction application that:
- Uploads and processes PDF documents using Vision AI
- Integrates with Databricks Model Serving endpoints
- Demonstrates automatic OAuth authentication
- Exports results to CSV, text, or Delta tables

**Key Concepts**: Streamlit development, Model Serving endpoints, SQL Warehouse connectivity, environment variable injection

---

### Demo 2: Support Tickets with Row-Level Security
**Framework**: Dash (Plotly)  
**Duration**: 20-25 minutes  
**Focus**: Transactional workloads with Lakebase and Row-Level Security

Build a support ticket system that:
- Submits and manages tickets with status tracking
- Displays tickets in a kanban board interface
- Enforces PostgreSQL Row-Level Security (RLS) at the database level
- Uses on-behalf-of (OBO) authorization to propagate user identity

**Key Concepts**: Databricks Lakebase (PostgreSQL), Row-Level Security, OBO authorization, CRUD operations

---

### Demo 3: Databricks SQL + Dash with MCP
**Framework**: Dash (Plotly)  
**Duration**: 25-30 minutes  
**Focus**: Direct Databricks SQL integration and AI-assisted development

Build a note-taking application that:
- Connects directly to Databricks SQL using the SQL Connector
- Creates and manages Delta tables with identity columns and timestamps
- Deploys via Databricks Asset Bundles (DABs)
- Uses Model Context Protocol (MCP) for AI-assisted schema modifications

**Key Concepts**: Databricks SQL Connector, Unity Catalog three-level namespace, Delta Lake features, Infrastructure-as-Code with DABs, MCP for AI-assisted development

---

## Prerequisites

- Access to a Databricks workspace with Apps enabled
- Databricks CLI installed and configured
- For Demo 1: A Model Serving endpoint with a vision-capable model
- For Demo 2: On-Behalf-Of User Authorization enabled (workspace admin setting)
- For Demo 3: A SQL Warehouse and Unity Catalog access
- (Optional) AI tool with MCP support for Demo 3 advanced features

---

## Repository Structure

```
databricks-apps-workshop/
├── README.md                          # This file
├── databricks.yml                     # Root Asset Bundle configuration
├── deploy_app_bundle.sh              # Deployment helper script
├── apps/
│   ├── demo1_pdf_extractor_streamlit/
│   │   ├── app.py                    # Streamlit application
│   │   ├── app.yml                   # App-specific configuration
│   │   ├── requirements.txt
│   │   └── WORKSHOP_USER_GUIDE.md   # Step-by-step instructions
│   ├── demo2_support_tickets_dash/
│   │   ├── app.py                    # Dash application
│   │   ├── app.yml
│   │   ├── setup-lakebase.ipynb     # Database setup notebook
│   │   ├── requirements.txt
│   │   └── WORKSHOP_USER_GUIDE.md
│   └── demo3_dash_dbsql/
│       ├── app.py                    # Dash application with SQL Connector
│       ├── app.yml
│       ├── requirements.txt
│       ├── WORKSHOP_USER_GUIDE.md
└── dab/
    └── resources/
        └── apps.yml                   # Asset Bundle app definitions
```

---

## Getting Started

### 1. Clone the Repository

```bash
git clone https://github.com/dbderek/databricks-apps-workshop.git
cd databricks-apps-workshop
```

### 2. Configure Databricks CLI
Install databricks CLI with Homebrew
```bash
brew install databricks
```

Configure the CLI
```bash
databricks configure --profile workshop
```

Follow prompts to enter your workspace URL and authentication.

### 3. Choose Your Demo

Each demo is self-contained with its own `WORKSHOP_USER_GUIDE.md`. Navigate to the demo folder and follow the guide:

- **Demo 1**: [`apps/demo1_pdf_extractor_streamlit/WORKSHOP_USER_GUIDE.md`](apps/demo1_pdf_extractor_streamlit/WORKSHOP_USER_GUIDE.md)
- **Demo 2**: [`apps/demo2_support_tickets_dash/WORKSHOP_USER_GUIDE.md`](apps/demo2_support_tickets_dash/WORKSHOP_USER_GUIDE.md)
- **Demo 3**: [`apps/demo3_dash_dbsql/WORKSHOP_USER_GUIDE.md`](apps/demo3_dash_dbsql/WORKSHOP_USER_GUIDE.md)

### 4. Update Configuration

Before deploying, update the configuration files with your workspace details:
- Root `databricks.yml`: Workspace host URL
- App-specific `app.yml`: Resource IDs (warehouse, endpoints, etc.)

### 5. Deploy

Each demo uses Databricks Asset Bundles for deployment:

```bash
databricks bundle validate -t dev
./deploy_app_bundle.sh dev
```

---

## Workshop Flow

**Recommended Order**: Complete demos sequentially (1 → 2 → 3)

- **Demo 1** introduces core concepts: app deployment, authentication, and Model Serving integration
- **Demo 2** adds complexity with transactional databases, RLS, and OBO authorization
- **Demo 3** demonstrates advanced patterns: direct SQL integration, Infrastructure-as-Code, and AI-assisted development

**Total Time**: 60-75 minutes for all three demos

---

## Resources

- [Databricks Apps Documentation](https://docs.databricks.com/en/apps/index.html)
- [Databricks Asset Bundles Guide](https://docs.databricks.com/en/dev-tools/bundles/index.html)
- [Unity Catalog Overview](https://docs.databricks.com/en/data-governance/unity-catalog/index.html)
- [Model Context Protocol (MCP)](https://modelcontextprotocol.io/)

---

## Support

For questions or issues during the workshop:
1. Check the `WORKSHOP_USER_GUIDE.md` troubleshooting sections
2. Review the Databricks Apps documentation
3. Contact your workshop facilitator

---

## License

This workshop content is provided for educational purposes.
