---
name: Chart
description: Generate an interactive chart visualization as HTML/SVG
category: visualization
---

Create an interactive chart visualization as an HTML artifact.

**Data**: {{ data }}
**Chart type**: {{ chart_type | default("bar") }}
**Title**: {{ title | default("Chart") }}

Supported chart types: bar, line, pie, area, scatter, doughnut

Requirements:
- Pure HTML/CSS/JavaScript (no external libraries)
- SVG-based rendering for sharp scaling
- Hover tooltips on data points
- Legend if multiple series
- Responsive sizing
- Clean color palette with good contrast
- Include axis labels and title

Use CSS animations for chart entrance (fade-in, grow).

Output: Create as an artifact with type "html". Return the preview URL.
