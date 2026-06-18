# Skill: Sales Account Research

Researches a target company using structured lookup tools and web searches, then synthesizes a report.

## Orchestration Flow

1. **Structured Lookup**: Calls the `search_company` tool to find foundational metadata (HQ, size, industry, year founded).
2. **Web Search**: Calls the `search_web` tool to pull relevant news articles and snippets.
3. **Verification**: Confirms both steps completed successfully and returned content.
4. **Synthesis**: Formats the compiled research as a clean Markdown briefing document.
