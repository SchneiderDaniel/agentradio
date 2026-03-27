---
name: general-general-code-simplifier
description: >
  Simplifies working code by reducing cognitive complexity, removing redundancy, flattening nesting,
  and applying clean-code patterns — without changing behaviour. Use this skill whenever a developer
  says the code works but is too complex, hard to read, or feels bloated. Trigger on phrases like
  "simplify this", "clean this up", "this code is messy", "make it shorter", "reduce complexity",
  "refactor for readability", or when the user shares a working function/module and asks you to
  improve it. Also trigger when someone pastes code and says anything like "I don't love this" or
  "there must be a better way".
---

# Skill: Code Simplifier

A focused skill for reducing the cognitive complexity of **already-working code** without altering its behaviour.
Inspired by Martin Fowler's *Refactoring*, Refactoring.guru, and SonarQube's cognitive-complexity metric.

---

## Philosophy

> "Perfection is achieved not when there is nothing more to add, but when there is nothing left to take away."
> — Antoine de Saint-Exupéry

The goal is not to rewrite — it is to **reveal** the logic that was always there, obscured by accidental complexity.
Every change must be **behaviour-preserving** and **motivation-explained**.

---

## The Simplification Workflow

### Step 1 — Read and Understand

Before touching anything:
1. Read the entire file or function carefully.
2. Identify its **single responsibility** — what it *actually* does in one sentence.
3. Note any parts that surprised you; those are the complexity hotspots.

### Step 2 — Score Cognitive Complexity

Mentally score the code on these axes (you don't need to output the scores — they guide your focus):

| Axis | What to look for |
|---|---|
| **Nesting depth** | `if` inside `for` inside `try` inside `if` → flatten |
| **Negative conditionals** | `if not x and not y` → invert or extract |
| **Long functions** | >20 lines doing more than one thing → split |
| **Magic values** | bare `0`, `"active"`, `86400` → extract to named constants |
| **Repeated patterns** | same 3-line block in multiple places → extract helper |
| **Dead code** | unreachable branches, unused variables → remove |
| **Over-abstraction** | one-line wrappers that add no clarity → inline |

### Step 3 — Apply Simplification Patterns

Work through these in priority order (most impactful first):

#### 🔻 Flatten Nesting (Early Returns / Guard Clauses)
Replace deeply nested conditionals with early returns. This is the single biggest readability win.

```python
# Before
def process(order):
    if order:
        if order.is_valid():
            if not order.is_cancelled():
                send(order)

# After
def process(order):
    if not order or not order.is_valid() or order.is_cancelled():
        return
    send(order)
```

#### 🧹 Extract Until It Reads Like Prose
If a block needs a comment to explain what it does, extract it into a function whose *name* is that comment.

```python
# Before
# Check if the user is eligible for a discount
if user.account_age_days > 365 and user.total_orders > 10 and not user.has_active_dispute:
    ...

# After
def is_eligible_for_discount(user):
    return user.account_age_days > 365 and user.total_orders > 10 and not user.has_active_dispute
```

#### 🔁 Collapse Redundancy
Remove loops, conditions, or variables that exist only to shuttle data from one place to another.

```python
# Before
result = []
for item in items:
    result.append(transform(item))
return result

# After
return [transform(item) for item in items]
```

#### 🏷️ Name Magic Values
Every literal that encodes a business rule should become a named constant.

```python
# Before
if session_seconds > 1800:

# After
SESSION_TIMEOUT_SECONDS = 1800
if session_seconds > SESSION_TIMEOUT_SECONDS:
```

#### ✂️ Remove Dead Code
Commented-out code, unreachable branches, and unused variables are noise — delete them.
If the user seems worried about losing history, reassure them: version control is for that.

### Step 4 — Produce the Output

Always output in this structure:

---

### 🔍 Complexity Hotspots Found
A short bullet list of what you identified as the main issues.
Be specific and honest — if the code is already clean, say so.

### ✅ Simplified Code
The full simplified version. Not a diff — the complete working code, ready to paste in.
Keep all original behaviour, signatures, and docstrings (updating them if they no longer match).

### 📋 What Changed & Why
A concise table:

| Change | Pattern applied | Reason |
|---|---|---|
| Flattened `process()` | Guard clause | Nesting depth was 4 — hard to follow the happy path |
| Extracted `is_eligible_for_discount()` | Extract function | Inline condition needed a comment to be understood |

---

## Hard Rules

- **Never change observable behaviour.** If you are unsure whether a change is safe, leave it and note it in "What Changed & Why" as "candidate for future extraction — needs test coverage first."
- **Never rename public API symbols** (function names, class names, exported variables) unless the user explicitly asks.
- **Preserve all error handling.** Simplifying a `try/except` away is almost never correct.
- **One pass at a time.** If the file is large, suggest simplifying one function or section at a time so the user can verify each change.

---

## When to Stop

Stop simplifying when:
- Further changes would require understanding the broader call graph (you can flag these as "next steps")
- The code already reads clearly — say so rather than making changes for the sake of it
- A simplification would trade readability for cleverness (list comprehensions with 3+ conditions, chained lambdas, etc.)
