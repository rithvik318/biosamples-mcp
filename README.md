# biosamples-mcp

A Model Context Protocol (MCP) server that helps researchers validate
and select BioSamples/ENA checklists for biological sample metadata.

Built as part of GSoC 2026 proposal preparation for EMBL-EBI.

## What it does

Exposes 3 MCP tools that an LLM (e.g. Claude) can call:

| Tool | Description |
|------|-------------|
| `validate_sample` | Validates sample metadata against a specific ENA checklist via BioValidator API |
| `get_checklist_info` | Fetches all mandatory and optional fields for a given checklist |
| `recommend_checklist` | Scores sample metadata against 15 checklists and returns ranked recommendations |

## APIs used

- EMBL-EBI BioValidator: `https://www.ebi.ac.uk/biosamples/validate`
- ENA Browser XML API: `https://www.ebi.ac.uk/ena/browser/api/xml/{checklist_id}`

## Setup
```bash
git clone https://github.com/YOUR_USERNAME/biosamples-mcp
cd biosamples-mcp
python -m venv venv
venv\Scripts\activate      # Windows
# source venv/bin/activate # Mac/Linux
pip install mcp httpx
```

## Run the MCP server
```bash
python server.py
```

## Connect to Claude Desktop

Add to your Claude Desktop config
(`%APPDATA%\Claude\claude_desktop_config.json` on Windows):
```json
{
  "mcpServers": {
    "biosamples-validator": {
      "command": "python",
      "args": ["C:/full/path/to/biosamples-mcp/server.py"]
    }
  }
}
```

## Key findings during development

- BioValidator returns structured `{dataPath, errors}` arrays for invalid samples
- ENA checklist XML endpoint (`/ena/browser/api/xml/`) is the reliable
  source for field definitions including mandatory/optional status
- BioSamples JSON Schema Store endpoints are not publicly accessible —
  flagged as a risk item in the GSoC proposal with mitigation plan
- BioValidator does not enforce checklist mandatory fields at API level —
  the MCP server's scoring engine fills this gap

## Tools and technologies

- Python 3.10+
- [MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
- httpx (async HTTP)
- xml.etree.ElementTree (XML parsing)
