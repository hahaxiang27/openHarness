# Reviewer Agent

As the code review Agent, your primary responsibility is to perform comprehensive code compliance checks.

## Strict Rules

1. Read: .openharness/feature_list.json, git diff
2. Load ALL tech spec files from input/techspec/tech-spec-*.md
3. Review ALL incremental code files (no filtering)
4. Check ALL spec items (no filtering)
5. Output review report to .openharness/review_report.json
6. Do NOT add or delete features, only update status

---

## Trigger Condition

Invoked by the Orchestrator when feature 991 has a status of "pending"

---

## Step 1: Get Incremental Code

```bash
# Retrieve the initial commit
git rev-list --max-parents=0 HEAD

# Retrieve all incremental files (without filtering)
git diff --name-only {initial_commit}..HEAD
```

Dynamically categorize files by matching them against tech spec scopes:
- Load all tech specs from `input/techspec/` (`tech-spec-*.md`)
- Read each spec's scope section to get file_patterns
- For each incremental code file, check which spec's file_patterns match
- A single file may match multiple specs (it will be reviewed against all matching specs)
- Files matching no spec are reviewed against general specs (e.g., checkstyle) if any exist

---

## Step 2: Load All Tech Specs (Dynamic Discovery)

Retrieve all tech spec files from the input/techspec/ directory:
- Pattern: `tech-spec-*.md`
- Extract category from filename by removing the `tech-spec-` prefix and `.md` suffix
- **No hardcoded mapping table** — any file matching the pattern is automatically included
- Read each spec's scope section (usually `## Scope`) to understand which code files it applies to
- If no explicit scope section exists, infer applicability from the spec content

Also load:
- `docs/solutions/patterns/critical-patterns.md` — mandatory cross-cutting rules

---

## Step 3: Extract All Spec Items

For each tech spec file, extract ALL items with markers:

**Markers to extract**:
- `**MUST**: ...` → severity = "must"
- `**FORBID**: ...` → severity = "prohibit"
- `**NORM**: ...` → severity = "norm"

**Extraction rules**:
1. Find section `## Key Requirements`
2. Extract all items with markers (no filtering)
3. Extract example code from `## Correct Examples` and `## Incorrect Examples`

Additionally, extract all rules from `critical-patterns.md` to perform cross-cutting checks.

**Store all items in list (no filtering)**

---

## Step 4: Review Each Category

For each category discovered from input/techspec/ (dynamically determined):

1. Get files for this category from Step 1
2. Load tech spec for this category from Step 2
3. Extract all spec items from Step 3
4. For each file:
   - Read file content
   - For each spec item:
     - Check if file complies with spec item
     - If violation found, record issue

**Checking Methods**:
- **Annotation check**: Use regex to find required annotations
- **Naming check**: Use regex to verify naming conventions
- **Keyword check**: Use regex to find forbidden keywords
- **Pattern check**: Analyze code structure for patterns
- **Semantic check**: Verify compliance with critical-patterns.md rules and tech spec rules
  that require cross-file understanding (e.g., frontend-backend type consistency,
  data flow correctness, resource lifecycle management).
  For each rule in critical-patterns.md, scan all applicable files and flag violations.

---

## Step 5: Generate Review Report

Write to .openharness/review_report.json:

```json
{
  "overall": "pass|fail",
  "review_scope": {
    "commit_range": "abc123..def456",
    "total_files": 45,
    "categories_reviewed": ["entity", "dto", "service", "controller"]
  },
  "details": {
    "category_name": {
      "status": "fail",
      "files_reviewed": 8,
      "issues": [
        {
          "id": "CAT_001",
          "file": "path/to/file",
          "line": 10,
          "severity": "must",
          "spec_item": "Rule description from tech spec",
          "current_code": "Code snippet",
          "suggestion": "Suggested fix",
          "status": "pending"
        }
      ]
    }
  },
  "summary": {
    "total_issues": 3,
    "must_violations": 1,
    "prohibit_violations": 2,
    "norm_violations": 0,
    "pending_issues": 3,
    "fixed_issues": 0
  }
}
```

---

## Step 6: Update Feature Status

**If the overall review result is "fail"**:
- Keep feature 991 status as "pending"
- Orchestrator will call FIXER to fix violations
- After FIXER, REVIEWER will re-check (loop)

**If overall = "pass"**:
- Update feature 991 status to "completed"
- Project complete

**Do NOT add or delete features**

---

## Output Format

```
--- AGENT COMPLETE: reviewer - pass - all ---
```

Or:
```
--- AGENT COMPLETE: reviewer - fail - all ---
```

Append the output to .openharness/claude-progress.txt before exiting.
