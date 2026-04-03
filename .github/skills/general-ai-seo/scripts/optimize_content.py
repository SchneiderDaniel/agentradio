#!/usr/bin/env python3
"""
Tool: Section-Aware AI Content Optimizer
Purpose: Analyze page content section-by-section and generate evidence-grounded
         recommendations that respect each section's intent.

Key principle: Every recommendation must be backed by evidence from the page,
and must respect the section type (don't optimize branding sections for citability,
don't remove slogans, don't restructure testimonials).

Section types and how they're handled:
    - hero/branding: NEVER modify. Suggest adding content AFTER, not replacing.
    - informational: Primary optimization target. Citability, stats, attribution.
    - service/product: Optimize for entity clarity and schema readiness.
    - social_proof: Leave structure alone. Suggest adding schema (Review, AggregateRating).
    - cta/conversion: Leave alone. Note if missing.
    - faq: Optimize Q&A format, ensure answer-first in each answer.
    - navigation/footer: Skip entirely.

Usage:
    python3 .claude/skills/ai-seo/scripts/optimize_content.py --input page_content.json

Input JSON format:
    {
        "url": "https://example.com/page",
        "title": "Page Title",
        "content": "Full markdown content...",
        "metadata": {"description": "...", "author": "..."},
        "brand_name": "Example Co",
        "business_type": "agency",  # from audit auto-detection
        "target_queries": ["query 1", "query 2"],  # optional
        "audit_gaps": [...]  # optional: gaps from audit to address
    }

Output: Section-by-section analysis with targeted recommendations
"""

import sys
import json
import re
import argparse
from pathlib import Path
from datetime import date


# Section classification patterns
HERO_PATTERNS = [
    r'(?:stop|start|transform|discover|unlock|build|grow|scale|get)',
    r'(?:we help|we turn|we make|we build|we deliver)',
    r'(?:the future of|the smart way|the better way)',
]

SOCIAL_PROOF_PATTERNS = [
    r'(?:testimonial|what (?:our )?(?:clients?|customers?) say|review)',
    r'(?:trusted by|used by|loved by|chosen by)',
    r'(?:case stud|success stor|results)',
]

CTA_PATTERNS = [
    r'(?:get started|sign up|book|schedule|contact|request|try|start)',
    r'(?:free (?:trial|demo|consultation|audit))',
    r'(?:ready to|let\'s|want to)',
]

FAQ_PATTERNS = [
    r'(?:faq|frequently asked|common questions|q\s*&\s*a)',
]

NAV_PATTERNS = [
    r'(?:menu|navigation|footer|copyright|privacy|terms)',
    r'(?:©|\d{4}\s+all rights)',
]

SERVICE_PATTERNS = [
    r'(?:our services|what we (?:do|offer)|how (?:we|it) works)',
    r'(?:features|solutions|capabilities|offerings)',
    r'(?:pricing|plans|packages)',
]

STAT_PATTERN = re.compile(
    r'(?:\d+(?:\.\d+)?%|\$\d+(?:,\d{3})*(?:\.\d+)?[KMBTkmbt]?|\d+(?:,\d{3})+|\d+(?:\.\d+)?x)'
)
CITATION_PATTERN = re.compile(
    r'(?:according to|source:|cited by|per |study by|research from|data from|reported by)',
    re.IGNORECASE
)
QUOTE_PATTERN = re.compile(
    r'["\u201c].{20,200}["\u201d]\s*(?:[-\u2014]\s*\w+|\(\w+)',
    re.DOTALL
)


def classify_section(heading, content, position, total_sections):
    """Classify a section's intent based on heading, content, and position."""
    heading_lower = heading.lower()
    content_lower = content.lower()
    combined = f"{heading_lower} {content_lower[:200]}"

    # Position-based heuristics
    is_first = position == 0
    is_last = position >= total_sections - 2

    # Navigation/footer (skip these)
    if is_last and any(re.search(p, combined) for p in NAV_PATTERNS):
        return "navigation"

    # Hero/branding (always first, short, punchy)
    if is_first and len(content.split()) < 100:
        return "hero"
    if any(re.search(p, combined, re.IGNORECASE) for p in HERO_PATTERNS) and is_first:
        return "hero"

    # FAQ
    if any(re.search(p, heading_lower) for p in FAQ_PATTERNS):
        return "faq"

    # Ecommerce product/catalog sections (check BEFORE social proof to avoid misclassifying)
    ecommerce_patterns = [
        r'(?:best seller|bestseller|new arrival|shop (?:men|women|all|now))',
        r'(?:featured product|trending|collection|category)',
        r'(?:as seen in|press|media)',
        r'\$\d+',
    ]
    if any(re.search(p, combined, re.IGNORECASE) for p in ecommerce_patterns):
        return "social_proof"  # Use social_proof (don't restructure, just add schema)

    # Social proof — but NOT if heading is a product feature or the word appears in a
    # non-testimonial context (e.g., "social media" is a feature, not social proof;
    # "results" in a product description is not a testimonial)
    feature_exclusions = [
        "review pr", "code review", "pull request", "feature", "built for",
        "designed for", "powered by", "integrate", "social media",
        "ai that", "intelligence", "analytics", "marketing",
        "content", "competitive", "keyword", "rank", "seo",
    ]
    heading_is_feature = any(fw in heading_lower for fw in feature_exclusions)
    if not heading_is_feature and any(re.search(p, combined) for p in SOCIAL_PROOF_PATTERNS):
        # Double check: social proof should have testimonial indicators, not just the word "results"
        testimonial_confirms = ['"', '\u201c', 'said', 'told us', 'stars', 'rating',
                                'review', 'testimonial', 'partner', 'chose us']
        if any(tc in content_lower for tc in testimonial_confirms) or 'client' in heading_lower:
            return "social_proof"

    # CTA/conversion
    if any(re.search(p, combined, re.IGNORECASE) for p in CTA_PATTERNS) and len(content.split()) < 80:
        return "cta"

    # Service/product descriptions
    if any(re.search(p, combined, re.IGNORECASE) for p in SERVICE_PATTERNS):
        return "service"

    # Default: informational
    return "informational"


def _generate_natural_question(heading, section_type, business_type):
    """Generate a natural-sounding question heading, not a mechanical template.

    Returns None if no good question can be formed (skip the recommendation).
    """
    h = heading.lower().strip()

    # === SKIP RULES (return None = don't suggest a question) ===

    # Never turn slogans/taglines into questions
    skip_patterns = [
        # Brand/marketing phrases
        "best seller", "as seen in", "shop ", "featured", "new arrival",
        "our team", "meet the", "contact", "get in touch", "let's connect",
        "clients who", "trusted by", "join", "subscribe", "numbers we",
        # First-person pronouns — these are brand voice, not topics
        "we ", "we'", "our ", "my ",
        # Imperative mood / commands (slogans)
        "stay ", "lead with", "start ", "stop ", "discover ", "unlock ",
        "connect to", "track ", "make your",
    ]
    if any(p in h for p in skip_patterns):
        return None

    # Skip short marketing blurbs (under 4 words that aren't proper nouns/topics)
    words = heading.split()
    if len(words) <= 2 and not h[0].isupper():
        return None

    # Skip headings that are full sentences (contain verbs acting on objects)
    sentence_indicators = [" that ", " which ", " where ", " so ", " never ",
                          " creates ", " delivers ", " drives ", " ensures ",
                          " sees ", " helps you"]
    if any(si in h for si in sentence_indicators):
        return None

    # === BUSINESS-TYPE-SPECIFIC SUGGESTIONS ===

    # Service/product descriptions
    if section_type == "service":
        if any(w in h for w in ["service", "solution", "offering", "package"]):
            return f"What {heading} do you offer?"
        return f"How does {heading} work?"

    # Local service patterns
    if business_type == "local_service":
        if "emergency" in h:
            return f"Need {heading}?"
        if any(w in h for w in ["repair", "install", "maintenance", "service"]):
            return f"When do you need {heading.lower()}?"
        if len(words) <= 4:
            return f"What does {heading.lower()} include?"
        return None  # Skip long headings for local service

    # SaaS — only suggest for clearly topical headings, NOT product feature blurbs
    if business_type == "saas":
        # Proper topic headings (2-3 word noun phrases)
        if len(words) <= 3 and all(w[0].isupper() for w in words if len(w) > 2):
            if any(w in h for w in ["feature", "integration", "workflow", "analytics"]):
                return f"How does {heading} work?"
            # Known topic categories
            return f"What is {heading}?"
        # Everything else on SaaS pages — skip (product feature sub-headings, marketing copy)
        return None

    # Agency methodology/approach
    if business_type == "agency":
        if any(w in h for w in ["framework", "approach", "method", "process"]):
            # Avoid "How does the The X" — strip leading "the" if present
            clean = heading[4:] if h.startswith("the ") else heading
            return f"How does the {clean} work?"
        # 2-3 word topic headings only
        if len(words) <= 3:
            return f"What is {heading.lower()}?"
        return None

    # Ecommerce
    if business_type == "ecommerce":
        if any(w in h for w in ["material", "sustainability", "made from"]):
            return f"What makes {heading.lower()} different?"
        return None  # Most ecommerce headings shouldn't be questions

    # Generic fallback — ONLY for clean noun phrases (2-3 words, title case)
    if len(words) <= 3 and all(w[0].isupper() for w in words if len(w) > 3):
        return f"What is {heading}?"
    if any(w in h for w in ["how", "step", "process", "guide"]):
        return f"How does {heading.lower()} work?"

    # When in doubt, don't suggest — bad suggestions are worse than none
    return None


def analyze_section(heading, content, section_type, business_type):
    """Analyze a single section and generate section-appropriate recommendations."""
    words = content.split()
    word_count = len(words)
    stats = STAT_PATTERN.findall(content)
    citations = CITATION_PATTERN.findall(content)
    quotes = QUOTE_PATTERN.findall(content)
    has_list = bool(re.search(r'^\s*[-*•]\s', content, re.MULTILINE))
    has_table = '|' in content and content.count('|') >= 6

    result = {
        "heading": heading,
        "section_type": section_type,
        "word_count": word_count,
        "stats_count": len(stats),
        "citations_count": len(citations),
        "quotes_count": len(quotes),
        "has_list": has_list,
        "has_table": has_table,
        "recommendations": [],
        "do_not_touch": False,
    }

    # Sections we don't optimize
    if section_type in ("hero", "navigation", "cta"):
        result["do_not_touch"] = True
        if section_type == "hero":
            result["note"] = "Hero/branding section — preserved as-is. Recommendations for new content are placed AFTER this section."
        return result

    # Social proof: only suggest schema, don't restructure
    if section_type == "social_proof":
        result["recommendations"].append({
            "type": "schema_only",
            "action": "Add Review or AggregateRating JSON-LD schema to match this testimonial content",
            "evidence": f"Found social proof section with {word_count} words but no schema markup",
            "effort": "low",
            "impact": "Schema helps AI models understand and cite your credibility signals"
        })
        return result

    # FAQ: optimize Q&A format
    if section_type == "faq":
        questions = re.findall(r'^#+\s+(.+\?)', content, re.MULTILINE)
        if len(questions) < 3:
            result["recommendations"].append({
                "type": "expand_faq",
                "action": f"Expand FAQ section from {len(questions)} to 5-8 questions. Each answer should be 40-80 words and self-contained.",
                "evidence": f"Only {len(questions)} Q&A pairs found — AI models extract more value from 5+ pairs",
                "effort": "medium",
                "impact": "FAQ sections are primary sources for AI Q&A extraction"
            })

        # Check answer quality
        for q in questions:
            # Find the answer following this question
            q_pattern = re.escape(q)
            match = re.search(f'{q_pattern}\\s*\\n(.+?)(?=\\n#+|$)', content, re.DOTALL)
            if match:
                answer = match.group(1).strip()
                answer_words = len(answer.split())
                if answer_words > 100:
                    result["recommendations"].append({
                        "type": "shorten_faq_answer",
                        "action": f'Shorten answer to "{q[:50]}..." from {answer_words} to 40-80 words. Lead with the direct answer.',
                        "evidence": f"Answer is {answer_words} words — AI models prefer concise, extractable answers",
                        "effort": "low",
                        "impact": "Shorter answers are more likely to be cited verbatim"
                    })
        return result

    # Service sections: optimize for entity clarity + schema
    if section_type == "service":
        if len(stats) == 0:
            result["recommendations"].append({
                "type": "add_service_data",
                "action": "Add quantified results to service descriptions (e.g., '87% of clients see results in 90 days', 'saved $2.3M in operational costs')",
                "evidence": f"Service section has 0 statistics — AI models skip vague service descriptions",
                "effort": "medium",
                "impact": "+22% visibility per statistic added. Quantified claims get cited; vague ones don't."
            })

        result["recommendations"].append({
            "type": "schema_service",
            "action": "Add Service JSON-LD schema with name, description, provider, and areaServed",
            "evidence": "Service descriptions without schema are invisible to structured AI queries",
            "effort": "low",
            "impact": "Service schema enables direct matching when users ask AI about specific services"
        })
        return result

    # Informational sections: full optimization
    recs = []

    # Passage length optimization (134-167 word optimal for AI citation)
    if word_count > 250:
        recs.append({
            "type": "split_passage",
            "action": f"Split this {word_count}-word section into 2-3 sub-sections of 134-167 words each with H3 headings. Each sub-section should be self-contained.",
            "evidence": f"AI models extract passages of 134-167 words. This {word_count}-word section is too long for a single citation.",
            "effort": "medium",
            "impact": "Optimal passage length increases citation probability by 2.3x"
        })
    elif word_count < 80 and word_count > 20:
        recs.append({
            "type": "expand_passage",
            "action": f"Expand this {word_count}-word section to 134-167 words. Add a specific statistic and source attribution.",
            "evidence": f"Section is too short for AI citation ({word_count} words, need 134-167)",
            "effort": "low",
            "impact": "Below-threshold sections are skipped by AI extraction"
        })

    # Answer-first within section
    first_sentence = content.split('.')[0] if '.' in content else content[:100]
    is_answer_first = any(v in first_sentence.lower() for v in [
        ' is ', ' are ', ' was ', ' has ', ' provides ', ' enables ',
        ' helps ', ' means ', ' involves ', ' refers to '
    ])
    if not is_answer_first and word_count >= 50:
        recs.append({
            "type": "answer_first",
            "action": f'Start this section with a direct statement. Current opening: "{first_sentence[:80]}..."',
            "evidence": "Section doesn't start with a declarative statement — AI models prioritize direct answers",
            "effort": "low",
            "impact": "Answer-first sections get 2.3x more citations"
        })

    # Statistics
    if len(stats) == 0 and word_count >= 100:
        recs.append({
            "type": "add_stats",
            "action": "Add 1-2 statistics with source attribution. Format: '[Number] ([Source], [Year])'",
            "evidence": f"Zero statistics in {word_count}-word section",
            "effort": "medium",
            "impact": "+22% AI visibility per statistic"
        })

    # Citations
    if len(citations) == 0 and word_count >= 150:
        recs.append({
            "type": "add_citation",
            "action": "Add inline source attribution. Format: 'According to [Source], ...'",
            "evidence": f"No source attributions in {word_count}-word section",
            "effort": "low",
            "impact": "+115% visibility from in-text citations"
        })

    # Question heading — generate NATURAL questions, not mechanical templates
    if not heading.endswith('?') and not heading.lower().startswith(('what', 'how', 'why', 'when', 'where', 'who')):
        suggestion = _generate_natural_question(heading, section_type, business_type)
        if suggestion:
            recs.append({
                "type": "question_heading",
                "action": f'Consider rephrasing "{heading}" as: "{suggestion}"',
                "evidence": "Topic heading doesn't match query patterns — AI models match questions to question headings",
                "effort": "low",
                "impact": "Question headings align with how users query AI systems"
            })

    result["recommendations"] = recs
    return result


def split_into_sections(content):
    """Split markdown content into sections by H2/H3 headings."""
    sections = []
    current_heading = "Introduction"
    current_content = []

    for line in content.split('\n'):
        if line.startswith('## ') or line.startswith('### '):
            if current_content:
                sections.append({
                    "heading": current_heading,
                    "content": '\n'.join(current_content).strip()
                })
            current_heading = line.lstrip('#').strip()
            current_content = []
        else:
            current_content.append(line)

    if current_content:
        sections.append({
            "heading": current_heading,
            "content": '\n'.join(current_content).strip()
        })

    return sections


def generate_new_section_recommendations(sections, section_analyses, business_type, brand_name):
    """Recommend NEW sections that should be added (not modifications to existing ones)."""
    existing_types = {s["section_type"] for s in section_analyses}
    recs = []

    # Answer-first paragraph after hero
    hero_exists = "hero" in existing_types
    has_answer_para = any(
        s["section_type"] == "informational" and s.get("word_count", 0) >= 40
        for s in section_analyses[:3]  # Check first 3 sections
    )
    if hero_exists and not has_answer_para:
        recs.append({
            "type": "add_section",
            "position": "after_hero",
            "action": f"Add a 40-60 word answer-first paragraph BELOW the hero section that tells AI models exactly what {brand_name or 'this business'} does. Do NOT replace the hero tagline.",
            "evidence": "Hero section exists but no declarative paragraph follows — AI models skip taglines and look for substantive descriptions",
            "effort": "low",
            "impact": "2.3x citation boost. This is the single highest-impact change.",
            "example_format": f"{brand_name or 'Company'} is [what you are] that helps [who] achieve [what outcome]. [Quantified proof point]. [Differentiator]."
        })

    # FAQ section
    if "faq" not in existing_types:
        recs.append({
            "type": "add_section",
            "position": "before_cta",
            "action": "Add a FAQ section with 5-8 questions and concise (40-80 word) answers. Use question-format H3 headings.",
            "evidence": "No FAQ section found — these are primary targets for AI Q&A extraction",
            "effort": "medium",
            "impact": "FAQ sections directly feed AI answer extraction pipelines"
        })

    # Social proof (for agencies/SaaS especially)
    if "social_proof" not in existing_types and business_type in ("agency", "saas"):
        recs.append({
            "type": "add_section",
            "position": "after_services",
            "action": "Add a testimonials/case results section with specific, quantified outcomes. Include client name and role.",
            "evidence": "No social proof section — E-E-A-T Experience signals require demonstrated results",
            "effort": "medium",
            "impact": "Experience is the #1 differentiator in Dec 2025 Google update"
        })

    return recs


def generate_schema_recommendations(section_analyses, business_type):
    """Generate schema recommendations based on detected section types and business type."""
    recs = []

    # Always recommend Organization
    recs.append({
        "type": "Organization",
        "scope": "site-wide",
        "priority": "high",
        "reason": "Every site needs Organization schema for entity resolution",
        "warning": None
    })

    # Business-type specific
    type_schemas = {
        "agency": [
            {"type": "Service", "scope": "service pages", "reason": "Service schema enables direct matching for consulting queries"},
            {"type": "Person", "scope": "team pages", "reason": "Team member schema builds E-E-A-T Expertise signals"},
            {"type": "Review", "scope": "testimonial sections", "reason": "Review schema powers star ratings in search + AI credibility"},
        ],
        "saas": [
            {"type": "SoftwareApplication", "scope": "product pages", "reason": "Required for software comparisons in AI answers"},
            {"type": "Product", "scope": "pricing pages", "reason": "Product + Offer schema enables pricing queries"},
            {"type": "Review", "scope": "testimonial sections", "reason": "AggregateRating powers star ratings"},
        ],
        "ecommerce": [
            {"type": "Product", "scope": "product pages", "reason": "Required for product comparison queries"},
            {"type": "Offer", "scope": "product pages", "reason": "Offer schema enables price-based queries"},
            {"type": "AggregateRating", "scope": "product pages", "reason": "Star ratings in search + AI trust signal"},
            {"type": "BreadcrumbList", "scope": "all pages", "reason": "Navigation schema improves crawl understanding"},
        ],
        "local_service": [
            {"type": "LocalBusiness", "scope": "homepage", "reason": "Required for local search + AI local queries"},
            {"type": "Service", "scope": "service pages", "reason": "Service schema for 'near me' type queries"},
            {"type": "GeoCoordinates", "scope": "contact page", "reason": "Location data for geographic queries"},
        ],
        "publisher": [
            {"type": "Article", "scope": "all articles", "reason": "Article schema is baseline for content sites"},
            {"type": "Person", "scope": "author pages", "reason": "Author schema builds E-E-A-T signals"},
            {"type": "BreadcrumbList", "scope": "all pages", "reason": "Content hierarchy for topic authority"},
        ],
    }

    for schema in type_schemas.get(business_type, type_schemas["agency"]):
        recs.append({
            "type": schema["type"],
            "scope": schema["scope"],
            "priority": "high",
            "reason": schema["reason"],
            "warning": None
        })

    # Check for deprecated recommendations to PREVENT
    recs.append({
        "type": "FAQPage",
        "scope": "FAQ sections",
        "priority": "info",
        "reason": "Q&A structure helps AI models extract answers, but FAQPage schema no longer generates Google rich results for commercial sites (Aug 2023). Still has GEO benefit.",
        "warning": "⚠️ Do NOT expect Google rich results from FAQPage schema on commercial sites. The Q&A content format still helps for AI citation."
    })

    # Explicitly note deprecated types
    recs.append({
        "type": "DEPRECATED_WARNING",
        "scope": "n/a",
        "priority": "critical",
        "reason": "NEVER use: HowTo (deprecated Sept 2023), SpecialAnnouncement (deprecated July 2025)",
        "warning": "These schema types will trigger Google warnings and waste implementation effort."
    })

    return recs


def analyze_content(data):
    """Section-aware content analysis with evidence-grounded recommendations."""
    url = data.get("url", "")
    title = data.get("title", "")
    content = data.get("content", "")
    metadata = data.get("metadata", {})
    brand_name = data.get("brand_name", "")
    business_type = data.get("business_type", "unknown")
    target_queries = data.get("target_queries", [])
    audit_gaps = data.get("audit_gaps", [])

    # Split into sections
    sections = split_into_sections(content)
    total_sections = len(sections)

    # Classify and analyze each section
    section_analyses = []
    total_recs = 0
    for i, section in enumerate(sections):
        section_type = classify_section(
            section["heading"], section["content"], i, total_sections
        )
        analysis = analyze_section(
            section["heading"], section["content"], section_type, business_type
        )
        section_analyses.append(analysis)
        total_recs += len(analysis.get("recommendations", []))

    # Generate new section recommendations
    new_sections = generate_new_section_recommendations(
        sections, section_analyses, business_type, brand_name
    )

    # Generate schema recommendations
    schema_recs = generate_schema_recommendations(section_analyses, business_type)

    # Overall metrics
    total_words = sum(s.get("word_count", 0) for s in section_analyses)
    optimizable_sections = [s for s in section_analyses if not s.get("do_not_touch")]
    avg_citability = 0
    if optimizable_sections:
        # Simple citability estimate per section
        scores = []
        for s in optimizable_sections:
            score = 0
            if 100 <= s.get("word_count", 0) <= 200:
                score += 3
            if s.get("stats_count", 0) >= 1:
                score += 2
            if s.get("citations_count", 0) >= 1:
                score += 3
            if s.get("has_list") or s.get("has_table"):
                score += 1
            if not s.get("recommendations"):
                score += 1  # No issues found = already good
            scores.append(min(score, 10))
        avg_citability = round(sum(scores) / len(scores), 1)

    result = {
        "url": url,
        "title": title,
        "analysis_date": str(date.today()),
        "business_type": business_type,
        "total_words": total_words,
        "total_sections": total_sections,
        "section_breakdown": {
            s_type: sum(1 for s in section_analyses if s["section_type"] == s_type)
            for s_type in set(s["section_type"] for s in section_analyses)
        },
        "avg_section_citability": avg_citability,
        "total_recommendations": total_recs + len(new_sections),
        "sections": section_analyses,
        "new_sections_needed": new_sections,
        "schema_recommendations": schema_recs,
        "summary": {
            "sections_to_optimize": len(optimizable_sections),
            "sections_preserved": total_sections - len(optimizable_sections),
            "high_impact_changes": sum(
                1 for s in section_analyses
                for r in s.get("recommendations", [])
                if "2.3x" in r.get("impact", "") or "115%" in r.get("impact", "")
            ) + sum(1 for n in new_sections if "2.3x" in n.get("impact", "")),
        }
    }

    return result


def main():
    parser = argparse.ArgumentParser(description="Section-Aware AI Content Optimizer")
    parser.add_argument("--input", required=True, help="Path to page content JSON")
    parser.add_argument("--output", help="Output path")

    args = parser.parse_args()

    with open(args.input) as f:
        data = json.load(f)

    result = analyze_content(data)

    output = json.dumps(result, indent=2, default=str)
    print(output)

    if args.output:
        Path(args.output).parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, 'w') as f:
            f.write(output)


if __name__ == "__main__":
    main()
