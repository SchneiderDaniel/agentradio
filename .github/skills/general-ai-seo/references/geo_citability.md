# GEO Citability Scoring Framework

Passage-level citability scoring for Generative Engine Optimization. Score each H2/H3 section for likelihood of being cited by AI models.

---

## Optimal Passage Length: 134-167 Words

AI models extract passages in this word-count range for citations. Each H2/H3 section should be evaluated as a potential citation unit.

- Sections shorter than ~100 words lack enough substance for standalone citation
- Sections longer than ~200 words should be split into focused subsections
- The sweet spot (134-167) matches the context window AI models allocate per source citation

---

## Strong Citability Signals

### Structure & Format
- Clear, quotable sentences with specific facts or statistics
- Self-contained answer blocks (extractable without surrounding context)
- Direct answer in the first 40-60 words of the section
- Definitions following "X is..." patterns
- Question-format headings that match natural language queries

### Data & Attribution
- Claims attributed with specific sources ("According to [Source], ...")
- Statistics with numbers, percentages, or dollar figures
- Unique data points not found elsewhere on the web
- Named studies, reports, or research with dates
- Expert quotes with attribution

### Content Quality
- Structured lists (3+ items) that AI can extract as bullet points
- Comparison tables with clear data
- Step-by-step processes with numbered items
- Concrete examples with specifics (names, dates, numbers)

---

## Weak Citability Signals

- Vague statements without supporting evidence
- Opinion without data or attribution
- Buried conclusions (key point not in first 2 sentences)
- No data points or statistics
- Requires surrounding context to make sense
- Filler content that restates the heading
- Generic advice that appears on hundreds of other pages

---

## Platform-Specific Citation Sources (Updated March 2026)

### Correlation with AI Citations

| Platform | Correlation | Priority |
|----------|-------------|----------|
| YouTube mentions | 0.737 | Highest — strongest predictor of AI citation |
| LinkedIn | #2 most-cited domain in AI search (ALM Corp 2026, 325K prompts) | Very high — professional authority signal |
| Reddit mentions | Cited in 24% of AI responses (OtterlyAI 2026, 1M+ citations) | Strong signal for topical authority |
| Wikipedia presence | High | Establishes baseline authority |
| Domain Rating (backlinks) | ~0.266 | Weak — backlinks alone insufficient |

### Cross-Platform Coverage
- Only **11% of domains** are cited by both ChatGPT AND Perplexity (OtterlyAI 2026)
- Each AI platform has distinct citation preferences
- Multi-platform presence (YouTube + LinkedIn + Reddit + own domain) maximizes citation probability
- YouTube is the single highest-leverage platform for earning AI citations
- LinkedIn is the #2 most-cited domain across AI search results (ALM Corp 2026)

---

## Citability Score Per Section: 0-10

| Score | Tier | Description |
|-------|------|-------------|
| 9-10 | Highly Citable | Self-contained, data-rich, attributed, optimal length. AI will likely cite this passage. |
| 6-8 | Moderately Citable | Some data, partially self-contained, needs minor restructuring or additional attribution. |
| 3-5 | Low Citability | Vague, no data, poor structure. Unlikely to be cited without significant revision. |
| 0-2 | Not Citable | Opinion only, no facts, requires context. Will not be cited by AI models. |

### Scoring Criteria Breakdown

| Criterion | Max Points |
|-----------|-----------|
| Passage length (100-200 words optimal) | 2 |
| Self-contained opening (definitional/declarative) | 1.5 |
| Statistics and data points (3+ = 2, 1-2 = 1) | 2 |
| Source attribution (2+ = 1.5, 1 = 0.5) | 1.5 |
| Question-format heading | 1 |
| Structured list (3+ items) | 1 |
| Expert quote present | 1 |

### Optimization Priority

Fix low-citability sections on high-traffic pages first. A page with 8 sections where 6 score below 4 needs a full restructure. A page where most sections score 6+ only needs targeted improvements.

---

## GEO Tactics That Backfire (March 2026)

Generative Engine Optimization is in its "pre-Penguin" phase — manipulative tactics work today but a crackdown is coming. LLMs are already collecting data on spam patterns.

### Self-Promotional Listicles

- Writing "Best X for Y" articles with yourself ranked #1 is being detected
- Claude and ChatGPT now explicitly warn users: "this is a spammed category — I used reputable third-party sources instead"
- These listicles may now HURT your brand's LLM visibility rather than help it
- Google is also nullifying their ranking benefit (Lily Ray, Amsive Digital, March 2026)

### Scaled AI Content Without Human Expertise

- Mass-producing AI-written content that lacks original insight is the #1 risk factor
- Google's March 2024 core update reduced "unhelpful content" by 45% — and they're building the next version
- The pattern: tactic works → gets popularized → Google/OpenAI collects data → mass penalty
- Using AI to write content is fine. Using AI to do the thinking is not. Original ideas + AI execution = safe. AI ideas + AI execution = increasingly detectable.

### Fake Author Profiles

- Midjourney-generated author photos and fabricated bios are detectable
- Google's Knowledge Graph cross-references authors across the ecosystem (conferences, publications, social profiles, media appearances)
- If your "expert author" has no footprint anywhere else, it signals manipulation

### ChatGPT Whitelisted Domain Searches (Emerging — March 2026)

- ChatGPT 5.4 fan-out queries now use `site:` searches targeting specific trusted domains per category
- Example: for product reviews, it may only search TrustPilot, G2, Yelp — filtering out manipulative sites
- This means being ON trusted third-party platforms is becoming mandatory, not optional
- Implication: the multi-platform presence dimension of our audit becomes even more critical

### The Historical Pattern

- Pre-Penguin (link spam worked) → Penguin update → mass penalties
- Pre-HCU (thin content worked) → Helpful Content Update → 45% reduction
- Pre-GEO crackdown (we are here) → next crackdown → expected within months
- Every cycle: early adopters of manipulation win short-term, get destroyed long-term
