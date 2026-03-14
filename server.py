import httpx
import json
import xml.etree.ElementTree as ET
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("biosamples-validator")

BIOVALIDATOR_URL = "https://www.ebi.ac.uk/biosamples/validate"
ENA_BROWSER_URL = "https://www.ebi.ac.uk/ena/browser/api"
ENA_PORTAL_URL = "https://www.ebi.ac.uk/ena/portal/api"

# Known public ENA checklists — discovered during API research.
# The dynamic listing endpoint requires internal access, so we
# maintain a curated list of the most commonly used checklists.
# This will be replaced by a live API call once internal schema
# store access is confirmed with mentors during community bonding.
KNOWN_CHECKLISTS = [
    "ERC000011", "ERC000012", "ERC000013", "ERC000014",
    "ERC000015", "ERC000016", "ERC000017", "ERC000018",
    "ERC000019", "ERC000020", "ERC000021", "ERC000022",
    "ERC000023", "ERC000024", "ERC000025"
]


# ─────────────────────────────────────────────
# HELPER: Parse checklist XML into structured dict
# ─────────────────────────────────────────────
def parse_checklist_xml(xml_text: str) -> dict:
    """
    Parses ENA checklist XML and extracts field metadata.
    Returns a dict with checklist name, description, and
    lists of mandatory and optional fields.
    """
    root = ET.fromstring(xml_text)
    checklist = root.find("CHECKLIST")
    descriptor = checklist.find("DESCRIPTOR")

    name = descriptor.find("NAME").text
    description = descriptor.find("DESCRIPTION").text

    mandatory_fields = []
    optional_fields = []

    for field_group in descriptor.findall("FIELD_GROUP"):
        for field in field_group.findall("FIELD"):
            name_el = field.find("NAME")
            mandatory_el = field.find("MANDATORY")
            desc_el = field.find("DESCRIPTION")

            field_name = name_el.text if name_el is not None else "unknown"
            is_mandatory = mandatory_el is not None and mandatory_el.text == "mandatory"
            desc = desc_el.text[:80] if desc_el is not None and desc_el.text else ""

            entry = {"field": field_name, "description": desc}

            if is_mandatory:
                mandatory_fields.append(entry)
            else:
                optional_fields.append(entry)

    return {
        "name":             name,
        "description":      description,
        "mandatory_fields": mandatory_fields,
        "optional_fields":  optional_fields,
    }


# ─────────────────────────────────────────────
# HELPER: Score how well a sample fits a checklist
# ─────────────────────────────────────────────
def score_sample_against_checklist(
    sample_characteristics: dict,
    checklist_data: dict
) -> dict:
    """
    Scores a sample against a checklist based on field coverage.

    Scoring logic:
    - Each mandatory field present in sample = +2 points
    - Each optional field present in sample  = +1 point
    - Confidence = matched points / max possible points

    Returns score details including which fields are missing.
    """
    mandatory = checklist_data["mandatory_fields"]
    optional = checklist_data["optional_fields"]

    # Normalise sample keys: lowercase + replace spaces with underscores
    # so "collection date" matches "collection_date" etc.
    sample_keys = set(
        k.lower().replace(" ", "_").replace("(", "").replace(")", "")
        for k in sample_characteristics.keys()
    )

    matched_mandatory = []
    missing_mandatory = []
    matched_optional = []

    for f in mandatory:
        field_norm = f["field"].lower().replace(" ", "_")
        if field_norm in sample_keys:
            matched_mandatory.append(f["field"])
        else:
            missing_mandatory.append(f["field"])

    for f in optional:
        field_norm = f["field"].lower().replace(" ", "_")
        if field_norm in sample_keys:
            matched_optional.append(f["field"])

    # Calculate score
    max_points = len(mandatory) * 2 + len(optional)
    got_points = len(matched_mandatory) * 2 + len(matched_optional)
    confidence = round(got_points / max_points, 3) if max_points > 0 else 0.0

    # A checklist is only viable if ALL mandatory fields are present
    mandatory_coverage = (
        len(matched_mandatory) / len(mandatory)
        if mandatory else 1.0
    )

    return {
        "confidence":          confidence,
        "mandatory_coverage":  round(mandatory_coverage, 3),
        "matched_mandatory":   matched_mandatory,
        "missing_mandatory":   missing_mandatory,
        "matched_optional":    matched_optional,
        "total_mandatory":     len(mandatory),
        "total_optional":      len(optional),
    }


# ─────────────────────────────────────────────
# TOOL 1: validate_sample
# ─────────────────────────────────────────────
@mcp.tool()
async def validate_sample(
    sample_name: str,
    characteristics: str,
    checklist_id: str = "ERC000011"
) -> str:
    """
    Validates a biological sample's metadata against a specific
    BioSamples checklist using the EMBL-EBI BioValidator API.

    Use this when the user already knows which checklist to validate
    against. For automatic checklist recommendation, use
    recommend_checklist instead.

    Args:
        sample_name:     Name of the sample. Example: "soil sample from Delhi"
        characteristics: Sample metadata as a JSON string.
                         Format: '{"field_name": [{"text": "value"}], ...}'
                         Example: '{"organism": [{"text": "soil metagenome"}],
                                    "collection_date": [{"text": "2024-01-01"}]}'
        checklist_id:    ENA checklist ID. Default: ERC000011 (ENA default).

    Returns:
        Validation result with field-level errors if the sample is invalid.
    """
    # Parse characteristics
    try:
        chars_dict = json.loads(characteristics)
    except json.JSONDecodeError:
        return "Error: characteristics must be valid JSON."

    payload = {
        "name":         sample_name,
        "characteristics": chars_dict,
        "checklist":    checklist_id
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.post(
                BIOVALIDATOR_URL,
                json=payload,
                headers={"Content-Type": "application/json"}
            )

        # 200 = valid
        if response.status_code == 200:
            return (
                f"✓ VALID — '{sample_name}' passed checklist {checklist_id}.\n"
                f"All required fields are present and correctly formatted."
            )

        # 400 = validation errors
        elif response.status_code == 400:
            body = response.json()

            # Structured validation errors: list of {dataPath, errors}
            if isinstance(body, list):
                lines = [
                    f"✗ INVALID — '{sample_name}' failed checklist {checklist_id}.",
                    f"Found {len(body)} issue(s):\n"
                ]
                for item in body:
                    path = item.get("dataPath", "unknown field")
                    errors = item.get("errors", [])
                    for err in errors:
                        lines.append(f"  • {path}: {err}")
                lines.append(
                    "\nFix: add the missing fields to characteristics "
                    "or use recommend_checklist to find a better matching checklist."
                )
                return "\n".join(lines)

            # Other 400: malformed request
            else:
                msg = body.get("message", response.text)
                return f"Error: Bad request — {msg}"

        else:
            return f"Unexpected status {response.status_code}: {response.text[:200]}"

    except httpx.TimeoutException:
        return "Error: BioValidator timed out."
    except httpx.RequestError as e:
        return f"Error: Could not reach BioValidator. {str(e)}"


# ─────────────────────────────────────────────
# TOOL 2: get_checklist_info
# ─────────────────────────────────────────────
@mcp.tool()
async def get_checklist_info(checklist_id: str) -> str:
    """
    Fetches the full field specification for a given ENA checklist.
    Returns all mandatory and optional fields with descriptions.

    Use this to understand what fields a specific checklist requires
    before submitting or validating a sample.

    Args:
        checklist_id: ENA checklist accession. Example: "ERC000011"

    Returns:
        Full list of mandatory and optional fields for the checklist.
    """
    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            response = await client.get(
                f"{ENA_BROWSER_URL}/xml/{checklist_id}",
                headers={"Accept": "application/xml"},
                follow_redirects=True
            )

        if response.status_code != 200:
            return f"Error: Could not fetch checklist {checklist_id}. Status: {response.status_code}"

        data = parse_checklist_xml(response.text)

        lines = [
            f"Checklist: {checklist_id}",
            f"Name: {data['name']}",
            f"Description: {data['description']}",
            f"\nMandatory fields ({len(data['mandatory_fields'])}):"
        ]
        for f in data["mandatory_fields"]:
            lines.append(f"  • {f['field']}: {f['description']}")

        lines.append(f"\nOptional fields ({len(data['optional_fields'])}):")
        for f in data["optional_fields"][:10]:  # show first 10 optional
            lines.append(f"  • {f['field']}: {f['description']}")

        if len(data["optional_fields"]) > 10:
            lines.append(
                f"  ... and {len(data['optional_fields']) - 10} more optional fields."
            )

        return "\n".join(lines)

    except ET.ParseError:
        return f"Error: Could not parse XML for checklist {checklist_id}."
    except httpx.RequestError as e:
        return f"Error: Could not reach ENA. {str(e)}"


# ─────────────────────────────────────────────
# TOOL 3: recommend_checklist
# ─────────────────────────────────────────────
@mcp.tool()
async def recommend_checklist(
    sample_name: str,
    characteristics: str,
    top_n: int = 3
) -> str:
    """
    Recommends the most suitable ENA/BioSamples checklists for a
    given sample metadata payload. Use this when the submitter has
    not specified a checklist, or wants to verify they picked the
    right one.

    Scoring is based on:
    - Mandatory field coverage (weighted 2x)
    - Optional field coverage (weighted 1x)
    - Overall confidence score (0.0 to 1.0)

    Args:
        sample_name:     Name of the sample.
        characteristics: Sample metadata as a JSON string.
                         Format: '{"field_name": [{"text": "value"}], ...}'
        top_n:           Number of top recommendations to return. Default: 3.

    Returns:
        Ranked list of checklists with confidence scores and missing fields.
    """
    # Parse characteristics
    try:
        chars_dict = json.loads(characteristics)
    except json.JSONDecodeError:
        return "Error: characteristics must be valid JSON."

    results = []

    async with httpx.AsyncClient(timeout=15.0) as client:
        for checklist_id in KNOWN_CHECKLISTS:
            try:
                # Fetch checklist XML
                r = await client.get(
                    f"{ENA_BROWSER_URL}/xml/{checklist_id}",
                    headers={"Accept": "application/xml"},
                    follow_redirects=True
                )

                if r.status_code != 200:
                    continue

                checklist_data = parse_checklist_xml(r.text)
                score = score_sample_against_checklist(
                    chars_dict, checklist_data
                )

                results.append({
                    "checklist_id":       checklist_id,
                    "name":               checklist_data["name"],
                    "confidence":         score["confidence"],
                    "mandatory_coverage": score["mandatory_coverage"],
                    "missing_mandatory":  score["missing_mandatory"],
                    "matched_optional":   len(score["matched_optional"]),
                })

            except Exception:
                # Skip checklists that fail to fetch or parse
                continue

    if not results:
        return "Error: Could not fetch any checklists. Please try again."

    # Sort: first by mandatory coverage (must-have), then by confidence
    results.sort(
        key=lambda x: (x["mandatory_coverage"], x["confidence"]),
        reverse=True
    )

    top = results[:top_n]

    lines = [
        f"Checklist recommendations for '{sample_name}'",
        f"Based on {len(results)} checklists evaluated.\n"
    ]

    for i, r in enumerate(top, 1):
        lines.append(f"{'─'*45}")
        lines.append(f"#{i} {r['checklist_id']} — {r['name']}")
        lines.append(f"   Confidence score:      {r['confidence']:.1%}")
        lines.append(
            f"   Mandatory coverage:    {r['mandatory_coverage']:.1%}")
        lines.append(f"   Optional fields matched: {r['matched_optional']}")

        if r["missing_mandatory"]:
            missing = ", ".join(r["missing_mandatory"])
            lines.append(f"   Missing mandatory:     {missing}")
        else:
            lines.append("   Missing mandatory:     none ✓")

    lines.append(f"{'─'*45}")
    lines.append(
        "\nTip: Use get_checklist_info to see all fields for a checklist, "
        "or validate_sample to check your sample against a specific one."
    )

    return "\n".join(lines)


# ─────────────────────────────────────────────
# Run
# ─────────────────────────────────────────────
if __name__ == "__main__":
    mcp.run(transport="stdio")
