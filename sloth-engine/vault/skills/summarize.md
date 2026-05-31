---
name: Summarize
description: Condense any content into a structured summary
category: writing
---

Summarize the following content.

**Content**: {{ content }}
**Format**: {{ format | default("bullets") }}
**Length**: {{ length | default("concise") }}
**Focus**: {{ focus | default("") }}

Requirements:
- Extract the 5-8 most important points
- Use the specified format: bullets, numbered, paragraphs, or table
- Keep it {{ length }} (concise = 1-2 sentences per point, detailed = 1 paragraph per point)
- If focus is specified, prioritize that aspect
- Lead with a one-line thesis statement
- End with key takeaway or action item if applicable
