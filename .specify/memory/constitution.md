# Holiday Meal Planner Constitution

## Core Principles

### I. Human Oversight Is Mandatory
Every autonomous contribution must receive human review before merge. Agents operate within guardrails; engineers are accountable for final outcomes. All documentation updates and Python scripts require validation before deployment.

### II. Build for Observability and Reproducibility
All features must include logging, metrics, and deterministic workflows so issues can be traced quickly. Python scripts must log file operations and URL access attempts with appropriate detail for debugging.

### III. Security by Default
Follow least privilege for credentials, validate all inputs, and prefer managed secrets. Never ship hard-coded tokens. Python scripts accessing public URLs must validate inputs, use secure connection protocols (HTTPS), and handle authentication safely.

### IV. Tests Drive Confidence
Write automated tests before or alongside new logic. Refuse to ship when critical coverage is missing. All Python file I/O operations and URL access functions must have corresponding unit tests.

### V. Documentation Matters
Capture assumptions, API contracts, and hand-off notes in the repo. Agents and humans rely on clear context to move fast safely. Document all external URL dependencies, file structure expectations, and data formats.

### VI. Safe File I/O Operations
All Python scripts must handle file operations defensively: validate file paths, use context managers for file handles, implement proper error handling, and never assume file system state. Use pathlib for cross-platform compatibility.

### VII. Secure URL Access
When accessing public URLs, implement proper error handling, timeout controls, and response validation. Use requests library with appropriate session management and respect rate limits. Log all network operations for observability.

### VIII. Think Before Coding
Don't assume. Don't hide confusion. Surface tradeoffs. State assumptions explicitly—if uncertain, ask rather than guess. Present multiple interpretations when ambiguity exists. Push back when warranted if a simpler approach is available.

### IX. Simplicity First
Minimum code that solves the problem. Nothing speculative. No features beyond what was asked, no abstractions for single-use code, no "flexibility" that wasn't requested. If 200 lines could be 50, rewrite it.

### X. Surgical Changes
Touch only what you must. Clean up only your own mess. When editing existing code, don't "improve" adjacent code, comments, or formatting. Match existing style, even if you'd do it differently.

### XI. Goal-Driven Execution
Define success criteria. Loop until verified. Transform imperative tasks into verifiable goals with clear success metrics. For multi-step tasks, state a brief plan with what each step accomplishes and how to verify it.

## Technology Requirements

### Python Standards
- Use Python 3.8+ with type hints for all public functions
- Follow PEP 8 style guidelines with line length limit of 88 characters
- Use pathlib for file operations and requests library for HTTP calls
- Implement proper logging using the logging module, not print statements

### File I/O Safety
- Always use context managers (with statements) for file operations
- Validate file paths before operations using pathlib.Path.resolve()
- Handle common exceptions: FileNotFoundError, PermissionError, OSError
- Never write to files without explicit permission validation

### External Dependencies
- Document all public URL dependencies in requirements.txt and README
- Implement retry logic with exponential backoff for network operations
- Cache responses when appropriate to minimize external API calls
- Validate SSL certificates and use HTTPS exclusively

## Development Workflow

### Code Review Process
- All Python scripts require automated testing before review
- Security review mandatory for any code accessing external URLs
- Performance testing required for file processing operations
- Documentation review for any public API changes

### Quality Gates
- 90% test coverage minimum for all Python modules
- All external dependencies must have security scanning approval
- File I/O operations must pass safety validation tests
- URL access patterns must be reviewed for data privacy compliance

## Governance

Constitution supersedes all other practices. Amendments require documentation, approval, and migration plan. All PRs/reviews must verify compliance with these principles. Complexity must be justified with explicit reasoning. Use project documentation for runtime development guidance.

**Version**: 1.0.0 | **Ratified**: 2026-03-18 | **Last Amended**: 2026-03-18
