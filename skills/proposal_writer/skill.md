# Skill: Proposal Writer

Orchestrates company research, PDF report formatting, PowerPoint slide compilation, and email delivery.

## Execution Workflow

1. **Structured Lookup**: Queries the `search_company` tool for core metadata attributes.
2. **News Search**: Queries the `search_web` tool for recent web snippets and links.
3. **PDF Generation**: Renders a formal partnership overview report PDF using `reportlab`.
4. **PowerPoint slide deck**: Renders a strategic slide deck file using `python-pptx`.
5. **Email Delivery**: Sends an email via the `GmailConnector` sharing download links to the target recipient.
