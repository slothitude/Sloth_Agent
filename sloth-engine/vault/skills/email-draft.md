---
name: Email Draft
description: Draft a professional email with proper formatting
category: writing
---

Draft a professional email.

**To**: {{ recipient | default("(recipient)") }}
**Subject**: {{ subject | default("(draft a subject line)") }}
**Key points**: {{ points }}
**Tone**: {{ tone | default("professional") }}

Requirements:
- Clear, concise subject line
- Professional greeting and sign-off
- Well-structured body (short paragraphs)
- If business: include call-to-action or next steps
- If follow-up: reference prior context
- Match the specified tone (professional, friendly, formal, casual)

Output the email ready to send.
