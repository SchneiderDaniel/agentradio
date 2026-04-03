#!/usr/bin/env python3
"""
Tool: AI SEO Audit Scorer
Purpose: Score crawl results against the scoring rubric to produce a final audit report.

Usage:
    python3 .claude/skills/ai-seo/scripts/audit_score.py --input .tmp/audit_crawl_example_com.json

Input: Output from audit_crawl.py
Output: Scored audit with per-dimension scores, overall score, tier, and priority fixes.

The scoring rubric is loaded from references/scoring_rubric.yaml.
"""

import sys
import json
import argparse
from pathlib import Path

try:
    import yaml
except ImportError:
    print("PyYAML required: pip3 install pyyaml", file=sys.stderr)
    sys.exit(1)

SKILL_DIR = Path(__file__).resolve().parent.parent
RUBRIC_PATH = SKILL_DIR / "references" / "scoring_rubric.yaml"


def load_rubric():
    """Load the scoring rubric from YAML."""
    with open(RUBRIC_PATH) as f:
        return yaml.safe_load(f)


def score_content_structure(agg, page_analyses, rubric_checks):
    """Score the content structure dimension (25 pts)."""
    total_pages = len(page_analyses) if page_analyses else 1
    scores = {}
    findings = {}

    # answer_first (8 pts)
    af_pct = agg.get("answer_first_pct", 0)
    if af_pct >= 80:
        scores["answer_first"] = 8
    elif af_pct >= 50:
        scores["answer_first"] = 5
    elif af_pct >= 25:
        scores["answer_first"] = 3
    else:
        scores["answer_first"] = 0
    findings["answer_first"] = f"{af_pct}% of pages have answer-first format"

    # fact_density (5 pts)
    pages_with_stats_pct = (agg.get("pages_with_stats", 0) / total_pages * 100) if total_pages else 0
    if pages_with_stats_pct >= 70:
        scores["fact_density"] = 5
    elif pages_with_stats_pct >= 40:
        scores["fact_density"] = 3
    else:
        scores["fact_density"] = 0
    findings["fact_density"] = f"{pages_with_stats_pct:.0f}% of pages contain statistics"

    # in_text_citations (4 pts)
    pages_with_cites_pct = (agg.get("pages_with_citations", 0) / total_pages * 100) if total_pages else 0
    if pages_with_cites_pct >= 50:
        scores["in_text_citations"] = 4
    elif pages_with_cites_pct >= 20:
        scores["in_text_citations"] = 2
    else:
        scores["in_text_citations"] = 0
    findings["in_text_citations"] = f"{pages_with_cites_pct:.0f}% of pages cite external sources"

    # expert_quotes (3 pts)
    pages_with_quotes_pct = (agg.get("pages_with_quotes", 0) / total_pages * 100) if total_pages else 0
    if pages_with_quotes_pct >= 30:
        scores["expert_quotes"] = 3
    elif pages_with_quotes_pct >= 10:
        scores["expert_quotes"] = 1
    else:
        scores["expert_quotes"] = 0
    findings["expert_quotes"] = f"{pages_with_quotes_pct:.0f}% of pages include expert quotes"

    # content_freshness (3 pts) — estimated from last_modified presence
    pages_with_dates = sum(1 for p in page_analyses if p.get("last_modified"))
    freshness_pct = (pages_with_dates / total_pages * 100) if total_pages else 0
    if freshness_pct >= 60:
        scores["content_freshness"] = 3
    elif freshness_pct >= 30:
        scores["content_freshness"] = 1
    else:
        scores["content_freshness"] = 0
    findings["content_freshness"] = f"{freshness_pct:.0f}% of pages have visible update dates"

    # question_headings (2 pts)
    pages_with_q = sum(1 for p in page_analyses if p.get("question_heading_count", 0) >= 2)
    q_pct = (pages_with_q / total_pages * 100) if total_pages else 0
    if q_pct >= 40:
        scores["question_headings"] = 2
    elif q_pct >= 15:
        scores["question_headings"] = 1
    else:
        scores["question_headings"] = 0
    findings["question_headings"] = f"{q_pct:.0f}% of pages use question-format headings"

    total = sum(scores.values())
    return total, scores, findings


def score_schema_markup(agg, page_analyses, rubric_checks):
    """Score the schema markup dimension (20 pts)."""
    total_pages = len(page_analyses) if page_analyses else 1
    scores = {}
    findings = {}

    # json_ld_present (6 pts)
    schema_pct = agg.get("schema_coverage_pct", 0)
    if schema_pct >= 80:
        scores["json_ld_present"] = 6
    elif schema_pct >= 50:
        scores["json_ld_present"] = 4
    elif schema_pct > 0:
        scores["json_ld_present"] = 2
    else:
        scores["json_ld_present"] = 0
    findings["json_ld_present"] = f"{schema_pct}% of pages have JSON-LD schema"

    # schema_variety (6 pts)
    schema_types = agg.get("all_schema_types", [])
    type_count = len(schema_types)
    if type_count >= 4:
        scores["schema_variety"] = 6
    elif type_count >= 2:
        scores["schema_variety"] = 4
    elif type_count >= 1:
        scores["schema_variety"] = 2
    else:
        scores["schema_variety"] = 0
    findings["schema_variety"] = f"{type_count} schema types found: {', '.join(schema_types) if schema_types else 'none'}"

    # faq_for_geo (4 pts) — FAQ content for AI citation, NOT FAQPage schema for Google rich results
    # FAQPage schema restricted to gov/healthcare since Aug 2023
    has_faq_content = agg.get("pages_with_faq", 0) > 0
    has_faq_schema = "FAQPage" in schema_types
    has_q_headings = any(p.get("question_heading_count", 0) >= 2 for p in page_analyses)

    if has_faq_content and has_q_headings:
        scores["faq_for_geo"] = 4
    elif has_faq_content or has_q_headings:
        scores["faq_for_geo"] = 2
    else:
        scores["faq_for_geo"] = 0

    faq_finding = f"FAQ content: {'found' if has_faq_content else 'missing'}, Q&A headings: {'found' if has_q_headings else 'missing'}"
    if has_faq_schema:
        faq_finding += " ⚠️ FAQPage schema detected — no longer generates Google rich results for commercial sites (Aug 2023). Still has GEO/LLM citation benefit."
    findings["faq_for_geo"] = faq_finding

    # schema_accuracy (4 pts) — approximation based on schema existence
    if type_count >= 2 and schema_pct >= 50:
        scores["schema_accuracy"] = 4
    elif type_count >= 1:
        scores["schema_accuracy"] = 2
    else:
        scores["schema_accuracy"] = 0
    findings["schema_accuracy"] = "Schema accuracy requires manual verification"

    total = sum(scores.values())
    return total, scores, findings


def score_crawler_access(robots_data, llms_data, sitemap_exists, rubric_checks):
    """Score the crawler access dimension (15 pts)."""
    scores = {}
    findings = {}

    # robots_txt_ai_bots (6 pts)
    if robots_data.get("exists"):
        allowed = robots_data.get("allowed_count", 0)
        total = robots_data.get("total_crawlers", len(AI_CRAWLERS))
        if allowed >= total:
            scores["robots_txt_ai_bots"] = 6
        elif allowed >= total * 0.7:
            scores["robots_txt_ai_bots"] = 4
        elif allowed >= total * 0.4:
            scores["robots_txt_ai_bots"] = 2
        else:
            scores["robots_txt_ai_bots"] = 0
        blocked_crawlers = [
            name for name, info in robots_data.get("crawlers", {}).items()
            if not info.get("allowed")
        ]
        findings["robots_txt_ai_bots"] = (
            f"{allowed}/{total} AI crawlers allowed" +
            (f". Blocked: {', '.join(blocked_crawlers)}" if blocked_crawlers else "")
        )
    else:
        scores["robots_txt_ai_bots"] = 6  # No robots.txt = all allowed
        findings["robots_txt_ai_bots"] = "No robots.txt found (all crawlers allowed by default)"

    # llms_txt (1 pt) — downgraded March 2026: no measurable citation impact (ALLMO.ai study)
    if llms_data.get("exists"):
        scores["llms_txt"] = 1
    else:
        scores["llms_txt"] = 0
    findings["llms_txt"] = f"llms.txt: {'exists' if llms_data.get('exists') else 'not found'} (no measurable citation impact as of March 2026)"

    # sitemap_xml (3 pts)
    scores["sitemap_xml"] = 3 if sitemap_exists else 0
    findings["sitemap_xml"] = f"sitemap.xml: {'found' if sitemap_exists else 'not found'}"

    # ssr_or_static (5 pts) — upgraded March 2026: more important than llms.txt
    scores["ssr_or_static"] = 2  # Conservative default
    findings["ssr_or_static"] = "Server rendering check requires manual verification"

    total = sum(scores.values())
    return total, scores, findings


def score_multiplatform(platform_data, rubric_checks):
    """Score multi-platform presence (15 pts). Platform data comes from Claude's Perplexity research."""
    scores = {}
    findings = {}

    # These are populated by Claude during the audit orchestration
    reddit = platform_data.get("reddit", {})
    youtube = platform_data.get("youtube", {})
    linkedin = platform_data.get("linkedin", {})
    third_party = platform_data.get("third_party", {})

    scores["reddit_presence"] = reddit.get("score", 0)
    findings["reddit_presence"] = reddit.get("finding", "Not checked yet — requires Perplexity research")

    scores["youtube_presence"] = youtube.get("score", 0)
    findings["youtube_presence"] = youtube.get("finding", "Not checked yet — requires Perplexity research")

    scores["linkedin_presence"] = linkedin.get("score", 0)
    findings["linkedin_presence"] = linkedin.get("finding", "Not checked yet — requires Perplexity research")

    scores["third_party_mentions"] = third_party.get("score", 0)
    findings["third_party_mentions"] = third_party.get("finding", "Not checked yet — requires Perplexity research")

    total = sum(scores.values())
    return total, scores, findings


def score_entity_clarity(entity_data, rubric_checks, alignment_data=None):
    """Score entity clarity (10 pts). Entity data comes from page analysis + Claude assessment.

    Sub-scores:
        alignment (3 pts) — entity-message alignment: does the site match what the business actually does?
        consistent_naming (3 pts)
        author_credentials (2 pts)
        linked_profiles (2 pts)

    The alignment sub-score replaces the former about_page sub-score. If alignment_data is not
    provided (no business context file was given), it falls back to the legacy about_page score.
    """
    scores = {}
    findings = {}

    # Alignment (3 pts) — replaces about_page
    if alignment_data and alignment_data.get("alignment_score") is not None:
        raw = alignment_data["alignment_score"]  # 0-10 scale from audit_alignment.py
        # Map 0-10 alignment score to 0-3 pts
        if raw >= 8:
            scores["alignment"] = 3
        elif raw >= 5:
            scores["alignment"] = 2
        elif raw >= 3:
            scores["alignment"] = 1
        else:
            scores["alignment"] = 0

        tier = alignment_data.get("alignment_tier", "")
        finding_parts = [f"Entity-message alignment: {raw}/10 ({tier})"]
        gap_count = len(alignment_data.get("gaps", []))
        if gap_count:
            finding_parts.append(f"{gap_count} signal gap(s) detected")
        top_findings = alignment_data.get("findings", [])[:2]
        if top_findings:
            finding_parts.append("; ".join(top_findings))
        findings["alignment"] = ". ".join(finding_parts)
    else:
        # Fallback to legacy about_page scoring when no alignment data is available
        scores["alignment"] = min(3, entity_data.get("about_page_score", 0))
        findings["alignment"] = entity_data.get(
            "about_page_finding",
            "Entity-message alignment not assessed (no business context provided). Fell back to about-page check."
        )

    scores["consistent_naming"] = entity_data.get("naming_score", 0)
    findings["consistent_naming"] = entity_data.get("naming_finding", "Not assessed yet")

    scores["author_credentials"] = entity_data.get("author_score", 0)
    findings["author_credentials"] = entity_data.get("author_finding", "Not assessed yet")

    scores["linked_profiles"] = entity_data.get("profiles_score", 0)
    findings["linked_profiles"] = entity_data.get("profiles_finding", "Not assessed yet")

    total = sum(scores.values())
    return total, scores, findings


def score_ai_visibility(visibility_data, rubric_checks):
    """Score current AI visibility (10 pts). Comes from Claude's Perplexity checks."""
    scores = {}
    findings = {}

    scores["perplexity_mentions"] = visibility_data.get("perplexity_score", 0)
    findings["perplexity_mentions"] = visibility_data.get("perplexity_finding", "Not checked yet")

    scores["search_ai_overview"] = visibility_data.get("aio_score", 0)
    findings["search_ai_overview"] = visibility_data.get("aio_finding", "Not checked yet")

    total = sum(scores.values())
    return total, scores, findings


def detect_business_type(crawl_data):
    """Auto-detect business type from crawl data for tailored recommendations.

    Checks multiple content sources: page content/markdown fields, page URLs,
    site-level metadata, findings text, and the brand description from meta tags.
    Also checks if business_type was explicitly provided in the crawl data.
    """
    # If explicitly provided, use it
    explicit = crawl_data.get("business_type")
    if explicit and explicit != "unknown":
        return explicit, {"explicit": 1}

    pages = crawl_data.get("page_analyses", [])

    # Gather ALL text sources — content, markdown, findings, metadata, URLs
    content_parts = []
    url_parts = []
    for p in pages:
        # Direct content
        content_parts.append(p.get("content", "") or "")
        content_parts.append(p.get("markdown", "") or "")
        # Findings text (always present even when content is stripped)
        findings = p.get("findings", {})
        if isinstance(findings, dict):
            for v in findings.values():
                if isinstance(v, str):
                    content_parts.append(v)
                elif isinstance(v, list):
                    content_parts.extend(str(x) for x in v)
        # URL
        url_parts.append(p.get("url", ""))

    # Also check site-level metadata
    meta_desc = crawl_data.get("meta_description", "")
    brand_desc = crawl_data.get("brand_description", "")
    content_parts.extend([meta_desc, brand_desc])

    # Also check sitemap URLs if available
    sitemap_urls = crawl_data.get("sitemap_urls", [])
    url_parts.extend(sitemap_urls)

    all_content = " ".join(content_parts).lower()
    all_urls = " ".join(url_parts).lower()

    signals = {
        "saas": 0,
        "agency": 0,
        "ecommerce": 0,
        "local_service": 0,
        "publisher": 0,
    }

    # SaaS signals
    for s in ["pricing", "free trial", "sign up", "sign-up", "signup", "demo",
              "/features", "/integrations", "/docs", "/api", "api ", "dashboard",
              "subscribe", "plan", "per month", "/mo", "saas", "platform",
              "start free", "get started free", "log in", "login"]:
        if s in all_content or s in all_urls:
            signals["saas"] += 1

    # Agency/Consultancy signals
    for s in ["case study", "case-study", "case studies", "portfolio", "our work",
              "client", "consulting", "consultancy", "services", "/industries",
              "team", "our approach", "framework", "methodology", "strategy call",
              "book a call", "schedule a call", "engagement", "retainer"]:
        if s in all_content or s in all_urls:
            signals["agency"] += 1

    # E-commerce signals — expanded with dollar signs, shop patterns, Shopify signals
    for s in ["/products", "/collections", "/cart", "add to cart", "add to bag",
              "shop now", "buy now", "price", "/shop", "shop men", "shop women",
              "shop all", "best sellers", "bestseller", "free shipping",
              "returns", "size guide", "quantity", "in stock", "out of stock",
              "shopify", "/product/"]:
        if s in all_content or s in all_urls:
            signals["ecommerce"] += 1
    # Check for dollar amounts (strong ecommerce signal)
    import re
    dollar_count = len(re.findall(r'\$\d+', all_content))
    if dollar_count >= 3:
        signals["ecommerce"] += 3
    elif dollar_count >= 1:
        signals["ecommerce"] += 1

    # Local service signals — expanded
    for s in ["phone", "address", "service area", "serving", "location",
              "directions", "map", "appointment", "call us", "call now",
              "emergency", "24/7", "licensed", "insured", "bonded",
              "free estimate", "near me", "local", "zip code",
              "schedule service", "request service", "our technicians"]:
        if s in all_content:
            signals["local_service"] += 1
    # Phone number pattern (strong local signal)
    phone_count = len(re.findall(r'\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', all_content))
    if phone_count >= 1:
        signals["local_service"] += 2

    # Publisher/Media signals
    for s in ["/blog", "/articles", "/topics", "/news", "author", "published",
              "editorial", "/category", "subscribe to", "newsletter",
              "read more", "min read", "by ", "written by"]:
        if s in all_content or s in all_urls:
            signals["publisher"] += 1

    # Return the top type, or "unknown" if no clear signals
    if max(signals.values()) == 0:
        return "unknown", signals

    detected = max(signals, key=signals.get)
    return detected, signals


def score_eeat(eeat_data, rubric_checks):
    """Score E-E-A-T signals (10 pts). E-E-A-T data comes from Claude's page analysis.

    Sub-scores:
        experience_signals (3 pts) — case studies, original data, first-hand accounts
        expertise_signals (3 pts) — credentials, accuracy, bylines
        trust_signals (4 pts) — contact info, policies, reviews, transparency
    """
    scores = {}
    findings = {}
    confidence = {}

    # Experience (3 pts)
    exp = eeat_data.get("experience", {})
    scores["experience_signals"] = min(3, exp.get("score", 0))
    findings["experience_signals"] = exp.get("finding", "Not assessed — requires content analysis")
    confidence["experience_signals"] = exp.get("confidence", "hypothesis")

    # Expertise (3 pts)
    ext = eeat_data.get("expertise", {})
    scores["expertise_signals"] = min(3, ext.get("score", 0))
    findings["expertise_signals"] = ext.get("finding", "Not assessed — requires content analysis")
    confidence["expertise_signals"] = ext.get("confidence", "hypothesis")

    # Trust (4 pts)
    trust = eeat_data.get("trust", {})
    scores["trust_signals"] = min(4, trust.get("score", 0))
    findings["trust_signals"] = trust.get("finding", "Not assessed — requires content analysis")
    confidence["trust_signals"] = trust.get("confidence", "hypothesis")

    total = sum(scores.values())
    return total, scores, findings, confidence


def score_geo_citability(citability_data, rubric_checks):
    """Score GEO passage-level citability (10 pts). Data from analyze_citability.py.

    Sub-scores:
        passage_optimization (4 pts) — sections at optimal 134-167 word length
        data_attribution (3 pts) — stats with source attribution
        section_structure (3 pts) — Q headings, lists, expert quotes
    """
    scores = {}
    findings = {}
    confidence = {}

    site_cit = citability_data.get("site_citability", {})
    avg_score = site_cit.get("average_score", 0)
    highly_citable_pct = site_cit.get("highly_citable_pct", 0)
    total_sections = site_cit.get("total_sections_analyzed", 0)

    # passage_optimization (4 pts)
    if highly_citable_pct >= 50:
        scores["passage_optimization"] = 4
    elif highly_citable_pct >= 25:
        scores["passage_optimization"] = 3
    elif highly_citable_pct >= 10:
        scores["passage_optimization"] = 2
    elif total_sections > 0:
        scores["passage_optimization"] = 1
    else:
        scores["passage_optimization"] = 0
    findings["passage_optimization"] = f"{highly_citable_pct}% of sections are highly citable ({total_sections} sections analyzed)"
    confidence["passage_optimization"] = "confirmed" if total_sections > 0 else "hypothesis"

    # data_attribution (3 pts) — derive from avg citability score
    if avg_score >= 7:
        scores["data_attribution"] = 3
    elif avg_score >= 4:
        scores["data_attribution"] = 2
    elif avg_score > 0:
        scores["data_attribution"] = 1
    else:
        scores["data_attribution"] = 0
    findings["data_attribution"] = f"Average section citability: {avg_score}/10"
    confidence["data_attribution"] = "confirmed" if total_sections > 0 else "hypothesis"

    # section_structure (3 pts) — from worst sections analysis
    worst = citability_data.get("worst_sections", [])
    low_pct = site_cit.get("low_citability_pct", 100)
    if low_pct <= 20:
        scores["section_structure"] = 3
    elif low_pct <= 50:
        scores["section_structure"] = 2
    elif low_pct <= 80:
        scores["section_structure"] = 1
    else:
        scores["section_structure"] = 0
    findings["section_structure"] = f"{low_pct}% of sections have low citability and need restructuring"
    confidence["section_structure"] = "confirmed" if total_sections > 0 else "hypothesis"

    total = sum(scores.values())
    return total, scores, findings, confidence


def assign_confidence(finding_source):
    """Assign confidence label based on how the finding was determined.

    Returns: 'confirmed' (script verified), 'likely' (inferred from strong signals),
             'hypothesis' (estimated or not directly measured)
    """
    # This is a utility used when building findings manually
    return finding_source


def score_technical(crawl_data, rubric_checks):
    """Score technical foundations (5 pts)."""
    scores = {}
    findings = {}

    scores["https"] = 2 if crawl_data.get("uses_https", False) else 0
    findings["https"] = "HTTPS: " + ("yes" if crawl_data.get("uses_https") else "no")

    # These require manual checks — default to partial
    scores["mobile_friendly"] = 1  # Conservative default
    findings["mobile_friendly"] = "Mobile-friendly check requires manual verification"

    scores["page_speed"] = 0  # Can't measure without Lighthouse
    findings["page_speed"] = "Page speed check requires Lighthouse or similar tool"

    # Clean URLs — check from crawled pages
    pages = crawl_data.get("page_analyses", [])
    messy_urls = sum(1 for p in pages if '?' in p.get("url", "") and 'utm' not in p.get("url", "").lower())
    scores["clean_urls"] = 1 if messy_urls == 0 else 0
    findings["clean_urls"] = f"Clean URLs: {len(pages) - messy_urls}/{len(pages)} pages"

    total = sum(scores.values())
    return total, scores, findings


AI_CRAWLERS = {
    # OpenAI — three tiers
    "GPTBot": "OpenAI (training)",
    "OAI-SearchBot": "OpenAI (search indexing)",
    "ChatGPT-User": "OpenAI (retrieval)",
    # Anthropic — three tiers (split March 2026)
    "ClaudeBot": "Anthropic (training)",
    "Claude-SearchBot": "Anthropic (search indexing)",
    "Claude-User": "Anthropic (retrieval)",
    # Perplexity — two tiers
    "PerplexityBot": "Perplexity (indexing)",
    "Perplexity-User": "Perplexity (retrieval)",
    # Google / ByteDance / Apple
    "Google-Extended": "Google Gemini",
    "Bytespider": "ByteDance",
    "Applebot-Extended": "Apple",
}


def determine_tier(score, rubric):
    """Determine the tier based on overall score."""
    tiers = rubric.get("tiers", {})
    if score >= tiers.get("ai_ready", {}).get("min_score", 80):
        return "ai_ready", tiers["ai_ready"]
    elif score >= tiers.get("partially_ready", {}).get("min_score", 60):
        return "partially_ready", tiers["partially_ready"]
    elif score >= tiers.get("significant_gaps", {}).get("min_score", 40):
        return "significant_gaps", tiers["significant_gaps"]
    else:
        return "not_ready", tiers["not_ready"]


def generate_priority_fixes(dimension_scores, dimension_findings, business_type="unknown", crawl_data=None):
    """Generate priority fixes ordered by impact, tailored to business type.

    Each fix includes:
    - confidence: confirmed/likely/hypothesis
    - evidence: the specific finding that triggered this recommendation
    - what_not_to_do: common mistake to avoid (prevents generic/dumb advice)
    """
    fixes = []
    crawl_data = crawl_data or {}
    agg = crawl_data.get("site_aggregates", {})
    entity_data = crawl_data.get("entity_data", {})
    page_analyses = crawl_data.get("page_analyses", [])

    cs_scores = dimension_findings.get("content_structure", {}).get("scores", {})
    cs_findings = dimension_findings.get("content_structure", {}).get("findings", {})
    ca_findings = dimension_findings.get("crawler_access", {}).get("findings", {})
    geo_scores = dimension_findings.get("geo_citability", {}).get("scores", {})
    eeat_scores = dimension_findings.get("eeat_signals", {}).get("scores", {})

    # Crawler access — if blocked, nothing else matters
    if dimension_scores.get("crawler_access", 0) < 10:
        fixes.append({
            "priority": 1,
            "dimension": "Crawler Access",
            "action": "Update robots.txt to explicitly allow AI crawlers (GPTBot, ClaudeBot, PerplexityBot, OAI-SearchBot)",
            "impact": "Blocking AI crawlers = invisible to AI search. This is pass/fail.",
            "effort": "low",
            "confidence": "confirmed",
            "evidence": ca_findings.get("robots_txt_ai_bots", ""),
            "what_not_to_do": "Don't just remove robots.txt entirely — explicitly allow AI bots while keeping other crawler rules intact."
        })

    # Schema markup — highest ROI technical fix
    if dimension_scores.get("schema_markup", 0) < 12:
        # Tailor schema recommendations by business type
        schema_recs = {
            "agency": "Organization, Service, Person (team members), Review/AggregateRating",
            "saas": "Organization, SoftwareApplication, Product, Offer, Review",
            "ecommerce": "Product, Offer, AggregateRating, BreadcrumbList, Organization",
            "local_service": "LocalBusiness, Service, Review, AggregateRating, GeoCoordinates",
            "publisher": "Article, BlogPosting, Person (authors), Organization, BreadcrumbList",
        }
        rec_types = schema_recs.get(business_type, "Organization, Article, Service")

        fixes.append({
            "priority": 2,
            "dimension": "Schema Markup",
            "action": f"Add JSON-LD structured data: {rec_types}. NEVER use HowTo (deprecated Sept 2023). FAQ schema only has GEO benefit for commercial sites (no Google rich result since Aug 2023).",
            "impact": "Significantly higher AI citation rate with proper schema (industry consensus: 2-3x)",
            "effort": "medium",
            "confidence": "confirmed",
            "evidence": cs_findings.get("json_ld_present", dimension_findings.get("schema_markup", {}).get("findings", {}).get("json_ld_present", "")),
            "what_not_to_do": "Don't add FAQPage schema expecting Google rich results on a commercial site — that was restricted in Aug 2023. The Q&A content structure still helps for AI citation though."
        })

    # Answer-first content — but NOT replacing branding
    if cs_scores.get("answer_first", 0) < 5:
        fixes.append({
            "priority": 3,
            "dimension": "Content Structure",
            "action": "Add a 40-60 word answer-first paragraph BELOW your hero/tagline section on key pages. This tells AI models what you do without replacing your branding.",
            "impact": "Significantly more AI citations for answer-first content (GEO research consensus)",
            "effort": "medium",
            "confidence": "confirmed",
            "evidence": cs_findings.get("answer_first", ""),
            "what_not_to_do": "Do NOT replace brand slogans or hero taglines. Those serve human visitors. Add the AI-readable paragraph after the hero section, not instead of it."
        })

    # GEO citability — passage-level optimization
    if dimension_scores.get("geo_citability", 0) < 6:
        fixes.append({
            "priority": 4,
            "dimension": "GEO Citability",
            "action": "Restructure content sections to 134-167 words each, with statistics and source attributions. Each section should be extractable as a standalone answer.",
            "impact": "Optimal passage length + attribution = highest AI citation probability",
            "effort": "medium-high",
            "confidence": "confirmed" if geo_scores.get("passage_optimization", 0) > 0 else "likely",
            "evidence": dimension_findings.get("geo_citability", {}).get("findings", {}).get("passage_optimization", ""),
            "what_not_to_do": "Don't mechanically split every paragraph to exactly 150 words. Optimize the informational sections — leave testimonials, CTAs, and branding sections alone."
        })

    # E-E-A-T — experience signals (the AI differentiator)
    if dimension_scores.get("eeat_signals", 0) < 6:
        eeat_recs = {
            "agency": "Add case studies with specific client results (before/after metrics), team credential pages, and methodology descriptions with real project examples.",
            "saas": "Add customer case studies with specific metrics, founder/team expertise pages, and product comparison content with original benchmark data.",
            "ecommerce": "Add product review content with real usage photos, buying guides with first-hand testing, and transparent return/warranty policies.",
            "local_service": "Add before/after project photos, customer testimonials with specific details, certifications/licenses page, and community involvement.",
            "publisher": "Add author bio pages with credentials, original research/data, expert interviews, and transparent editorial policies.",
        }
        rec = eeat_recs.get(business_type, "Add case studies, team credentials, and original data/research to demonstrate first-hand experience.")

        fixes.append({
            "priority": 5,
            "dimension": "E-E-A-T Signals",
            "action": rec,
            "impact": "Dec 2025 Google update: E-E-A-T applies to ALL competitive queries. Sites without experience signals saw 52-71% traffic drops.",
            "effort": "high",
            "confidence": eeat_scores.get("experience_signals", {}) if isinstance(eeat_scores.get("experience_signals"), str) else "likely",
            "evidence": dimension_findings.get("eeat_signals", {}).get("findings", {}).get("experience_signals", ""),
            "what_not_to_do": "Don't fake experience with AI-generated case studies. Google's systems detect this. Use real client work, real numbers, real photos."
        })

    # In-text citations
    if cs_scores.get("in_text_citations", 0) < 2:
        fixes.append({
            "priority": 6,
            "dimension": "Content Structure",
            "action": "Add statistics with source attributions throughout content. Format: '[Specific number] ([Source], [Year])'",
            "impact": "Passages with source attribution have significantly higher AI citation rates (GEO research consensus)",
            "effort": "medium",
            "confidence": "confirmed",
            "evidence": cs_findings.get("in_text_citations", ""),
            "what_not_to_do": "Don't add fake or outdated statistics. AI models cross-reference claims. Use reputable, recent sources."
        })

    # Multi-platform presence
    if dimension_scores.get("multiplatform_presence", 0) < 8:
        fixes.append({
            "priority": 7,
            "dimension": "Multi-Platform Presence",
            "action": "Build presence on Reddit (~24% of Perplexity responses cite it), YouTube (0.737 correlation with AI citations — strongest signal), and LinkedIn (#2 most-cited domain in AI search — ALM Corp 2026). Most brand citations in AI come from third-party sources, not your own site.",
            "impact": "Strong correlation between multi-platform presence (4+) and AI citation frequency",
            "effort": "high (ongoing)",
            "confidence": "likely",
            "evidence": dimension_findings.get("multiplatform_presence", {}).get("findings", {}),
            "what_not_to_do": "Don't just create profiles and abandon them. Active participation (Reddit comments, YouTube content, LinkedIn posts) drives citations."
        })

    # llms.txt
    if "not found" in ca_findings.get("llms_txt", ""):
        fixes.append({
            "priority": 8,
            "dimension": "Crawler Access",
            "action": "Create /llms.txt at domain root — structured guide for AI crawlers describing your site, key pages, and value proposition.",
            "impact": "No measurable citation impact as of March 2026 (ALLMO.ai study). Low effort, safe to implement but don't expect visibility gains.",
            "effort": "low",
            "confidence": "likely",
            "evidence": "llms.txt not found at domain root",
            "what_not_to_do": "Don't stuff keywords into llms.txt. It's for AI crawlers — be clear and factual about what your site offers."
        })

    # FAQ section — Q&A content is the most extractable format for AI models
    faq_score = cs_scores.get("faq_for_geo", 0)
    if faq_score < 3:
        fixes.append({
            "priority": 5,  # High priority — FAQ content directly feeds AI Q&A pipelines
            "dimension": "Content Structure",
            "action": "Add an FAQ section with 5-8 real questions your prospects ask. Each answer should be 40-80 words, lead with the direct answer, and include one specific number or data point. Q&A pairs are the most extractable content format for AI models.",
            "impact": "FAQ content directly feeds ChatGPT/Perplexity Q&A pipelines. Combined with FAQPage JSON-LD schema, this is one of the highest-leverage content additions for AI citation.",
            "effort": "medium",
            "confidence": "confirmed",
            "evidence": cs_findings.get("faq_for_geo", dimension_findings.get("schema_markup", {}).get("findings", {}).get("faq_for_geo", "")),
            "what_not_to_do": "Don't write generic FAQs that nobody actually asks. Use real questions from sales calls, support tickets, and search queries. AI models can tell when FAQ content is filler."
        })

    # Expert quotes
    if cs_scores.get("expert_quotes", 0) == 0:
        fixes.append({
            "priority": 9,
            "dimension": "Content Structure",
            "action": "Add named expert quotes with credentials. Use real quotes from team members, clients, or industry experts.",
            "impact": "Expert quotes improve AI trust and citation likelihood (GEO research consensus)",
            "effort": "medium",
            "confidence": "confirmed",
            "evidence": cs_findings.get("expert_quotes", ""),
            "what_not_to_do": "Don't invent quotes or attribute generic statements to unnamed experts. AI models check attribution consistency."
        })

    # Sitemap.xml missing
    if not crawl_data.get("sitemap_exists", True):
        fixes.append({
            "priority": 3,
            "dimension": "Crawler Access",
            "action": "Create a sitemap.xml and submit it to Google Search Console. A sitemap helps AI crawlers discover all your pages efficiently.",
            "impact": "Sitemaps are table stakes for crawlability. Without one, AI crawlers may miss pages entirely.",
            "effort": "low",
            "confidence": "confirmed",
            "evidence": "sitemap.xml not found (404)",
            "what_not_to_do": "Don't just generate a sitemap once and forget it. Auto-generate it from your CMS/build process so new pages are always included."
        })

    # About page / entity clarity fixes
    about_score = entity_data.get("about_page_score", 3)
    if about_score < 2:
        fixes.append({
            "priority": 6,
            "dimension": "Entity Clarity",
            "action": "Create a dedicated About page with founder/team bios, credentials, company story, and years of experience. AI models need to confidently identify WHO you are before citing you.",
            "impact": "AI models build entity graphs from About pages. Without one, your brand is indistinguishable from thousands of generic sites.",
            "effort": "medium",
            "confidence": "confirmed",
            "evidence": entity_data.get("about_page_finding", "No About page found"),
            "what_not_to_do": "Don't write a generic 'we are passionate about...' About page. Include specific credentials, years of experience, named team members, and real project history."
        })

    # Social profile links missing
    profiles_score = entity_data.get("profiles_score", 2)
    if profiles_score < 2:
        fixes.append({
            "priority": 8,
            "dimension": "Entity Clarity",
            "action": "Add visible links to your LinkedIn, YouTube, and Twitter/X profiles in your site footer and About page. Include these URLs in your Organization schema sameAs field.",
            "impact": "Linked social profiles help AI models verify your entity identity and cross-reference your brand across platforms.",
            "effort": "low",
            "confidence": "confirmed",
            "evidence": entity_data.get("profiles_finding", "No social profile links found on site"),
            "what_not_to_do": "Don't link to empty or abandoned social profiles. Only link profiles where you're actively posting — dead profiles hurt more than help."
        })

    # Author credentials missing
    author_score = entity_data.get("author_score", 2)
    if author_score == 0:
        fixes.append({
            "priority": 7,
            "dimension": "Entity Clarity",
            "action": "Add author bylines with credentials to all content pages. Format: 'By [Name], [Title] at [Company]' with a link to their bio page.",
            "impact": "Author attribution is a key E-E-A-T signal. Content with named authors is more likely to be cited by AI models.",
            "effort": "low",
            "confidence": "confirmed",
            "evidence": entity_data.get("author_finding", "No author bylines found"),
            "what_not_to_do": "Don't use 'Admin' or 'Staff Writer' as author names. Use real people with real credentials."
        })

    # Content freshness — no pages have visible update dates
    pages_with_freshness = agg.get("pages_with_freshness", 0)
    total_pages = crawl_data.get("total_pages_analyzed", 1)
    if total_pages > 0 and pages_with_freshness == 0:
        fixes.append({
            "priority": 8,
            "dimension": "Content Structure",
            "action": "Add visible 'Last updated: [date]' or 'Updated [Month Year]' markers to all content pages. AI models use recency as a quality signal — stale content gets deprioritized.",
            "impact": "Content freshness is a ranking signal for both Google and AI models. Pages with visible dates are treated as more authoritative.",
            "effort": "low",
            "confidence": "confirmed",
            "evidence": f"0/{total_pages} pages have visible update dates",
            "what_not_to_do": "Don't add fake dates or auto-update timestamps without actually reviewing the content. AI models can detect when dates change but content doesn't."
        })

    # OG image / social meta missing
    pages_with_og = agg.get("pages_with_og_image", -1)
    if pages_with_og == 0:
        fixes.append({
            "priority": 7,
            "dimension": "Technical Foundations",
            "action": "Add Open Graph image tags (og:image) to all pages. Create a branded OG image (1200x630px) for social sharing. Ensure og:title, og:description, and twitter:card tags are also present.",
            "impact": "OG images drive click-through when your pages are shared on social media and messaging apps. Without them, shared links look broken and unprofessional — reducing the social amplification that feeds AI citation.",
            "effort": "low-medium",
            "confidence": "confirmed",
            "evidence": f"0/{total_pages} pages have og:image tags",
            "what_not_to_do": "Don't use a generic stock photo. Use a branded image with your logo and a clear value proposition. Each key page should have a unique OG image."
        })
    elif pages_with_og >= 0:
        # Check for incomplete social meta (has OG image but missing other tags)
        complete_social = agg.get("pages_with_complete_social", 0)
        if complete_social < total_pages and total_pages > 0:
            missing_pct = round((1 - complete_social / total_pages) * 100)
            if missing_pct > 30:
                fixes.append({
                    "priority": 9,
                    "dimension": "Technical Foundations",
                    "action": "Complete your social meta tags — ensure every page has og:title, og:description, og:image, and twitter:card. Incomplete social meta means broken previews when shared.",
                    "impact": "Social sharing drives third-party mentions, which are the #1 source of AI brand citations (85% come from third-party sources).",
                    "effort": "low",
                    "confidence": "confirmed",
                    "evidence": f"{missing_pct}% of pages have incomplete social meta tags",
                    "what_not_to_do": "Don't just duplicate your meta description into og:description. Write social-specific copy that's compelling in a feed context (shorter, punchier)."
                })

    return sorted(fixes, key=lambda x: x["priority"])[:15]


def run_scoring(crawl_data):
    """Run the full scoring pipeline with 9 dimensions (was 7)."""
    rubric = load_rubric()
    agg = crawl_data.get("site_aggregates", {})
    page_analyses = crawl_data.get("page_analyses", [])
    dimensions = rubric.get("dimensions", {})

    # Detect business type for tailored recommendations
    business_type, business_signals = detect_business_type(crawl_data)

    # Score each dimension
    cs_score, cs_scores, cs_findings = score_content_structure(
        agg, page_analyses, dimensions.get("content_structure", {}).get("checks", {})
    )
    sm_score, sm_scores, sm_findings = score_schema_markup(
        agg, page_analyses, dimensions.get("schema_markup", {}).get("checks", {})
    )
    ca_score, ca_scores, ca_findings = score_crawler_access(
        crawl_data.get("robots_txt", {}),
        crawl_data.get("llms_txt", {}),
        crawl_data.get("sitemap_exists", False),
        dimensions.get("crawler_access", {}).get("checks", {})
    )

    # Claude-provided dimensions
    mp_score, mp_scores, mp_findings = score_multiplatform(
        crawl_data.get("platform_data", {}),
        dimensions.get("multiplatform_presence", {}).get("checks", {})
    )
    ec_score, ec_scores, ec_findings = score_entity_clarity(
        crawl_data.get("entity_data", {}),
        dimensions.get("entity_clarity", {}).get("checks", {}),
        alignment_data=crawl_data.get("alignment_data")
    )
    av_score, av_scores, av_findings = score_ai_visibility(
        crawl_data.get("visibility_data", {}),
        dimensions.get("current_ai_visibility", {}).get("checks", {})
    )
    tech_score, tech_scores, tech_findings = score_technical(
        crawl_data, dimensions.get("technical_foundations", {}).get("checks", {})
    )

    # NEW: E-E-A-T scoring (10 pts)
    eeat_score, eeat_scores, eeat_findings, eeat_confidence = score_eeat(
        crawl_data.get("eeat_data", {}),
        dimensions.get("eeat_signals", {}).get("checks", {})
    )

    # NEW: GEO citability scoring (10 pts)
    geo_score, geo_scores, geo_findings, geo_confidence = score_geo_citability(
        crawl_data.get("citability_data", {}),
        dimensions.get("geo_citability", {}).get("checks", {})
    )

    # Overall score (now out of 120 — normalized to 0-100 for display)
    dimension_scores = {
        "content_structure": cs_score,
        "schema_markup": sm_score,
        "crawler_access": ca_score,
        "multiplatform_presence": mp_score,
        "entity_clarity": ec_score,
        "current_ai_visibility": av_score,
        "technical_foundations": tech_score,
        "eeat_signals": eeat_score,
        "geo_citability": geo_score,
    }
    raw_total = sum(dimension_scores.values())
    max_total = 120  # 25+20+15+15+10+10+5+10+10
    overall_score = round(raw_total / max_total * 100)

    # Determine tier (now against 0-100 normalized score)
    tier_key, tier_info = determine_tier(overall_score, rubric)

    # All findings with confidence labels
    all_findings = {
        "content_structure": {"scores": cs_scores, "findings": cs_findings},
        "schema_markup": {"scores": sm_scores, "findings": sm_findings},
        "crawler_access": {"scores": ca_scores, "findings": ca_findings},
        "multiplatform_presence": {"scores": mp_scores, "findings": mp_findings},
        "entity_clarity": {"scores": ec_scores, "findings": ec_findings},
        "current_ai_visibility": {"scores": av_scores, "findings": av_findings},
        "technical_foundations": {"scores": tech_scores, "findings": tech_findings},
        "eeat_signals": {"scores": eeat_scores, "findings": eeat_findings, "confidence": eeat_confidence},
        "geo_citability": {"scores": geo_scores, "findings": geo_findings, "confidence": geo_confidence},
    }

    # Generate priority fixes (pass business type and full crawl data for comprehensive fix detection)
    priority_fixes = generate_priority_fixes(dimension_scores, all_findings, business_type, crawl_data=crawl_data)

    result = {
        "domain": crawl_data.get("domain", ""),
        "brand_name": crawl_data.get("brand_name", ""),
        "audit_date": crawl_data.get("crawl_date", str(__import__('datetime').date.today())),
        "overall_score": overall_score,
        "raw_score": raw_total,
        "max_score": max_total,
        "tier": tier_key,
        "tier_label": tier_info.get("label", ""),
        "tier_description": tier_info.get("description", ""),
        "business_type": business_type,
        "business_type_signals": business_signals,
        "dimension_scores": dimension_scores,
        "dimension_max": {
            "content_structure": 25,
            "schema_markup": 20,
            "crawler_access": 15,
            "multiplatform_presence": 15,
            "entity_clarity": 10,
            "current_ai_visibility": 10,
            "technical_foundations": 5,
            "eeat_signals": 10,
            "geo_citability": 10,
        },
        "detailed_findings": all_findings,
        "priority_fixes": priority_fixes,
        "total_pages_analyzed": crawl_data.get("total_pages_analyzed", 0),
        "site_aggregates": agg,
        "page_analyses": page_analyses,
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="AI SEO Audit Scorer")
    parser.add_argument("--input", required=True, help="Path to crawl results JSON")
    parser.add_argument("--output", help="Output path (default: .tmp/audit_score_<domain>.json)")

    args = parser.parse_args()

    with open(args.input) as f:
        crawl_data = json.load(f)

    result = run_scoring(crawl_data)

    domain_slug = crawl_data.get("domain", "unknown").replace(".", "_")
    output_path = args.output or f".tmp/audit_score_{domain_slug}.json"

    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)

    print(json.dumps({
        "success": True,
        "output": output_path,
        "overall_score": result["overall_score"],
        "raw_score": result["raw_score"],
        "max_score": result["max_score"],
        "tier": result["tier_label"],
        "business_type": result.get("business_type", "unknown"),
        "dimensions": {k: f"{v}/{result['dimension_max'][k]}" for k, v in result["dimension_scores"].items()},
        "top_fix": result["priority_fixes"][0]["action"] if result["priority_fixes"] else "None"
    }, indent=2))


if __name__ == "__main__":
    main()
