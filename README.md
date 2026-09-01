<div align="center">
  <img src="./frontend/public/logo_no_background.png" alt="PCBGPT Logo" width="200" />
  <h1>PCBGPT</h1>
  <p><strong>AI-Powered PCB Design Assistant</strong></p>
  <p>Generate KiCad schematics from natural language descriptions</p>

[![Frontend Docker Build](https://github.com/tk-king/pcbGPT/actions/workflows/build-docker-frontend.yml/badge.svg?branch=refactor%2Foss)](https://github.com/tk-king/pcbGPT/actions/workflows/build-docker-frontend.yml)
[![Backend Docker Build](https://github.com/tk-king/pcbGPT/actions/workflows/build-docker-backend.yml/badge.svg?branch=refactor%2Foss)](https://github.com/tk-king/pcbGPT/actions/workflows/build-docker-backend.yml)
[![Desktop App Build](https://github.com/tk-king/pcbGPT/actions/workflows/build-desktop.yml/badge.svg?branch=refactor%2Foss)](https://github.com/tk-king/pcbGPT/actions/workflows/build-desktop.yml)
</div>

## ✨ Features

- 🔍 **Component search** from indexed KiCad libraries
- 📋 **Datasheet analysis** to extract reference circuits and pin configs
- ⚡ **Circuit generation** with correct connections and values
- ✅ **LLM-driven validation loop** that checks the design, then iterates on fixes
- 📤 **KiCad export** — schematics, netlists, and PDF docs
- 💬 **Modern web UI** with real-time streaming chat and tool tracking

## 🚀 Quick Start

### Requirements

- Python 3.11+
- Node.js 22+
- KiCad, including `kicad-cli`
- An OpenAI-compatible model provider

### Docker (recommended)

```bash
git clone https://github.com/tk-king/pcbGPT.git
cd pcbGPT
docker compose up --build
```

- **Frontend:** http://localhost:5173
- **Backend API:** http://localhost:8000 (docs at `/docs`)

### Local development

Install the backend dependencies:

```bash
cd backend
uv sync --extra dev
```

Start the FastAPI backend:

```bash
uv run python main.py
```

In a second terminal, start the frontend:

```bash
cd frontend
npm ci
npm run dev
```

### Component data

`Datasets/` and `datasheets/` contain local runtime data and are excluded from Git. After configuring your KiCad paths in the **Parts** screen, use **Parts → Reindex** to build the component search indexes. Datasheet PDFs and page-preview caches are downloaded as needed.

Configure an LLM provider from the **Settings** screen. Never commit API keys or real provider credentials.

### Desktop app (prebuilt)

Download the latest prebuilt desktop app from the [releases](https://github.com/tk-king/pcbGPT/releases/latest):

- 🪟 **Windows:** [PCBGPT.exe](https://github.com/tk-king/pcbGPT/releases/latest/download/PCBGPT.exe)
- 🍎 **macOS:** [pcbGPT-macos.dmg](https://github.com/tk-king/pcbGPT/releases/latest/download/pcbGPT-macos.dmg)

## 📖 Usage

1. **Configure a provider** — open Settings (gear icon) and add your LLM API key + models.
2. **Index parts** — click **Parts**, configure the KiCad library paths, and run **Reindex**.
3. **Describe a circuit** — start a session and type a prompt, e.g.:

   ```
   Design a buck converter that converts 12V to 3.3V at up to 1A.
   Use a TI TPS5430 and include input/output filtering.
   ```

4. **Review & export** — the agent searches parts, reads datasheets, generates and validates the circuit, then exports KiCad project files. Download the **Netlist** (SPICE) or **Project** (full KiCad files).

Generated designs must be reviewed by a qualified engineer before fabrication or use in safety-critical systems.

## 📬 Contact

- **Issues:** [GitHub Issues](https://github.com/tk-king/pcbGPT/issues)
- **Discussions:** [GitHub Discussions](https://github.com/tk-king/pcbGPT/discussions)
