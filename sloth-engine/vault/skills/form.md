---
name: Form
description: Generate a styled, functional form as an HTML artifact
category: web
---

Create a styled, functional web form as an HTML artifact.

**Form purpose**: {{ purpose }}
**Fields**: {{ fields | default("name, email, message") }}
**Style**: {{ style | default("modern, floating labels") }}

Requirements:
- Single HTML file with inline CSS and JavaScript
- Floating label inputs (CSS-only animation)
- Client-side validation with inline error messages
- Submit handler that collects data and shows a success state
- Responsive layout (stacks on mobile)
- Accessible: proper labels, focus states, ARIA attributes
- Clean, professional appearance

Output: Create as an artifact with type "html". Return the preview URL.
