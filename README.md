# biosamples-mcp

A Model Context Protocol (MCP) server for biological sample
checklist validation and recommendation.

Built as part of GSoC 2026 proposal preparation for EMBL-EBI
(Project: Expose BioSamples Submission and Search Capabilities
as MCP Tools for AI-Assisted Metadata Interaction).

---

## What it does

Exposes 3 MCP tools that an LLM (e.g. Claude) can call:

| Tool                  | Description                                                                                            |
| --------------------- | ------------------------------------------------------------------------------------------------------ |
| `validate_sample`     | Validates sample metadata against a specific ENA checklist via BioValidator API                        |
| `get_checklist_info`  | Returns all mandatory and optional fields for a given checklist ID                                     |
| `recommend_checklist` | Scores sample metadata against 15 checklists and returns ranked recommendations with confidence scores |

---

## Architecture

```
LLM / MCP Client
      ↓  MCP protocol (stdio)
  server.py  ←  your MCP server
      ↓
  ┌─────────────────────────────────┐
  │ Tool 1: validate_sample         │──→ BioValidator API
  │ Tool 2: get_checklist_info      │──→ ENA Browser XML API
  │ Tool 3: recommend_checklist     │──→ ENA Browser XML API (x15)
  └─────────────────────────────────┘
```

---

## Key findings from API research

- **BioValidator** (`/biosamples/validate`) validates JSON structure
  but does not enforce checklist mandatory fields — the MCP server's
  scoring engine fills this gap independently
- **ENA Browser XML API** (`/ena/browser/api/xml/{id}`) is the
  reliable public source for checklist field definitions
- **BioSamples JSON Schema Store** (internal MongoDB) is not publicly
  accessible — flagged as a risk in the GSoC proposal with ENA XML
  as a confirmed working alternative
- Validation errors return as structured `{dataPath, errors}` arrays
  — machine-parseable and LLM-friendly

---

## Setup

```bash
git clone https://github.com/rithvik318/biosamples-mcp
cd biosamples-mcp
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # Mac/Linux
pip install -r requirements.txt
```

---

## Run

```bash
python server.py
```

---

## Test with MCP Inspector

```bash
npx @modelcontextprotocol/inspector python D:\biosamples-mcp\server.py
```

Open `http://localhost:6274` and connect using:

- Command: `D:\biosamples-mcp\venv\Scripts\python.exe`
- Arguments: `D:\biosamples-mcp\server.py`

---

## Example tool calls

**validate_sample**

```json
{
  "sample_name": "soil sample from Delhi",
  "characteristics": "{\"organism\": [{\"text\": \"soil metagenome\"}], \"collection_date\": [{\"text\": \"2024-01-01\"}], \"geographic_location_country_andor_sea\": [{\"text\": \"India\"}]}",
  "checklist_id": "ERC000011"
}
```

**recommend_checklist**

```json
{
  "sample_name": "soil metagenome sample",
  "characteristics": "{\"organism\": [{\"text\": \"soil metagenome\"}], \"collection_date\": [{\"text\": \"2024-01-01\"}]}",
  "top_n": 3
}
```

---

## Technologies

- Python 3.10+
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- httpx (async HTTP)
- xml.etree.ElementTree (XML parsing)
- Tested with MCP Inspector v0.21.1
