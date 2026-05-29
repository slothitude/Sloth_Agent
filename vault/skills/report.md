---
name: Report
description: Generate a formatted data report as HTML artifact
category: writing
---

Create a formatted, professional report as an HTML artifact.

**Topic**: {{ topic }}
**Data/Findings**: {{ findings | default("(describe key findings)") }}
**Format**: {{ format | default("executive summary") }}

Requirements:
- Clean HTML document with print-friendly CSS
- Title page with topic and date
- Executive summary section (if applicable)
- Data tables with alternating row colors
- Key metrics highlighted with callout boxes
- Section headings with table of contents
- Charts if data is quantitative (inline SVG)
- Professional typography (serif body, sans-serif headings)
- Page-break hints for multi-page printing

Output: Create as an artifact with type "html". Return the preview URL.
