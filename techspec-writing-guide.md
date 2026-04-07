# Tech Spec Writing Guide

## 1. Document Purpose and Target Audience

This guide is intended for all developers who need to write technical specification documents. It defines the standard structure, writing method, and quality requirements for tech spec documents.

## 2. Standard Document Structure

### 2.1 Required Sections

Every tech spec document must contain the following five sections, in this exact order:

| Section No. | Section Name | Required | Description |
|------------|--------------|----------|-------------|
| 1 | Scope | Yes | Defines where the spec applies, including relevant packages or modules |
| 2 | Key Requirements | Yes | Core rules organized by subtopic |
| 3 | Full Specification Details | Yes | Expanded explanation of the key requirements |
| 4 | Correct Examples | Yes | Code examples that comply with the spec |
| 5 | Incorrect Examples | Yes | Code examples that violate the spec, plus correction guidance |

### 2.2 Detailed Section Requirements

#### Chapter 1: Scope

- Use concise paragraphs to describe the scope
- Clearly identify the relevant package paths (for example, the `controller` package or `service` package)
- If multiple modules are involved, list them separately

#### Chapter 2: Key Requirements

- Split content into sub-sections based on logical grouping (such as 2.1, 2.2, 2.3)
- Each sub-section should focus on one theme
- Each rule should appear on its own line in list format

#### Chapter 3: Full Specification Details

- Expand on the key requirements from Chapter 2 in detail
- May include supplementary tables, process descriptions, annotation notes, and similar material
- May include reference information such as naming rules, type mappings, and common patterns

#### Chapter 4: Correct Examples

- Provide 3-7 representative correct examples
- Each example should demonstrate one requirement point
- Use the format `// ✅ Correct Example N: Short description`

#### Chapter 5: Incorrect Examples

- Provide 5-10 common incorrect examples
- Each incorrect example should include an explanation of the issue and a suggested correction
- Use the format `// ❌ Incorrect N: Error description`

## 3. Rule Severity Levels

### 3.1 Three Severity Levels

| Level | Marker | Meaning | Expected Coding Behavior |
|------|--------|---------|--------------------------|
| Must | `**MUST**` | Mandatory requirement that cannot be violated | Always implement |
| Forbid | `**FORBID**` | Explicitly disallowed behavior | Never do it |
| Norm | `**NORM**` | Recommended requirement | Follow unless there is a strong reason not to |

### 3.2 Marker Format

```markdown
- **MUST**: Add the `@RestController` annotation
- **FORBID**: Use physical deletion
- **NORM**: List queries should sort by creation time in descending order by default
```

### 3.3 Marker Usage Principles

- Each rule should use exactly one severity marker
- The marker must be followed by a colon, then the actual requirement
- Try to keep severity levels consistent within the same sub-section when appropriate

## 4. Example Writing Standards

### 4.1 Correct Example Format

```markdown
// ✅ Correct Example 1: Brief description of the requirement point covered
Actual code content
```

### 4.2 Incorrect Example Format

```markdown
// ❌ Incorrect 1: Description of the wrong behavior
Actual code content
// ✅ Correct approach: How to fix it
```

### 4.3 Example Writing Principles

- Example code must be runnable, or at minimum syntactically valid
- Correct and incorrect examples should cover the same functional point so they form a clear contrast
- Incorrect examples must point out the exact problem location, typically with comments
- Example entities should use domain vocabulary (for example, voucher type or order)
- Each example should focus on a single requirement point; avoid putting multiple unrelated mistakes into one example

## 5. Content Organization Principles

### 5.1 From Abstract to Concrete

1. Chapter 1 defines the scope (most abstract)
2. Chapter 2 presents the core rules (moderately abstract)
3. Chapter 3 expands the details (more concrete)
4. Chapters 4-5 provide code examples (most concrete)

### 5.2 Logical Grouping

- Place related rules in the same sub-section
- Arrange sub-sections by execution order or dependency relationship
- When referencing another sub-section, use explicit section numbering

### 5.3 Independence Requirement

- Each spec document should be complete and self-contained
- When referencing another spec, provide the document name and section number
- Avoid duplicating the same content across documents

## 6. Code Example Style

### 6.1 Java Example Style

- Use the package prefix `com.example.erp.grd.gl`
- Use domain-specific entity names such as `GlVoucherType`
- Show annotations and imports in full
- Use English comments for explanation

### 6.2 Frontend Example Style

- Use PascalCase for component names
- Define TypeScript types completely
- Use English comments and error messages
- Follow React Hooks conventions

### 6.3 SQL Example Style

- Use uppercase SQL keywords
- Wrap field names in backticks
- Use English comments

## 7. Naming and Formatting Conventions

### 7.1 Document Naming

Format: `tech-spec-{module-name}.md`

Examples:
- `tech-spec-controller.md`
- `tech-spec-react-component.md`
- `tech-spec-database.md`

### 7.2 Heading Format

- H1: `# {Module Name} Tech Spec`
- H2: `## 1. Scope`, `## 2. Key Requirements`, and so on
- H3: `### 2.1 Subtopic`, `### 2.2 Subtopic`, and so on

### 7.3 Code Block Format

- Use ` ```java ` for Java code
- Use ` ```typescript ` or ` ```tsx ` for TypeScript code
- Use ` ```sql ` for SQL code
- Use ` ```xml ` for XML code

## 8. Quality Checklist

### 8.1 Structural Completeness

- [ ] Includes all five required sections
- [ ] Section numbering is complete and correct
- [ ] Sub-sections are organized logically

### 8.2 Clarity of Requirements

- [ ] Every rule has an explicit severity marker
- [ ] Requirement descriptions are unambiguous
- [ ] Forbidden behaviors are clearly listed

### 8.3 Adequacy of Examples

- [ ] Correct examples cover the main requirement points
- [ ] Incorrect examples cover common violations
- [ ] Every example has clear explanatory comments

### 8.4 Formatting Consistency

- [ ] Document naming follows the convention
- [ ] Code blocks use the correct language markers
- [ ] List indentation is consistent

## 9. Recommended Writing Process

### 9.1 Preparation Phase

1. Clarify the scope and goal of the spec
2. Collect common patterns and issues in the domain
3. Determine which requirement points must be covered

### 9.2 Writing Phase

1. Write Chapter 1 Scope first
2. Organize the core rules and write Chapter 2
3. Expand the details and write Chapter 3
4. Write correct examples for Chapter 4
5. Write incorrect examples for Chapter 5

### 9.3 Review Phase

1. Check structural completeness
2. Verify example code correctness
3. Ensure requirement descriptions are unambiguous
4. Unify formatting and style
