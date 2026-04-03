#!/usr/bin/env python3
"""
Tool: Entity-Message Alignment Checker
Purpose: Compare what a business actually does (provided context) vs what the website says it does.
         The gap between business reality and website messaging is a scoreable SEO signal.

Usage:
    python3 .claude/skills/ai-seo/scripts/audit_alignment.py \
        --crawl .tmp/audit_crawl_example_com.json \
        --context path/to/business_context.md

Input:
    --crawl: Output JSON from audit_crawl.py (contains page content analysis)
    --context: Business context file (markdown or YAML) describing the actual business

Output: JSON with alignment score (0-10), findings, and gaps.
        Saved to .tmp/audit_alignment_<domain>.json
"""

import sys
import json
import re
import argparse
from pathlib import Path

try:
    import yaml
    HAS_YAML = True
except ImportError:
    HAS_YAML = False


def parse_context(context_path):
    """Parse business context from markdown or YAML file.

    Extracts five key signals:
        - business_name
        - services (list of what they sell)
        - target_audience / ICP
        - revenue_model
        - differentiators
    """
    path = Path(context_path)
    text = path.read_text(encoding="utf-8")
    ext = path.suffix.lower()

    if ext in (".yaml", ".yml"):
        if not HAS_YAML:
            print("PyYAML required for YAML context files: pip3 install pyyaml", file=sys.stderr)
            sys.exit(1)
        data = yaml.safe_load(text) or {}
        return normalize_context(data)

    # Markdown parsing — extract structured sections
    return parse_markdown_context(text)


def parse_markdown_context(text):
    """Extract business signals from a markdown file.

    Handles three formats:
    1. Embedded YAML code blocks (```yaml ... ```)
    2. Heading-based sections (## Services, ## Audience, etc.)
    3. Freetext fallback
    """
    ctx = {
        "business_name": "",
        "services": [],
        "target_audience": [],
        "revenue_model": [],
        "differentiators": [],
    }

    # Priority 1: Check for embedded YAML code blocks
    yaml_blocks = re.findall(r'```(?:yaml|yml)\s*\n(.*?)```', text, re.DOTALL)
    if yaml_blocks and HAS_YAML:
        for block in yaml_blocks:
            try:
                data = yaml.safe_load(block) or {}
                if isinstance(data, dict):
                    yaml_ctx = _extract_from_yaml_dict(data)
                    # Merge into ctx (first block with data wins for each field)
                    if not ctx["business_name"] and yaml_ctx["business_name"]:
                        ctx["business_name"] = yaml_ctx["business_name"]
                    for key in ["services", "target_audience", "revenue_model", "differentiators"]:
                        if not ctx[key] and yaml_ctx[key]:
                            ctx[key] = yaml_ctx[key]
            except Exception:
                pass

    # Priority 2: Heading-based sections (for content outside YAML blocks)
    heading_map = {
        "business_name": [
            "business name", "company name", "brand", "name", "who we are",
        ],
        "services": [
            "services", "what we do", "offerings", "products", "what we sell",
            "what they sell", "service", "product", "offer",
        ],
        "target_audience": [
            "target audience", "icp", "ideal customer", "audience", "who we serve",
            "target market", "customer", "persona",
        ],
        "revenue_model": [
            "revenue model", "revenue", "pricing", "monetization", "business model",
            "how we make money", "money model",
        ],
        "differentiators": [
            "differentiators", "unique", "competitive advantage", "why us",
            "what makes us different", "usp", "positioning", "key differentiators",
            "what moves", "needle",
        ],
    }

    # Strip YAML blocks before parsing headings
    text_no_yaml = re.sub(r'```(?:yaml|yml)\s*\n.*?```', '', text, flags=re.DOTALL)
    sections = re.split(r'^#{1,3}\s+', text_no_yaml, flags=re.MULTILINE)
    headings = re.findall(r'^#{1,3}\s+(.+)', text_no_yaml, flags=re.MULTILINE)

    for i, heading in enumerate(headings):
        heading_lower = heading.strip().lower()
        section_body = sections[i + 1] if i + 1 < len(sections) else ""

        for signal, keywords in heading_map.items():
            if any(kw in heading_lower for kw in keywords):
                lines = [
                    ln.lstrip("- *•").strip()
                    for ln in section_body.strip().split("\n")
                    if ln.strip() and not ln.strip().startswith("#") and not ln.strip().startswith("```")
                ]
                if signal == "business_name" and not ctx["business_name"]:
                    ctx["business_name"] = lines[0] if lines else ""
                elif signal != "business_name" and not ctx[signal]:
                    ctx[signal].extend(lines)

    # Fallback: try to grab business name from the first H1
    if not ctx["business_name"]:
        h1 = re.search(r'^#\s+(.+)', text, re.MULTILINE)
        if h1:
            ctx["business_name"] = h1.group(1).strip()

    # If no structured sections found, do a best-effort full-text extraction
    if not any([ctx["services"], ctx["target_audience"], ctx["revenue_model"], ctx["differentiators"]]):
        ctx = extract_signals_from_freetext(text_no_yaml, ctx)

    return ctx


def _extract_from_yaml_dict(data):
    """Extract business signals from a parsed YAML dictionary."""

    def to_list(val):
        if isinstance(val, list):
            return [str(v).strip() for v in val if str(v).strip()]
        if isinstance(val, str):
            return [v.strip() for v in val.split(",") if v.strip()]
        return []

    # Business name — prefer 'business' field (brand name) over 'name' (person name)
    name = ""
    for key in ["business_name", "brand", "company", "business", "name"]:
        val = data.get(key, "")
        if val:
            name = str(val)
            # Clean up patterns like "atomicOps — AI YouTube Channel + Consulting + Community"
            # Use the first part before any dash/emdash separator as the brand name
            if " — " in name:
                name = name.split(" — ")[0].strip()
            elif " - " in name and len(name.split(" - ")[0]) > 2:
                name = name.split(" - ")[0].strip()
            break

    # Services — multiple possible keys
    services = []
    for key in ["services", "offerings", "products", "what_we_do"]:
        val = data.get(key)
        if val:
            services = to_list(val)
            break
    # Also extract from business description if it lists services
    biz_desc = str(data.get("business", ""))
    if biz_desc and not services:
        # Parse "X + Y + Z" patterns
        if "+" in biz_desc:
            parts = [p.strip() for p in biz_desc.split("+") if p.strip()]
            # Skip the brand name part
            if " — " in biz_desc:
                parts = [p.strip() for p in biz_desc.split(" — ", 1)[1].split("+") if p.strip()]
            services = parts
    # Also check revenue_model and current_priorities for service hints
    revenue_str = str(data.get("revenue_model", ""))
    if revenue_str:
        services.extend([r.strip() for r in revenue_str.split(",") if r.strip()])
    priorities = to_list(data.get("current_priorities", []))
    for p in priorities:
        if any(kw in p.lower() for kw in ["consulting", "community", "launch", "pipeline", "content"]):
            services.append(p)

    # Target audience
    audience = []
    for key in ["target_audience", "icp", "audience", "ideal_customer"]:
        val = data.get(key)
        if val:
            audience = to_list(val)
            break

    # Revenue model
    revenue = to_list(data.get("revenue_model", data.get("pricing", data.get("monetization", []))))

    # Differentiators
    differentiators = to_list(data.get("differentiators", data.get("usp", data.get("competitive_advantage", []))))

    return {
        "business_name": name,
        "services": services,
        "target_audience": audience,
        "revenue_model": revenue,
        "differentiators": differentiators,
    }


def extract_signals_from_freetext(text, ctx):
    """Best-effort signal extraction from unstructured text."""
    lines = [ln.strip() for ln in text.split("\n") if ln.strip()]

    for line in lines:
        lower = line.lower()
        # Skip headings themselves
        if line.startswith("#"):
            continue

        # Services indicators
        if any(kw in lower for kw in ["we offer", "we provide", "we sell", "service include",
                                       "consulting", "coaching", "course", "workshop",
                                       "saas", "platform", "tool", "product"]):
            ctx["services"].append(line.lstrip("- *•").strip())

        # Audience indicators
        if any(kw in lower for kw in ["target", "audience", "icp", "serve", "customer",
                                       "client", "founder", "developer", "builder",
                                       "enterprise", "smb", "startup"]):
            ctx["target_audience"].append(line.lstrip("- *•").strip())

        # Revenue indicators
        if any(kw in lower for kw in ["$/mo", "pricing", "revenue", "subscription",
                                       "one-time", "retainer", "per month", "free tier"]):
            ctx["revenue_model"].append(line.lstrip("- *•").strip())

        # Differentiator indicators
        if any(kw in lower for kw in ["unique", "only", "unlike", "differentiator",
                                       "competitive", "advantage", "first to",
                                       "no one else", "proprietary"]):
            ctx["differentiators"].append(line.lstrip("- *•").strip())

    return ctx


def normalize_context(data):
    """Normalize a YAML-loaded dict into the standard context shape."""
    def to_list(val):
        if isinstance(val, list):
            return [str(v) for v in val]
        if isinstance(val, str):
            return [v.strip() for v in val.split(",") if v.strip()] if "," in val else [val]
        return []

    return {
        "business_name": str(data.get("business_name", data.get("name", data.get("brand", "")))),
        "services": to_list(data.get("services", data.get("offerings", data.get("products", [])))),
        "target_audience": to_list(data.get("target_audience", data.get("icp", data.get("audience", [])))),
        "revenue_model": to_list(data.get("revenue_model", data.get("pricing", data.get("monetization", [])))),
        "differentiators": to_list(data.get("differentiators", data.get("usp", data.get("competitive_advantage", [])))),
    }


def build_site_text(crawl_data):
    """Concatenate all page content from the crawl into a single searchable text blob.
    Also returns a per-page mapping for locating gaps.
    """
    pages = crawl_data.get("page_analyses", [])
    full_text_parts = []
    page_texts = []

    for page in pages:
        # Use the findings and url; actual content isn't in the crawl output,
        # but we can reconstruct searchable text from findings + metadata
        url = page.get("url", "")
        findings = page.get("findings", {})
        # Build a text representation from available signals
        parts = [url]
        parts.extend(findings.get("stat_examples", []))
        parts.extend(findings.get("citation_examples", []))
        parts.extend(findings.get("question_headings", []))
        page_text = " ".join(str(p) for p in parts)
        full_text_parts.append(page_text)
        page_texts.append({"url": url, "text": page_text, "page_type": page.get("page_type", "")})

    # Also check the raw pages array if present in the original crawl data
    raw_pages = crawl_data.get("pages", [])
    for rp in raw_pages:
        content = rp.get("content", "")
        if content:
            full_text_parts.append(content)
            metadata = rp.get("metadata", {})
            title = metadata.get("title", "")
            description = metadata.get("description", "")
            full_text_parts.extend([title, description])

    full_text = "\n".join(full_text_parts).lower()
    return full_text, page_texts


def check_signal_presence(signal_name, signal_items, full_text, page_texts):
    """Check whether a list of signal items appear in the site content.

    Returns:
        found: list of items found
        missing: list of items not found
        coverage_pct: percentage of items found
    """
    if not signal_items:
        return [], [], None  # No items to check — signal not provided

    found = []
    missing = []

    for item in signal_items:
        item_str = str(item).strip()
        if not item_str:
            continue

        # Build search terms: the full item and its key phrases (3+ word subsequences)
        search_terms = [item_str.lower()]
        words = item_str.lower().split()
        if len(words) >= 4:
            # Also search for meaningful sub-phrases (first 3 words, last 3 words)
            search_terms.append(" ".join(words[:3]))
            search_terms.append(" ".join(words[-3:]))
        # Also search for individual key terms (skip common words)
        stop_words = {"the", "a", "an", "and", "or", "is", "are", "was", "were", "to", "for",
                      "of", "in", "on", "at", "by", "with", "from", "as", "it", "we", "our",
                      "they", "their", "that", "this", "who", "what", "how", "do", "does"}
        key_terms = [w for w in words if w.lower() not in stop_words and len(w) > 2]

        # Check presence: full phrase match or majority of key terms present
        full_match = any(term in full_text for term in search_terms)
        key_term_matches = sum(1 for kt in key_terms if kt in full_text) if key_terms else 0
        key_term_coverage = (key_term_matches / len(key_terms)) if key_terms else 0

        if full_match or key_term_coverage >= 0.7:
            found.append(item_str)
        else:
            missing.append(item_str)

    total = len(found) + len(missing)
    coverage_pct = round(len(found) / total * 100, 1) if total > 0 else None

    return found, missing, coverage_pct


def check_business_name(name, full_text, crawl_data):
    """Check if business name is used consistently across the site."""
    if not name:
        return {
            "present": False,
            "consistent": False,
            "finding": "Business name not provided in context — cannot check",
        }

    name_lower = name.lower()
    pages = crawl_data.get("page_analyses", [])
    total_pages = len(pages) if pages else 1

    # Check raw pages content if available
    raw_pages = crawl_data.get("pages", [])
    pages_with_name = 0

    for rp in raw_pages:
        content = (rp.get("content", "") or "").lower()
        title = (rp.get("metadata", {}).get("title", "") or "").lower()
        if name_lower in content or name_lower in title:
            pages_with_name += 1

    # Fallback: check in the aggregated full_text
    present = name_lower in full_text
    name_count = full_text.count(name_lower)

    if raw_pages:
        consistency_pct = round(pages_with_name / len(raw_pages) * 100, 1) if raw_pages else 0
    else:
        # Estimate from occurrence count
        consistency_pct = min(100, round(name_count / total_pages * 100, 1))

    return {
        "present": present,
        "consistent": consistency_pct >= 50,
        "occurrences": name_count,
        "consistency_pct": consistency_pct,
        "finding": (
            f"Business name '{name}' found {name_count} times across site ({consistency_pct}% page coverage)"
            if present
            else f"Business name '{name}' not found on the website"
        ),
    }


def check_cta_and_pricing(full_text):
    """Check if site has clear calls to action or pricing."""
    cta_patterns = [
        r"get started", r"sign up", r"book a call", r"schedule",
        r"contact us", r"request a demo", r"free trial", r"start free",
        r"buy now", r"add to cart", r"subscribe", r"join now",
        r"apply now", r"enroll", r"register",
    ]
    pricing_patterns = [
        r"\$\d+", r"pricing", r"per month", r"/mo", r"/year",
        r"free plan", r"starter plan", r"enterprise", r"custom pricing",
    ]

    has_cta = any(re.search(p, full_text) for p in cta_patterns)
    has_pricing = any(re.search(p, full_text) for p in pricing_patterns)

    return has_cta, has_pricing


def compute_alignment_score(name_check, signal_results, has_cta, has_pricing):
    """Compute the 0-10 alignment score.

    Weighting:
        Business name consistency:  1.5 pts
        Services described:         3.0 pts
        Target audience addressed:  2.0 pts
        CTA / pricing present:      1.5 pts
        Differentiators communicated: 2.0 pts
    Total: 10 pts

    Signals without context data are excluded from scoring and the max adjusts.
    """
    earned = 0.0
    possible = 0.0

    # Business name (1.5 pts)
    possible += 1.5
    if name_check["present"] and name_check["consistent"]:
        earned += 1.5
    elif name_check["present"]:
        earned += 0.75

    # Services (3.0 pts)
    svc = signal_results.get("services", {})
    svc_cov = svc.get("coverage_pct")
    if svc_cov is not None:
        possible += 3.0
        if svc_cov >= 80:
            earned += 3.0
        elif svc_cov >= 50:
            earned += 2.0
        elif svc_cov >= 25:
            earned += 1.0

    # Target audience (2.0 pts)
    aud = signal_results.get("target_audience", {})
    aud_cov = aud.get("coverage_pct")
    if aud_cov is not None:
        possible += 2.0
        if aud_cov >= 70:
            earned += 2.0
        elif aud_cov >= 40:
            earned += 1.0
        elif aud_cov > 0:
            earned += 0.5

    # CTA / pricing (1.5 pts)
    possible += 1.5
    if has_cta and has_pricing:
        earned += 1.5
    elif has_cta or has_pricing:
        earned += 0.75

    # Differentiators (2.0 pts)
    diff = signal_results.get("differentiators", {})
    diff_cov = diff.get("coverage_pct")
    if diff_cov is not None:
        possible += 2.0
        if diff_cov >= 70:
            earned += 2.0
        elif diff_cov >= 40:
            earned += 1.0
        elif diff_cov > 0:
            earned += 0.5

    # Revenue model doesn't directly contribute to score but generates findings

    # Scale to 0-10
    if possible > 0:
        raw_score = round(earned / possible * 10, 1)
    else:
        raw_score = 0

    return min(10, max(0, raw_score))


def score_tier(score):
    """Return a human-readable tier label for the alignment score."""
    if score >= 9:
        return "excellent", "Website clearly communicates what the business does"
    elif score >= 6:
        return "good", "Most elements present but some gaps exist"
    elif score >= 3:
        return "weak", "Significant disconnect between business reality and website"
    else:
        return "poor", "Website doesn't represent what the business actually does"


def generate_findings(name_check, signal_results, has_cta, has_pricing, context):
    """Generate specific, actionable finding strings."""
    findings = []

    # Business name
    if not name_check["present"]:
        findings.append(f"Your business name '{context['business_name']}' doesn't appear on the website")
    elif not name_check["consistent"]:
        findings.append(
            f"Your business name '{context['business_name']}' is used inconsistently "
            f"(only {name_check.get('consistency_pct', 0)}% page coverage)"
        )

    # Services
    svc = signal_results.get("services", {})
    for item in svc.get("missing", []):
        findings.append(f"Your site doesn't clearly describe this service/offering: \"{item}\"")

    # Target audience
    aud = signal_results.get("target_audience", {})
    for item in aud.get("missing", []):
        findings.append(f"Target audience '{item}' is not addressed directly on the site")

    # Revenue model
    rev = signal_results.get("revenue_model", {})
    for item in rev.get("missing", []):
        findings.append(f"Revenue model component not mentioned on site: \"{item}\"")

    # Differentiators
    diff = signal_results.get("differentiators", {})
    for item in diff.get("missing", []):
        findings.append(f"Key differentiator not communicated: \"{item}\"")

    # CTA / pricing
    if not has_cta:
        findings.append("No clear call to action found on the site (no 'get started', 'book a call', 'sign up', etc.)")
    if not has_pricing:
        findings.append("No pricing information found on the site")

    return findings


def run_alignment_check(crawl_data, context):
    """Run the full alignment check and return results."""
    full_text, page_texts = build_site_text(crawl_data)

    # Check business name
    name_check = check_business_name(context["business_name"], full_text, crawl_data)

    # Check each signal category
    signal_results = {}
    for signal_name in ["services", "target_audience", "revenue_model", "differentiators"]:
        items = context.get(signal_name, [])
        found, missing, coverage_pct = check_signal_presence(signal_name, items, full_text, page_texts)
        signal_results[signal_name] = {
            "found": found,
            "missing": missing,
            "coverage_pct": coverage_pct,
            "total_items": len(found) + len(missing),
        }

    # Check CTA and pricing
    has_cta, has_pricing = check_cta_and_pricing(full_text)

    # Compute score
    score = compute_alignment_score(name_check, signal_results, has_cta, has_pricing)

    # Determine tier
    tier_key, tier_description = score_tier(score)

    # Generate findings
    findings = generate_findings(name_check, signal_results, has_cta, has_pricing, context)

    # Build gaps summary
    gaps = []
    for signal_name, result in signal_results.items():
        if result["missing"]:
            gaps.append({
                "signal": signal_name,
                "missing_items": result["missing"],
                "coverage_pct": result["coverage_pct"],
            })

    domain = crawl_data.get("domain", "unknown")

    return {
        "domain": domain,
        "alignment_score": score,
        "alignment_tier": tier_key,
        "alignment_description": tier_description,
        "business_name_check": name_check,
        "signal_coverage": {
            name: {
                "found_count": len(r["found"]),
                "missing_count": len(r["missing"]),
                "coverage_pct": r["coverage_pct"],
                "found": r["found"],
                "missing": r["missing"],
            }
            for name, r in signal_results.items()
        },
        "has_cta": has_cta,
        "has_pricing": has_pricing,
        "findings": findings,
        "gaps": gaps,
        "context_provided": {
            "business_name": context["business_name"],
            "services_count": len(context["services"]),
            "audience_count": len(context["target_audience"]),
            "revenue_items_count": len(context["revenue_model"]),
            "differentiators_count": len(context["differentiators"]),
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Entity-Message Alignment Checker")
    parser.add_argument("--crawl", required=True, help="Path to crawl results JSON (from audit_crawl.py)")
    parser.add_argument("--context", required=True, help="Path to business context file (markdown or YAML)")
    parser.add_argument("--output", help="Output path (default: .tmp/audit_alignment_<domain>.json)")

    args = parser.parse_args()

    # Load crawl data
    with open(args.crawl) as f:
        crawl_data = json.load(f)

    # Parse business context
    context = parse_context(args.context)

    # Run alignment check
    result = run_alignment_check(crawl_data, context)

    # Determine output path
    domain_slug = crawl_data.get("domain", "unknown").replace(".", "_")
    output_path = args.output or f".tmp/audit_alignment_{domain_slug}.json"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(result, f, indent=2, default=str)

    print(json.dumps({
        "success": True,
        "output": output_path,
        "alignment_score": result["alignment_score"],
        "tier": result["alignment_tier"],
        "findings_count": len(result["findings"]),
        "gaps_count": len(result["gaps"]),
    }, indent=2))


if __name__ == "__main__":
    main()
