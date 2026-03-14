from server import (
    validate_sample,
    get_checklist_info,
    recommend_checklist
)
import asyncio
import json
import sys
import os

# Add project root to path so we can import server functions directly
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


async def run_tests():

    print("=" * 50)
    print("TEST 1: validate_sample — should FAIL (missing fields)")
    print("=" * 50)
    result = await validate_sample(
        sample_name="incomplete test sample",
        characteristics=json.dumps({
            "organism": [{"text": "soil metagenome"}]
            # intentionally missing collection_date and geographic_location
        }),
        checklist_id="ERC000011"
    )
    print(result)

    print("\n" + "=" * 50)
    print("TEST 2: validate_sample — should PASS (all mandatory fields)")
    print("=" * 50)
    result = await validate_sample(
        sample_name="complete soil sample",
        characteristics=json.dumps({
            "organism": [{"text": "soil metagenome",
                          "ontologyTerms": ["http://purl.obolibrary.org/obo/NCBITaxon_410658"]}],
            "collection_date":  [{"text": "2024-01-01"}],
            "geographic_location_country_andor_sea": [{"text": "India"}]
        }),
        checklist_id="ERC000011"
    )
    print(result)

    print("\n" + "=" * 50)
    print("TEST 3: get_checklist_info — ERC000011")
    print("=" * 50)
    result = await get_checklist_info("ERC000011")
    print(result)

    print("\n" + "=" * 50)
    print("TEST 4: recommend_checklist — soil sample")
    print("=" * 50)
    result = await recommend_checklist(
        sample_name="soil metagenome sample",
        characteristics=json.dumps({
            "organism":         [{"text": "soil metagenome"}],
            "collection_date":  [{"text": "2024-01-01"}],
            "geographic_location_country_andor_sea": [{"text": "India"}],
            "lat_lon":          [{"text": "28.6139 N 77.2090 E"}]
        }),
        top_n=3
    )
    print(result)

asyncio.run(run_tests())
