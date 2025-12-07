# DocuSenseLM

**DocuSenseLM** is a lightweight, local desktop application designed to make legal and business document management intelligent and private. By combining a secure local storage architecture with GPT-4o integration, it provides automated analysis, key data extraction, and chat capabilities for any document type—from NDAs to Supplier Agreements.

## Why DocuSenseLM?

- **Privacy First**: Your documents stay on your local machine. Only text excerpts are sent to OpenAI for processing, and only when you choose to analyze them.
- **Intelligent Extraction**: Don't just store files; understand them. Automatically extract expiration dates, party names, and jurisdictions.
- **Flexible**: It's not just for NDAs. Configure any document type and set your own "Competency Questions" to extract the data that matters to you.

## Features

- **Drag-and-Drop Management**: Easily organize PDF and DOCX files.
- **AI Analysis**: Automated extraction of critical metadata using GPT-4o.
- **Chat with Documents**: Ask questions across your entire document library.
- **Dashboard**: Track expirations and workflow statuses at a glance.
- **Configurable**: Define custom document types and questions in `config.yaml`.
- **Branding**: Fully white-label ready via environment variables.

## Architecture

- **Frontend**: Electron + React + TailwindCSS for a modern, responsive UI.
- **Backend**: Python (FastAPI/FastMCP) running locally as a subprocess for robust logic.
- **Storage**: Local filesystem (`documents/` folder and `documents/metadata.json`) for zero-dependency data management.

## Setup

1. **Install Dependencies**
   ```bash
   npm install
   ```

2. **Setup Python Environment**
   ```bash
   cd python
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   ```

3. **Configure OpenAI**
   Copy `.env.example` to `.env` and add your API key:
   ```bash
   cp .env.example .env
   ```
   Edit `.env` with your `OPENAI_API_KEY`.

4. **Run Development Mode**
   ```bash
   npm run electron:dev
   ```

## Branding & White-Labeling

DocuSenseLM is designed to be easily rebranded for your organization. You can customize the application name and window title by setting environment variables in your `.env` file:

```bash
VITE_APP_TITLE="My Law Firm Analyzer"
APP_NAME="My Law Firm Analyzer"
```

The application icon can be customized by replacing the `build/icon.png` file before building.

## Configuration

Edit `config.yaml` to define your own document types (e.g., Employment Contracts, Leases) and the specific questions you want the AI to answer for each.

## Legacy

The original Docker-based microservices version has been archived to the `legacy_v1/` directory for reference.

