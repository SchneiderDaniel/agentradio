#!/usr/bin/env python3
"""
Tool: AI SEO Audit Enricher
Purpose: Merge Perplexity research data (platform_data, entity_data, visibility_data)
         into the crawl JSON so the scorer can access all dimensions.

This script sits between audit_crawl.py and audit_score.py in the audit flow:
  1. audit_crawl.py  → crawl JSON
  2. Perplexity MCP  → enrichment JSON (platform_data, entity_data, visibility_data)
  3. audit_enrich.py → merged crawl JSON (this script)
  4. audit_score.py  → scored audit

Usage:
    # Merge from a separate enrichment JSON file:
    python3 .claude/skills/ai-seo/scripts/audit_enrich.py \
        --crawl .tmp/audit_crawl_example_com.json \
        --enrichment .tmp/enrichment_example_com.json

    # Or pass individual data as JSON strings:
    python3 .claude/skills/ai-seo/scripts/audit_enrich.py \
        --crawl .tmp/audit_crawl_example_com.json \
        --platform-data '{"reddit": {"score": 3, "finding": "..."}, ...}' \
        --entity-data '{"about_page_score": 3, ...}' \
        --visibility-data '{"perplexity_score": 5, ...}'

    # Mix and match (file + overrides):
    python3 .claude/skills/ai-seo/scripts/audit_enrich.py \
        --crawl .tmp/audit_crawl_example_com.json \
        --enrichment .tmp/enrichment_example_com.json \
        --visibility-data '{"perplexity_score": 5, "perplexity_finding": "Found in 3/5 queries"}'

Enrichment JSON format:
    {
        "platform_data": {
            "reddit":      {"score": 0-4, "finding": "description"},
            "youtube":     {"score": 0-4, "finding": "description"},
            "linkedin":    {"score": 0-4, "finding": "description"},
            "third_party": {"score": 0-3, "finding": "description"}
        },
        "entity_data": {
            "about_page_score": 0-3,   "about_page_finding": "...",
            "naming_score": 0-3,       "naming_finding": "...",
            "author_score": 0-2,       "author_finding": "...",
            "profiles_score": 0-2,     "profiles_finding": "..."
        },
        "visibility_data": {
            "perplexity_score": 0-5,   "perplexity_finding": "...",
            "aio_score": 0-5,          "aio_finding": "..."
        }
    }

Output: Enriched crawl JSON (overwrites the crawl file by default, or writes to --output)
"""

import sys
import json
import argparse
from pathlib import Path

ENRICHMENT_KEYS = ["platform_data", "entity_data", "visibility_data", "eeat_data", "citability_data"]


def validate_platform_data(data):
    """Validate platform_data structure. Returns list of warnings."""
    warnings = []
    if not isinstance(data, dict):
        warnings.append("platform_data should be a dict")
        return warnings

    expected_platforms = ["reddit", "youtube", "linkedin", "third_party"]
    for platform in expected_platforms:
        if platform not in data:
            warnings.append(f"platform_data missing '{platform}' — will score as 0")
        else:
            entry = data[platform]
            if not isinstance(entry, dict):
                warnings.append(f"platform_data.{platform} should be a dict with 'score' and 'finding'")
            elif "score" not in entry:
                warnings.append(f"platform_data.{platform} missing 'score' — will score as 0")

    return warnings


def validate_entity_data(data):
    """Validate entity_data structure. Returns list of warnings."""
    warnings = []
    if not isinstance(data, dict):
        warnings.append("entity_data should be a dict")
        return warnings

    expected_keys = [
        "about_page_score", "naming_score", "author_score", "profiles_score"
    ]
    for key in expected_keys:
        if key not in data:
            warnings.append(f"entity_data missing '{key}' — will score as 0")

    return warnings


def validate_visibility_data(data):
    """Validate visibility_data structure. Returns list of warnings."""
    warnings = []
    if not isinstance(data, dict):
        warnings.append("visibility_data should be a dict")
        return warnings

    expected_keys = ["perplexity_score", "aio_score"]
    for key in expected_keys:
        if key not in data:
            warnings.append(f"visibility_data missing '{key}' — will score as 0")

    return warnings


def validate_eeat_data(data):
    """Validate eeat_data structure. Returns list of warnings."""
    warnings = []
    if not isinstance(data, dict):
        warnings.append("eeat_data should be a dict")
        return warnings
    for key in ["experience", "expertise", "trust"]:
        if key not in data:
            warnings.append(f"eeat_data missing '{key}' — will score as 0")
        elif not isinstance(data[key], dict) or "score" not in data[key]:
            warnings.append(f"eeat_data.{key} should be a dict with 'score' and 'finding'")
    return warnings


def validate_citability_data(data):
    """Validate citability_data structure. Returns list of warnings."""
    warnings = []
    if not isinstance(data, dict):
        warnings.append("citability_data should be a dict")
        return warnings
    if "site_citability" not in data:
        warnings.append("citability_data missing 'site_citability' — GEO scoring will be limited")
    return warnings


VALIDATORS = {
    "platform_data": validate_platform_data,
    "entity_data": validate_entity_data,
    "visibility_data": validate_visibility_data,
    "eeat_data": validate_eeat_data,
    "citability_data": validate_citability_data,
}


def merge_enrichment(crawl_data, enrichment_data):
    """Merge enrichment data into crawl data. Returns (merged_data, warnings)."""
    warnings = []

    for key in ENRICHMENT_KEYS:
        if key in enrichment_data:
            # Validate
            validator = VALIDATORS.get(key)
            if validator:
                key_warnings = validator(enrichment_data[key])
                warnings.extend(key_warnings)

            # Merge (enrichment overrides crawl if both have the key)
            if key in crawl_data and isinstance(crawl_data[key], dict) and isinstance(enrichment_data[key], dict):
                # Deep merge one level: update existing dict
                crawl_data[key].update(enrichment_data[key])
            else:
                crawl_data[key] = enrichment_data[key]

    return crawl_data, warnings


def main():
    parser = argparse.ArgumentParser(
        description="Merge Perplexity research data into AI SEO crawl JSON"
    )
    parser.add_argument(
        "--crawl", required=True,
        help="Path to crawl JSON from audit_crawl.py"
    )
    parser.add_argument(
        "--enrichment",
        help="Path to enrichment JSON file containing platform_data, entity_data, visibility_data"
    )
    parser.add_argument(
        "--platform-data",
        help="JSON string for platform_data (overrides enrichment file)"
    )
    parser.add_argument(
        "--entity-data",
        help="JSON string for entity_data (overrides enrichment file)"
    )
    parser.add_argument(
        "--visibility-data",
        help="JSON string for visibility_data (overrides enrichment file)"
    )
    parser.add_argument(
        "--eeat-data",
        help="JSON string for eeat_data (overrides enrichment file)"
    )
    parser.add_argument(
        "--citability-data",
        help="JSON string or file path for citability_data (overrides enrichment file)"
    )
    parser.add_argument(
        "--output",
        help="Output path (default: overwrites the crawl JSON in-place)"
    )

    args = parser.parse_args()

    # Load crawl data
    crawl_path = Path(args.crawl)
    if not crawl_path.exists():
        print(json.dumps({"success": False, "error": f"Crawl file not found: {args.crawl}"}))
        sys.exit(1)

    with open(crawl_path) as f:
        crawl_data = json.load(f)

    # Build enrichment data from file + CLI args
    enrichment = {}

    # Load from enrichment file first
    if args.enrichment:
        enrichment_path = Path(args.enrichment)
        if not enrichment_path.exists():
            print(json.dumps({"success": False, "error": f"Enrichment file not found: {args.enrichment}"}))
            sys.exit(1)
        with open(enrichment_path) as f:
            enrichment = json.load(f)

    # CLI args override file values
    if args.platform_data:
        try:
            enrichment["platform_data"] = json.loads(args.platform_data)
        except json.JSONDecodeError as e:
            print(json.dumps({"success": False, "error": f"Invalid JSON for --platform-data: {e}"}))
            sys.exit(1)

    if args.entity_data:
        try:
            enrichment["entity_data"] = json.loads(args.entity_data)
        except json.JSONDecodeError as e:
            print(json.dumps({"success": False, "error": f"Invalid JSON for --entity-data: {e}"}))
            sys.exit(1)

    if args.visibility_data:
        try:
            enrichment["visibility_data"] = json.loads(args.visibility_data)
        except json.JSONDecodeError as e:
            print(json.dumps({"success": False, "error": f"Invalid JSON for --visibility-data: {e}"}))
            sys.exit(1)

    if args.eeat_data:
        try:
            enrichment["eeat_data"] = json.loads(args.eeat_data)
        except json.JSONDecodeError as e:
            print(json.dumps({"success": False, "error": f"Invalid JSON for --eeat-data: {e}"}))
            sys.exit(1)

    if args.citability_data:
        try:
            # Accept either JSON string or file path
            if Path(args.citability_data).exists():
                with open(args.citability_data) as f:
                    enrichment["citability_data"] = json.load(f)
            else:
                enrichment["citability_data"] = json.loads(args.citability_data)
        except json.JSONDecodeError as e:
            print(json.dumps({"success": False, "error": f"Invalid JSON for --citability-data: {e}"}))
            sys.exit(1)

    # Check we have something to merge
    has_data = any(key in enrichment for key in ENRICHMENT_KEYS)
    if not has_data:
        print(json.dumps({
            "success": False,
            "error": "No enrichment data provided. Use --enrichment file or --platform-data/--entity-data/--visibility-data args."
        }))
        sys.exit(1)

    # Merge
    merged, warnings = merge_enrichment(crawl_data, enrichment)

    # Write output
    output_path = args.output or str(crawl_path)
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(merged, f, indent=2, default=str)

    # Summary of what was enriched
    enriched_keys = [key for key in ENRICHMENT_KEYS if key in enrichment]

    result = {
        "success": True,
        "output": output_path,
        "domain": merged.get("domain", "unknown"),
        "enriched": enriched_keys,
        "warnings": warnings if warnings else None
    }

    # Remove None values for cleaner output
    result = {k: v for k, v in result.items() if v is not None}

    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
