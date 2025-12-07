# NDA Tool Lite

A simple, local Electron desktop application for managing and analyzing NDAs and Agreements using GPT-4o.

## Features

- **Document Management**: Drag and drop PDF/DOCX files. Organize by type (NDA, Supplier Agreement).
- **Automated Analysis**: Automatically extracts key information (Parties, Expiration, Jurisdiction) using GPT-4o based on configurable competency questions.
- **Dashboard**: View high-level metrics and expiration warnings.
- **Chat**: Chat with your documents to answer specific questions.
- **Configurable**: Define new document types and questions in `config.yaml`.
- **Local & Secure**: Documents stay on your local machine (except for processing by OpenAI).

## Architecture

- **Frontend**: Electron + React + TailwindCSS
- **Backend**: Python (FastAPI/FastMCP) running locally as a subprocess
- **Storage**: Local filesystem (`documents/` folder and `documents/metadata.json`)

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

## Configuration

Edit `config.yaml` to change document types or competency questions.

## Legacy

The original Docker-based microservices version has been archived to the `legacy_v1/` directory for reference.

