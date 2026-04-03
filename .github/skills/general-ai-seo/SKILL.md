---
name: ai-seo
description: >
  AI SEO Command Center — audit sites for AI-readiness, optimize content for LLM
  citability, track Share of Model across ChatGPT/Perplexity/Gemini/AI Overviews,
  and build multi-platform distribution strategies. Use this skill when the user asks
  to "audit my site for AI", "AI SEO check", "optimize for AI search", "share of model",
  "am I showing up in ChatGPT", "AI overview tracking", "check my AI visibility",
  "SEO audit", "AI readiness", "optimize my content for AI", or wants to improve their
  visibility in AI-generated answers.
user-invocable: true
argument-hint: "audit <url> | optimize <url> | monitor <brand> | distribute <brand> | measure <brand> | report <brand>"
---

# AI SEO Command Center

Audit, optimize, and monitor websites for visibility in AI-generated search results (ChatGPT, Perplexity, Gemini, Google AI Overviews) alongside traditional Google search.

## Why This Matters

SEO has split into two games. Google rankings still matter, but AI search engines now answer queries directly — and only 12% of URLs cited by ChatGPT/Perplexity rank in Google's top 10. AI referral traffic converts at 14.2% vs Google organic's 2.8%. Most businesses are optimizing for one game while a higher-converting second game happens without them.

## Prerequisites

- Supabase tables created: run `python3 .claude/skills/ai-seo/scripts/seo_db.py --init-db`
- Firecrawl MCP connected (site crawling and scraping)
- Perplexity MCP connected (AI visibility checks and research)
- `psycopg2` installed (`pip3 install psycopg2-binary`)

## Commands

### `audit <url>`

Crawl a site and score it 0-100 on AI-readiness across 7 dimensions.

#### Step 1: Crawl the site (up to 20 pages)

**1a. Discover URLs** — Use Firecrawl MCP `firecrawl_map` on the root URL to get a full URL list for the site.

**1b. Select key pages** — From the map results, pick up to 20 pages. Prioritize in this order:
1. Homepage
2. About / Team
3. Services / Features / Product pages
4. Pricing
5. Case studies / Testimonials
6. Blog posts (top 5-8 by recency or prominence)
7. FAQ / Help / Knowledge base
8. Contact

If fewer than 20 pages exist, scrape all of them.

**1c. Scrape each page** — Two-pass scraping with Firecrawl MCP `firecrawl_scrape`:

**Pass 1 — Content (all 20 pages):** Scrape with `formats: ["markdown"]` and `onlyMainContent: true`.
- `onlyMainContent: true` strips site nav, footer, language switchers, and breadcrumbs — reducing noise by ~40% compared to `false`.
- Some UI elements survive (service switchers, logo carousels, form configurators) but `audit_crawl.py` handles these — it skips image-only lines, short nav links, and form placeholders.
- This markdown goes in the `content` field of the input JSON.

**Pass 2 — Schema (3-5 key pages only):** Separately scrape homepage, about, 1-2 service pages, and 1 blog post with `formats: ["rawHtml"]` and `onlyMainContent: false`.
- `onlyMainContent: false` is required here because JSON-LD `<script>` tags may be in `<head>` or outside the main content area.
- Extract ONLY the JSON-LD `<script>` blocks from the raw HTML (regex: `<script[^>]*type=["']application/ld\+json["'][^>]*>.*?</script>`). Discard the rest to keep file size manageable.
- Put the extracted JSON-LD blocks in the `raw_html` field of the page object.

**Why this approach:**
- `onlyMainContent: true` for markdown = cleanest content for analysis (~60% actual content vs ~45% with `false`)
- `onlyMainContent: false` for rawHtml = catches JSON-LD in `<head>` and inline, which `true` would strip
- `excludeTags: ["nav", "footer"]` does NOT help further — component-based sites render navs outside `<nav>` tags
- `formats: ["json"]` with schema extraction works but costs 5x more credits and AI-interprets (may hallucinate types)
- `firecrawl_crawl` is async and can't mix `onlyMainContent` per-page — no advantage for 20 pre-selected URLs
- Total cost: ~23-25 Firecrawl credits per audit (20 content + 3-5 schema)

**1d. Analyze** — Run each scraped page through the audit script:

```bash
python3 .claude/skills/ai-seo/scripts/audit_crawl.py --input <crawled_pages>.json
```

Checks per page:
- robots.txt for AI crawler access (GPTBot, ClaudeBot, PerplexityBot, Google-Extended)
- llms.txt existence (homepage only)
- sitemap.xml validity (homepage only)
- Schema markup (JSON-LD) on each page
- Content structure (answer-first format, stats, citations, quotes, FAQ sections)
- Page freshness (last modified dates)

**Output**: JSON with per-page analysis results saved to `.tmp/audit_crawl_<domain>.json`

**1e. Analyze GEO citability** — Run passage-level citability analysis on the crawl output:

```bash
python3 .claude/skills/ai-seo/scripts/analyze_citability.py --input .tmp/audit_crawl_<domain>.json
```

**Output**: JSON with per-section citability scores saved to `.tmp/citability_<domain>.json`

**Note**: E-E-A-T signals are now auto-extracted by `audit_crawl.py` from the page content (case studies, author bylines, testimonials, contact info). The `eeat_data` field is included in the crawl output automatically. If the automated extraction misses signals you can see in the content, you can override via the enrichment step.

#### Step 2: Perplexity research (multi-platform + AI visibility)

Run these two research tasks using Perplexity MCP, then save findings to an enrichment JSON:

**2a. Check multi-platform presence** — Use Perplexity MCP `search_and_summarize` to find the brand across Reddit, YouTube, LinkedIn, and industry publications. Use Firecrawl MCP `firecrawl_search` as backup.

**2b. Check current AI visibility** — Use Perplexity MCP to query 5-10 industry-relevant questions and check if the brand appears in AI responses. This establishes the baseline.

Save the research output to `.tmp/enrichment_<domain>.json` with this structure:

```json
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
```

#### Step 3: Enrich crawl data with research

```bash
python3 .claude/skills/ai-seo/scripts/audit_enrich.py \
    --crawl .tmp/audit_crawl_<domain>.json \
    --enrichment .tmp/enrichment_<domain>.json
```

Merges platform_data, entity_data, visibility_data, and citability_data into the crawl JSON so the scorer has access to all 9 dimensions. Overwrites the crawl JSON in-place by default (use `--output` for a separate file).

Include the citability data from Step 1e:
```bash
python3 .claude/skills/ai-seo/scripts/audit_enrich.py \
    --crawl .tmp/audit_crawl_<domain>.json \
    --enrichment .tmp/enrichment_<domain>.json \
    --citability-data .tmp/citability_<domain>.json
```

Can also accept data as inline JSON args instead of a file:
```bash
python3 .claude/skills/ai-seo/scripts/audit_enrich.py \
    --crawl .tmp/audit_crawl_<domain>.json \
    --platform-data '{ ... }' \
    --entity-data '{ ... }' \
    --visibility-data '{ ... }'
```

#### Step 4: Score the audit

```bash
python3 .claude/skills/ai-seo/scripts/audit_score.py --input .tmp/audit_crawl_<domain>.json
```

Scores crawl results against `references/scoring_rubric.yaml`:

| Dimension | Points | What's Checked |
|---|---|---|
| Content Structure | 25 | Answer-first format, fact density, citations, freshness, question headings |
| Schema Markup | 20 | JSON-LD presence, type variety (FAQ, Article, HowTo, Org), coverage % |
| Crawler Access | 15 | robots.txt allows AI bots, llms.txt exists, sitemap valid |
| Multi-Platform | 15 | Found on Reddit, YouTube, LinkedIn, industry pubs (4+ = high score) |
| Entity Clarity | 10 | Consistent brand naming, About page, linked profiles, author credentials |
| Current AI Visibility | 10 | Already appearing in Perplexity/AI Overview results (baseline) |
| Technical Foundations | 5 | HTTPS, mobile-friendly, page speed, clean URLs |

**Tiers**: 80-100 AI-Ready | 60-79 Partially Ready | 40-59 Significant Gaps | 0-39 Not AI-Ready

**Output**: JSON with scores and findings saved to `.tmp/audit_score_<domain>.json`

#### Step 5: Generate the report

Three output formats available:

```bash
# HTML report (default for audits — styled, tabbed, dark theme)
python3 .claude/skills/ai-seo/scripts/format_report.py --input .tmp/audit_score_<domain>.json --type audit --format html

# Machine-readable fix list (for another AI model to consume and execute)
python3 .claude/skills/ai-seo/scripts/format_report.py --input .tmp/audit_score_<domain>.json --type audit --format fixes

# Markdown report
python3 .claude/skills/ai-seo/scripts/format_report.py --input .tmp/audit_score_<domain>.json --type audit --format markdown
```

The HTML report includes:
- Per-page breakdown of issues found across all crawled pages
- **Projected score after fixes**: estimates the new score if top recommendations are implemented
- **Pre-filled content**: ready-to-use schema markup (JSON-LD), answer-first paragraphs, and FAQ sections for priority pages

The fixes JSON is a lean, structured file designed for handoff to another AI (e.g. Lovable, Cursor). Contains priority-ordered fix list, site-level issues, and per-page issues — no prose, no formatting, just what's broken and what to do.

**Output**:
- HTML: `data/ai_seo/audits/<domain>_YYYY-MM-DD.html`
- Fixes: `data/ai_seo/audits/<domain>_fixes_YYYY-MM-DD.json`
- Markdown: `data/ai_seo/audits/<domain>_YYYY-MM-DD.md`

#### Step 6: Save to database

```bash
python3 .claude/skills/ai-seo/scripts/seo_db.py --save-audit .tmp/audit_score_<domain>.json
```

---

### `optimize <url>`

Take a specific page URL and restructure its content for maximum AI citability.

#### Step 1: Scrape the page

Use Firecrawl MCP `firecrawl_scrape` to get full page content.

#### Step 2: Analyze and research

Use Perplexity MCP `research_technical` to:
- Find what AI models currently say about this topic
- Identify available statistics and quotable experts
- Find related questions people ask

#### Step 3: Generate optimized content (Claude-native)

Apply these transformations:
- **Answer-first paragraph**: 40-60 words directly answering the core question, placed at the top
- **Citation blocks**: 3-5 bullet points with statistics and sources (+115% AI visibility)
- **Question-based headings**: H2s as natural questions
- **Expert quotes**: Integrate or flag for +37% AI visibility boost
- **FAQ section**: 5-8 Q&A pairs matching real user queries
- **Recency markers**: "Updated [date]" and "As of [month year]"
- **Entity mentions**: Brand/author name appears 2-3 times naturally

#### Step 4: Generate schema markup

Using templates from `references/schema_templates/`:
- FAQPage JSON-LD from FAQ section
- Article or HowTo JSON-LD as appropriate
- Organization JSON-LD if not site-wide

#### Step 5: Generate llms.txt (if site doesn't have one)

Using `references/llms_txt_template.md` as a starting point.

**Output**: Optimized content + schema blocks saved to `data/ai_seo/optimizations/<slug>_YYYY-MM-DD.md`

---

### `monitor <brand>`

Track Share of Model — how often a brand appears in AI-generated responses.

#### Step 1: Generate or load tracked queries

```bash
python3 .claude/skills/ai-seo/scripts/monitor_som.py --generate-queries --brand "<brand>" --industry "<industry>"
```

Generates 20-30 queries a potential customer would ask. Categories: informational, comparative, transactional, brand.

#### Step 2: Run Share of Model check

```bash
python3 .claude/skills/ai-seo/scripts/monitor_som.py --check --brand "<brand>"
```

For each tracked query:
1. Query Perplexity MCP `search_and_summarize`
2. Parse: brand mentioned? Position (primary/top3/mentioned/absent)? Sentiment?
3. Score: primary=3, top3=2, mentioned=1, absent=0
4. Store in `ops.aiseo_som_snapshots`

#### Step 3: Calculate aggregates

```bash
python3 .claude/skills/ai-seo/scripts/monitor_som.py --aggregate --brand "<brand>"
```

Calculates: mention_rate, avg_position_score, competitor_comparison. Stores in `ops.aiseo_som_aggregates`.

#### Step 4: Generate report

```bash
python3 .claude/skills/ai-seo/scripts/format_report.py --input .tmp/som_<brand>.json --type monitor
```

**Output**: Report saved to `data/ai_seo/monitoring/<brand>_YYYY-MM-DD.md`

**Scheduling**: Run weekly via cron. The real value is trend data over time.

---

### `distribute <brand>`

Generate a multi-platform presence strategy to maximize AI citation surface area.

#### Step 1: Assess current footprint

Use Perplexity MCP + Firecrawl MCP to find where the brand currently appears across:
- Reddit (24% of AI responses cite Reddit)
- YouTube (29.5% of AI Overviews cite YouTube)
- LinkedIn (professional authority signal)
- Industry publications (85% of brand citations come from 3rd party)
- Wikipedia, Quora, podcast directories

#### Step 2: Gap analysis (Claude-native)

Compare current presence against high-citation platforms. Identify 2-3 platforms where they're missing but should be.

#### Step 3: Generate platform-specific strategies

For each gap, produce:
- **Reddit**: Relevant subreddits, content types that work, example comment templates
- **YouTube**: SEO optimization for AI (answer-first descriptions, timestamps, keyword titles)
- **LinkedIn**: Content cadence, post types that get cited
- **Third-party seeding**: Guest post opportunities, podcasts, directory listings, roundup posts

#### Step 4: Build 90-day calendar

Week-by-week action items, priority ordered by impact (third-party mentions first).

**Output**: Saved to `data/ai_seo/distribution/<brand>_plan_YYYY-MM-DD.md`

---

### `measure <brand>`

Connect AI visibility to estimated revenue impact.

#### Step 1: Pull monitoring data

```bash
python3 .claude/skills/ai-seo/scripts/seo_db.py --som-history --brand "<brand>"
```

#### Step 2: Estimate revenue impact (Claude-native)

Using the 14.2% AI referral conversion rate vs 2.8% Google organic:
- Estimate monthly AI referral traffic from current visibility
- Calculate conversion value differential
- Project revenue impact of improving from current to target score

#### Step 3: Generate business impact report

**Output**: Saved to `data/ai_seo/measurement/<brand>_YYYY-MM-DD.md`

---

### `report <brand>`

Aggregate all data into a periodic executive report combining audit scores, SoM trends, distribution progress, and revenue estimates.

**Output**: Saved to `data/ai_seo/reports/<brand>_YYYY-MM-DD.md`

---

## Key Statistics (Research-Backed)

These numbers drive the scoring and recommendations:

| Metric | Value | Source | Verified |
|---|---|---|---|
| AI Overview CTR reduction | -61% | Seer Interactive | Industry report |
| AI referral conversion rate | ~4.4x higher than Google organic | Multiple sources | Directionally confirmed |
| Schema markup citation boost | Significant (widely cited as 2-3x) | Industry consensus | Directionally supported, no single study |
| Answer-first format | Significantly increases AI citation probability | GEO research consensus | Directionally supported |
| Data-dense passages | Higher citation rates | GEO research consensus | Directionally supported |
| Expert quotes | Improve AI trust and citation | GEO research consensus | Directionally supported |
| Source attribution | Significantly higher citation rates | GEO research consensus | Directionally supported |
| 3rd-party brand citations | ~85% | AirOps | Industry report |
| Multi-platform presence | Strongly correlated with AI citations | Multiple sources | Confirmed (4+ platforms) |
| Reddit in Perplexity responses | ~24% (Jan 2026) | OtterlyAI 2026 | Verified (Perplexity-specific) |
| YouTube in AI Overviews | ~18.8% | Multiple sources | Verified |
| YouTube correlation with AI citations | 0.737 (strongest signal) | GEO research | Verified |
| Optimal citable passage length | 134-167 words | AmICited.com, GEO research | Verified |
| LinkedIn is #2 cited domain | In AI search results | ALM Corp 2026 (325K prompts) | Verified |
| Domains cited by both ChatGPT AND Perplexity | Only 11% | OtterlyAI 2026 | Industry report |
| AI Overviews query coverage | ~33% of queries | OtterlyAI 2026 | Industry report |
| AI Overviews engine | Upgraded to Gemini 3 (Jan 27, 2026) | Google | Confirmed |
| March 2026 Core Update | Rolling out (began March 13, 2026) | Google | Confirmed |

## Database

All tables in `ops` schema (Supabase). Verify with:

```bash
python3 .claude/skills/ai-seo/scripts/seo_db.py --init-db
```

Tables: `aiseo_sites`, `aiseo_audits`, `aiseo_page_analyses`, `aiseo_tracked_queries`, `aiseo_som_snapshots`, `aiseo_som_aggregates`

## Edge Cases

| Scenario | Handling |
|---|---|
| Firecrawl can't crawl site | Fall back to Perplexity research. Note limitation in audit. |
| Zero schema markup found | Score 0 for that dimension. Priority fix #1. |
| Brand name is generic | Ask user for disambiguating terms. Use "brand + industry" in queries. |
| Perplexity rate limited | Batch queries in chunks of 5 with 30-second pauses. |
| Site has 500+ pages | Audit top 20 pages only. Note sampling in report. |
| No AI referral traffic yet | Normal for most SMBs. Show opportunity cost, not failure. |

## Integration With Other Skills

| Skill | How It Connects |
|---|---|
| `youtube-seo` | Share seed keywords. AI monitoring queries feed YouTube tracking. |
| `youtube-content` | Content gaps from monitoring become video briefs. |
| `linkedin-content` | Distribution plan feeds LinkedIn post topics. |
| `competitor-analysis` | Compare AI visibility against competitors. |
| `research-lead` | Run audit as a lead magnet for consulting prospects. |
| `daily-brief` | Weekly SoM summary included in daily brief. |
