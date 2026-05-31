---
name: Landing Page
description: Generate a complete landing page with hero, features, CTA
category: web
---

Create a production-quality landing page as an HTML artifact.

**Topic**: {{ topic }}
**Style**: {{ style | default("modern, clean, professional") }}
**Brand colors**: {{ colors | default("#667eea, #764ba2") }}

Requirements:
- Single-page responsive HTML with inline CSS (no external dependencies)
- Hero section with headline, subtext, and CTA button
- 3-6 feature cards with icons (use Unicode symbols)
- Footer with placeholder links
- Smooth scroll, hover effects, gradient background
- Mobile-friendly (flexbox/grid)
- Use the brand colors as primary/secondary palette

Output: Create the page as an artifact with type "html". Return the preview URL.
