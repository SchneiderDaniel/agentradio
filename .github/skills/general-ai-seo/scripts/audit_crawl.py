#!/usr/bin/env python3
"""
Tool: AI SEO Audit Crawler
Purpose: Crawl a website using Firecrawl MCP results (passed as JSON) and extract
         AI-readiness signals from each page.

This script processes pre-crawled page data (from Firecrawl MCP) and extracts:
- Schema markup (JSON-LD)
- Content structure signals (answer-first, stats, citations, quotes, FAQ)
- Technical signals (HTTPS, clean URLs)
- robots.txt and llms.txt analysis

Usage:
    # Claude orchestrates: Firecrawl MCP crawls -> saves to JSON -> this script analyzes
    python3 .claude/skills/ai-seo/scripts/audit_crawl.py --input crawled_pages.json --domain example.com

Input JSON format:
    {
        "domain": "example.com",
        "brand_name": "Example Co",
        "robots_txt": "...",
        "llms_txt": "..." or null,
        "sitemap_exists": true,
        "pages": [
            {
                "url": "https://example.com/page",
                "content": "markdown content...",
                "raw_html": "optional — raw HTML for schema detection (use on 3-5 key pages)",
                "metadata": { "title": "...", "description": "..." }
            }
        ]
    }

Output: JSON with per-page analysis + site-level findings
"""

import sys
import json
import re
import argparse
from pathlib import Path
from urllib.parse import urlparse

# AI crawler user-agents to check in robots.txt
AI_CRAWLERS = {
    "GPTBot": "OpenAI (ChatGPT)",
    "ChatGPT-User": "OpenAI (ChatGPT live search)",
    "Google-Extended": "Google (Gemini)",
    "ClaudeBot": "Anthropic (Claude)",
    "PerplexityBot": "Perplexity",
    "Bytespider": "ByteDance (TikTok)",
    "Applebot-Extended": "Apple Intelligence",
    "OAI-SearchBot": "OpenAI (SearchGPT)",
}

# Regex patterns for content analysis
STAT_PATTERN = re.compile(
    r'(?:\d+(?:\.\d+)?%|\$\d+(?:,\d{3})*(?:\.\d+)?[KMBTkmbt]?|\d+(?:,\d{3})+|\d+(?:\.\d+)?x)'
)
CITATION_PATTERN = re.compile(
    r'(?:according to|source:|cited by|per |study by|research from|data from|reported by)',
    re.IGNORECASE
)
QUOTE_PATTERNS = [
    # "quote text" — Name or (Name)
    re.compile(r'["\u201c].{20,200}["\u201d]\s*(?:[-\u2014]\s*\w+|\(\w+)', re.DOTALL),
    # "quote text" followed by Name · Title or Name, Title
    re.compile(r'["\u201c].{20,300}["\u201d]\s*\n?\s*[\w\s]+[\u00b7,]\s*[\w\s]+', re.DOTALL),
    # Testimonial: paragraph followed by attribution line (— Name, Title at Company)
    re.compile(r'\n.{40,400}\n\s*[-\u2014]\s*[\w\s]+[,\u00b7]\s*[\w\s]+', re.DOTALL),
]
FAQ_PATTERN = re.compile(
    r'(?:^|\n)(?:#+\s*)?(?:FAQ|Frequently Asked|Common Questions|Questions?\s+(?:about|on))',
    re.IGNORECASE
)
QUESTION_HEADING_PATTERN = re.compile(
    r'^#+\s+.*\?$',
    re.MULTILINE
)
# Broader question detection: accordion FAQs, bold questions, plain-text Q&A
QUESTION_TEXT_PATTERN = re.compile(
    r'(?:'
    r'^\*\*[^*]{10,}\?\*\*'              # **Bold question?**
    r'|^#{1,4}\s+.*\?$'                  # Any heading level ending in ?
    r'|^(?!#|\*\*).{15,120}\?\s*$'       # Plain-text question line (15-120 chars ending in ?)
    r')',
    re.MULTILINE
)
# Content freshness: date patterns in body text
CONTENT_DATE_PATTERN = re.compile(
    r'(?:Updated|Published|Modified|Reviewed|Last updated|Posted|Edited)'
    r'(?:\s+on)?\s*:?\s*'
    r'(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2})',
    re.IGNORECASE
)
JSON_LD_PATTERN = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE
)


def analyze_robots_txt(robots_txt):
    """Check which AI crawlers are allowed/blocked."""
    if not robots_txt:
        return {"exists": False, "crawlers": {}, "score_notes": "No robots.txt found"}

    results = {}
    lines = robots_txt.lower().split('\n')

    for crawler_name, description in AI_CRAWLERS.items():
        # Check for explicit disallow
        blocked = False
        allowed = True
        in_agent_block = False

        for line in lines:
            line = line.strip()
            if line.startswith('user-agent:'):
                agent = line.split(':', 1)[1].strip()
                in_agent_block = (agent == crawler_name.lower() or agent == '*')
            elif in_agent_block and line.startswith('disallow:'):
                path = line.split(':', 1)[1].strip()
                if path == '/' or path == '':
                    blocked = True

        results[crawler_name] = {
            "description": description,
            "allowed": not blocked,
            "status": "allowed" if not blocked else "blocked"
        }

    allowed_count = sum(1 for v in results.values() if v['allowed'])
    return {
        "exists": True,
        "crawlers": results,
        "allowed_count": allowed_count,
        "total_crawlers": len(AI_CRAWLERS),
        "score_notes": f"{allowed_count}/{len(AI_CRAWLERS)} AI crawlers allowed"
    }


def analyze_page_content(page):
    """Analyze a single page for AI-readiness signals."""
    url = page.get("url", "")
    content = page.get("content", "")
    metadata = page.get("metadata", {})

    if not content:
        return {
            "url": url,
            "page_type": classify_page_type(url),
            "word_count": 0,
            "findings": {"error": "No content available"},
            "has_schema": False,
            "schema_types": [],
            "answer_first": False,
            "stat_count": 0,
            "citation_count": 0,
            "quote_count": 0,
            "has_faq": False,
            "page_score": 0
        }

    words = content.split()
    word_count = len(words)

    # Check answer-first: does the first substantive paragraph directly address the topic?
    # Skip headings, nav elements, short lines (buttons/links), and lines under 15 words
    paragraphs = []
    for p in content.split('\n\n'):
        p = p.strip()
        if not p:
            continue
        # Skip headings
        if p.startswith('#'):
            continue
        # Skip very short lines (likely nav items, buttons, CTAs)
        if len(p.split()) < 15:
            continue
        # Skip lines that are just links
        if p.startswith('[') and p.endswith(')'):
            continue
        # Skip bullet lists
        if p.startswith('- ') or p.startswith('* ') or p.startswith('•'):
            continue
        paragraphs.append(p)

    first_para_words = len(paragraphs[0].split()) if paragraphs else 0
    # Answer-first means the first substantive paragraph is 20-80 words and makes
    # a direct claim (contains a verb, not just a tagline)
    answer_first = False
    if paragraphs and 20 <= first_para_words <= 80:
        first_para = paragraphs[0].lower()
        # Check it reads like a statement, not a tagline (has common verb patterns)
        has_verb = any(v in first_para for v in [
            ' is ', ' are ', ' was ', ' were ', ' has ', ' have ', ' helps ',
            ' turns ', ' provides ', ' offers ', ' enables ', ' delivers ',
            ' we ', ' you ', ' they ', ' it ', ' this ', ' that '
        ])
        answer_first = has_verb

    # Count statistics
    stat_matches = STAT_PATTERN.findall(content)
    stat_count = len(stat_matches)

    # Count citations/attributions
    citation_matches = CITATION_PATTERN.findall(content)
    citation_count = len(citation_matches)

    # Count expert quotes (check multiple patterns, deduplicate by position)
    quote_positions = set()
    for pattern in QUOTE_PATTERNS:
        for match in pattern.finditer(content):
            # Deduplicate by start position (within 50 chars)
            pos = match.start()
            if not any(abs(pos - existing) < 50 for existing in quote_positions):
                quote_positions.add(pos)
    quote_count = len(quote_positions)

    # Check for FAQ section
    has_faq = bool(FAQ_PATTERN.search(content))

    # Count question headings (markdown headings + accordion/bold/plain-text questions)
    question_headings = QUESTION_HEADING_PATTERN.findall(content)
    question_text_matches = QUESTION_TEXT_PATTERN.findall(content)
    # Deduplicate: question_headings are a subset of question_text_matches
    all_questions = set(q.strip() for q in question_headings)
    all_questions.update(q.strip() for q in question_text_matches)
    question_heading_count = len(all_questions)

    # Check for schema markup
    # Priority 1: Accept schema_types passed directly on the page dict
    # (allows Claude to pass detected schema types from raw HTML it reads separately)
    raw_html = page.get("raw_html", "")
    schema_types = list(page.get("schema_types", []))
    has_schema = bool(schema_types)

    # Priority 2: Parse JSON-LD from raw HTML if available
    if raw_html:
        json_ld_blocks = JSON_LD_PATTERN.findall(raw_html)
        for block in json_ld_blocks:
            try:
                schema_data = json.loads(block)
                if isinstance(schema_data, list):
                    for item in schema_data:
                        if '@type' in item:
                            schema_types.append(item['@type'])
                elif '@type' in schema_data:
                    schema_types.append(schema_data['@type'])
                has_schema = True
            except json.JSONDecodeError:
                pass

    # Priority 3: Fallback — detect schema from markdown content if raw_html empty
    if not has_schema and not raw_html and content:
        # Check for JSON-LD blocks that survived markdown conversion
        md_json_ld_blocks = JSON_LD_PATTERN.findall(content)
        for block in md_json_ld_blocks:
            try:
                schema_data = json.loads(block)
                if isinstance(schema_data, list):
                    for item in schema_data:
                        if '@type' in item:
                            schema_types.append(item['@type'])
                elif '@type' in schema_data:
                    schema_types.append(schema_data['@type'])
                has_schema = True
            except json.JSONDecodeError:
                pass

        # Check for schema indicator patterns in markdown text
        if not has_schema:
            schema_indicators = [
                (r'"@type"\s*:\s*"([^"]+)"', True),    # "@type": "Organization"
                (r'itemtype\s*=\s*"https?://schema\.org/([^"]+)"', True),   # itemtype="https://schema.org/..."
                (r'vocab\s*=\s*"https?://schema\.org"', False),  # vocab="https://schema.org"
            ]
            for pattern, extracts_type in schema_indicators:
                matches = re.findall(pattern, content, re.IGNORECASE)
                if matches:
                    has_schema = True
                    if extracts_type:
                        schema_types.extend(matches)

        # Check metadata for og: tags as indicator of structured data awareness
        if not has_schema and metadata:
            og_keys = [k for k in metadata if k.startswith('og:')]
            if len(og_keys) >= 3:
                # Multiple OG tags suggest structured data awareness but not full schema
                has_schema = False  # Don't count OG alone as schema
                # Still note it in schema_types for visibility
                schema_types.append("_og_tags_present")

    # Deduplicate schema types
    schema_types = list(dict.fromkeys(t for t in schema_types if not t.startswith('_')))

    # Content freshness (from metadata first, then scan body text)
    last_modified = metadata.get("last_modified") or metadata.get("dateModified") or metadata.get("og:updated_time")
    if not last_modified and content:
        date_matches = CONTENT_DATE_PATTERN.findall(content)
        if date_matches:
            last_modified = date_matches[-1]  # Use the last match (usually "Updated on" comes after "Published on")

    # Determine page type
    page_type = classify_page_type(url)

    # Calculate page-level score (simplified)
    page_score = 0
    if answer_first:
        page_score += 15
    if stat_count >= 3:
        page_score += 10
    elif stat_count >= 1:
        page_score += 5
    if citation_count >= 2:
        page_score += 10
    elif citation_count >= 1:
        page_score += 5
    if quote_count >= 1:
        page_score += 8
    if has_faq:
        page_score += 10
    if has_schema:
        page_score += 15
    if question_heading_count >= 2:
        page_score += 7
    if word_count >= 1000:
        page_score += 5
    if last_modified:
        page_score += 5

    # Social meta analysis (OG tags, Twitter cards)
    social_meta = {
        "has_og_title": bool(metadata.get("og:title")),
        "has_og_description": bool(metadata.get("og:description")),
        "has_og_image": bool(metadata.get("og:image") or metadata.get("ogImage")),
        "has_twitter_card": bool(metadata.get("twitter:card")),
        "has_twitter_image": bool(metadata.get("twitter:image")),
        "has_meta_description": bool(metadata.get("description")),
    }
    social_meta["complete"] = all([
        social_meta["has_og_title"],
        social_meta["has_og_description"],
        social_meta["has_og_image"],
        social_meta["has_twitter_card"],
    ])
    social_meta_score = sum([
        social_meta["has_og_title"],
        social_meta["has_og_description"],
        social_meta["has_og_image"],
        social_meta["has_twitter_card"],
        social_meta["has_twitter_image"],
        social_meta["has_meta_description"],
    ])

    findings = {
        "first_para_words": first_para_words,
        "stat_examples": stat_matches[:5],
        "citation_examples": citation_matches[:3],
        "question_headings": question_headings[:5],
        "schema_types_found": schema_types,
        "has_last_modified": bool(last_modified),
        "social_meta": social_meta,
    }

    return {
        "url": url,
        "page_type": page_type,
        "word_count": word_count,
        "content": content,  # Store full content for business type detection + optimizer
        "metadata": metadata,  # Pass through for downstream analysis (OG tags, etc.)
        "has_schema": has_schema,
        "schema_types": schema_types,
        "answer_first": answer_first,
        "stat_count": stat_count,
        "citation_count": citation_count,
        "quote_count": quote_count,
        "has_faq": has_faq,
        "question_heading_count": question_heading_count,
        "last_modified": last_modified,
        "social_meta": social_meta,
        "social_meta_score": social_meta_score,
        "page_score": min(page_score, 100),
        "findings": findings
    }


def classify_page_type(url):
    """Classify a URL into a page type."""
    path = urlparse(url).path.lower().rstrip('/')

    if path == '' or path == '/':
        return 'homepage'
    elif any(x in path for x in ['/about', '/team', '/our-story']):
        return 'about'
    elif any(x in path for x in ['/blog', '/post', '/article', '/news']):
        return 'blog_post'
    elif any(x in path for x in ['/service', '/solution', '/offering']):
        return 'service_page'
    elif any(x in path for x in ['/product', '/pricing', '/plan']):
        return 'product_page'
    elif any(x in path for x in ['/contact', '/get-in-touch']):
        return 'contact'
    elif any(x in path for x in ['/faq', '/help', '/support']):
        return 'faq'
    elif any(x in path for x in ['/case-study', '/case-studies', '/portfolio']):
        return 'case_study'
    else:
        return 'other'


def extract_eeat_signals(page_analyses):
    """Extract E-E-A-T signals from page content for automated scoring.

    Returns structured eeat_data dict compatible with audit_score.py's score_eeat().
    """
    all_content = " ".join(p.get("content", "") for p in page_analyses).lower()
    all_urls = " ".join(p.get("url", "") for p in page_analyses).lower()

    # --- Experience signals (3 pts) ---
    exp_score = 0
    exp_signals = []

    # Case study pages
    case_study_pages = sum(1 for p in page_analyses if p.get("page_type") == "case_study")
    if case_study_pages == 0:
        # Also check URLs and content for case study indicators
        case_study_pages = sum(1 for p in page_analyses
            if any(x in (p.get("url", "") + " " + p.get("content", "")[:200]).lower()
                   for x in ["case study", "case-study", "casestudy", "success story", "customer story"]))
    if case_study_pages >= 3:
        exp_score += 2
        exp_signals.append(f"{case_study_pages} case study pages found")
    elif case_study_pages >= 1:
        exp_score += 1
        exp_signals.append(f"{case_study_pages} case study page(s) found")

    # Specific metrics in content (before/after, percentage results, revenue figures)
    metric_patterns = [
        r'\d+\s*(?:qualified\s+)?(?:appointments?|meetings?|leads?|prospects?)',
        r'(?:€|\$|CHF)\s*[\d,]+(?:k|K)?\s*(?:revenue|turnover|contracts?|pipeline)',
        r'\d+%\s*(?:open|response|conversion|deliverability|interest)',
        r'\d+\s*(?:new\s+)?(?:customers?|clients?) signed',
    ]
    metric_count = sum(len(re.findall(p, all_content, re.IGNORECASE)) for p in metric_patterns)
    if metric_count >= 10:
        exp_score = 3
        exp_signals.append(f"{metric_count} specific result metrics across pages")
    elif metric_count >= 3:
        exp_score = max(exp_score, 2)
        exp_signals.append(f"{metric_count} specific result metrics found")

    # --- Expertise signals (3 pts) ---
    ext_score = 0
    ext_signals = []

    # Author bylines
    byline_patterns = [r'by\s+[A-Z][\w]+\s+[A-Z][\w]+', r'author:\s*\w+', r'founder|ceo|cto|director|manager|phd|dr\.']
    byline_count = sum(len(re.findall(p, all_content, re.IGNORECASE)) for p in byline_patterns)
    if byline_count >= 5:
        ext_score += 1
        ext_signals.append(f"Author bylines with credentials found ({byline_count} instances)")
    elif byline_count >= 1:
        ext_score += 1
        ext_signals.append(f"Some author attribution found")

    # External citations (reuse existing count)
    total_citations = sum(p.get("citation_count", 0) for p in page_analyses)
    if total_citations >= 10:
        ext_score += 2
        ext_signals.append(f"{total_citations} external source citations across pages")
    elif total_citations >= 3:
        ext_score += 1
        ext_signals.append(f"{total_citations} external source citations found")

    # --- Trust signals (4 pts) ---
    trust_score = 0
    trust_signals = []

    # Customer testimonials (reuse quote detection)
    total_quotes = sum(p.get("quote_count", 0) for p in page_analyses)
    if total_quotes >= 3:
        trust_score += 1
        trust_signals.append(f"{total_quotes} customer testimonials/quotes detected")
    elif total_quotes >= 1:
        trust_score += 1
        trust_signals.append(f"{total_quotes} testimonial(s) found")

    # Contact page / privacy policy
    has_contact = any("contact" in p.get("url", "").lower() or "consultation" in p.get("url", "").lower() for p in page_analyses)
    has_privacy = any("privacy" in p.get("url", "").lower() or "terms" in p.get("url", "").lower() for p in page_analyses)
    if has_contact:
        trust_score += 1
        trust_signals.append("Contact/consultation page exists")
    if has_privacy:
        trust_score += 1
        trust_signals.append("Privacy policy/terms page exists")

    # Physical address / phone
    if any(p in all_content for p in ["street", "address", "canton", "headquarter", "based in", "office"]):
        trust_score += 1
        trust_signals.append("Physical address/location mentioned")

    return {
        "experience": {
            "score": min(3, exp_score),
            "finding": "; ".join(exp_signals) if exp_signals else "No experience signals detected",
            "confidence": "confirmed" if exp_signals else "hypothesis"
        },
        "expertise": {
            "score": min(3, ext_score),
            "finding": "; ".join(ext_signals) if ext_signals else "No expertise signals detected",
            "confidence": "confirmed" if ext_signals else "hypothesis"
        },
        "trust": {
            "score": min(4, trust_score),
            "finding": "; ".join(trust_signals) if trust_signals else "No trust signals detected",
            "confidence": "confirmed" if trust_signals else "hypothesis"
        }
    }


def analyze_site(data):
    """Run full site analysis."""
    domain = data.get("domain", "")
    brand_name = data.get("brand_name", "")
    pages = data.get("pages", [])

    # Analyze robots.txt
    robots_analysis = analyze_robots_txt(data.get("robots_txt", ""))

    # Check llms.txt
    llms_txt = data.get("llms_txt")
    llms_txt_analysis = {
        "exists": bool(llms_txt),
        "length": len(llms_txt) if llms_txt else 0,
        "well_structured": bool(llms_txt and '##' in llms_txt) if llms_txt else False
    }

    # Sitemap
    sitemap_exists = data.get("sitemap_exists", False)

    # Analyze each page
    page_analyses = [analyze_page_content(page) for page in pages]

    # Site-level aggregates
    total_pages = len(page_analyses)
    pages_with_schema = sum(1 for p in page_analyses if p['has_schema'])
    pages_with_answer_first = sum(1 for p in page_analyses if p['answer_first'])
    pages_with_stats = sum(1 for p in page_analyses if p['stat_count'] > 0)
    pages_with_citations = sum(1 for p in page_analyses if p['citation_count'] > 0)
    pages_with_quotes = sum(1 for p in page_analyses if p['quote_count'] > 0)
    pages_with_faq = sum(1 for p in page_analyses if p['has_faq'])

    # Collect all schema types found across pages
    all_schema_types = set()
    for p in page_analyses:
        all_schema_types.update(p['schema_types'])

    # Technical checks
    uses_https = domain.startswith('https') or any(
        p['url'].startswith('https') for p in page_analyses if p.get('url')
    )

    avg_page_score = (
        sum(p['page_score'] for p in page_analyses) / total_pages
        if total_pages > 0 else 0
    )

    # Extract E-E-A-T signals from content (only if not already provided)
    if "eeat_data" not in data:
        eeat_data = extract_eeat_signals(page_analyses)
    else:
        eeat_data = data["eeat_data"]

    # Count pages with question headings (for aggregate)
    pages_with_questions = sum(1 for p in page_analyses if p.get("question_heading_count", 0) >= 2)

    # Social meta aggregates
    pages_with_og_image = sum(1 for p in page_analyses if p.get("social_meta", {}).get("has_og_image"))
    pages_with_complete_social = sum(1 for p in page_analyses if p.get("social_meta", {}).get("complete"))
    pages_with_freshness = sum(1 for p in page_analyses if p.get("last_modified"))

    result = {
        "domain": domain,
        "brand_name": brand_name,
        "crawl_date": str(__import__('datetime').date.today()),
        "total_pages_analyzed": total_pages,
        "robots_txt": robots_analysis,
        "llms_txt": llms_txt_analysis,
        "sitemap_exists": sitemap_exists,
        "uses_https": uses_https,
        "eeat_data": eeat_data,
        "site_aggregates": {
            "pages_with_schema": pages_with_schema,
            "schema_coverage_pct": round(pages_with_schema / total_pages * 100, 1) if total_pages else 0,
            "all_schema_types": sorted(all_schema_types),
            "pages_with_answer_first": pages_with_answer_first,
            "answer_first_pct": round(pages_with_answer_first / total_pages * 100, 1) if total_pages else 0,
            "pages_with_stats": pages_with_stats,
            "pages_with_citations": pages_with_citations,
            "pages_with_quotes": pages_with_quotes,
            "pages_with_faq": pages_with_faq,
            "pages_with_og_image": pages_with_og_image,
            "pages_with_complete_social": pages_with_complete_social,
            "pages_with_freshness": pages_with_freshness,
            "avg_page_score": round(avg_page_score, 1)
        },
        "page_analyses": page_analyses
    }

    # Pass through ALL enrichment fields if provided (from MCP tools or audit_enrich.py)
    for key in [
        "platform_data", "entity_data", "visibility_data",
        "eeat_data", "citability_data", "alignment_data",
        "business_type", "meta_description", "brand_description",
        "sitemap_urls"
    ]:
        if key in data:
            result[key] = data[key]

    return result


def main():
    parser = argparse.ArgumentParser(description="AI SEO Audit Crawler")
    parser.add_argument("--input", required=True, help="Path to crawled pages JSON")
    parser.add_argument("--output", help="Output path (default: .tmp/audit_crawl_<domain>.json)")

    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    result = analyze_site(data)

    domain_slug = data.get("domain", "unknown").replace(".", "_")
    output_path = args.output or f".tmp/audit_crawl_{domain_slug}.json"

    # Ensure output directory exists
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(result, f, indent=2, default=str)

    print(json.dumps({
        "success": True,
        "output": output_path,
        "pages_analyzed": result["total_pages_analyzed"],
        "avg_page_score": result["site_aggregates"]["avg_page_score"]
    }, indent=2))


if __name__ == "__main__":
    main()
