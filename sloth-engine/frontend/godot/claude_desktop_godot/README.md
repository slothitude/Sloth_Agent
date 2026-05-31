# Claude Desktop UI — Godot 4.6

A pixel-faithful recreation of the Claude Desktop interface built entirely in
Godot 4.6 using **pure GDScript + StyleBoxFlat overrides** — no textures, no
external assets, no plugins required.

## Quick Start

1. Open Godot 4.6 → Import Project → point at this folder
2. Run with F5 — the main scene loads automatically
3. Type a message and press **Enter** or click the send button

## Architecture

```
claude_desktop_godot/
├── project.godot
├── icon.svg
├── scenes/
│   └── main.tscn          ← Full layout tree
├── scripts/
│   ├── main.gd            ← All logic: styling, messaging, streaming, drawing
│   ├── sidebar.gd         ← Search filter, conversation history
│   └── chat_message.gd    ← Reusable bubble component
└── themes/
    └── claude_theme.tres  ← Palette reference (used manually via code)
```

## Colour Palette

| Token              | Hex       | Usage                        |
|--------------------|-----------|------------------------------|
| `C_BG`             | `#1a1a1a` | App background               |
| `C_SIDEBAR`        | `#171717` | Sidebar panel                |
| `C_SURFACE_RAISED` | `#2a2a2a` | Input box, user bubbles      |
| `C_BORDER`         | `#333333` | Panel outlines               |
| `C_ACCENT`         | `#da7756` | Claude brand orange          |
| `C_TEXT_PRIMARY`   | `#ececec` | Main body text               |
| `C_TEXT_MUTED`     | `#6b6b6b` | Timestamps, metadata         |

## Features Implemented

- [x] Sidebar with conversation history list
- [x] Search filtering of conversation history
- [x] Welcome screen with greeting + 4 suggestion cards
- [x] User message bubbles (right-aligned, rounded)
- [x] Claude response rendering with name + icon row
- [x] Animated typing indicator (● ●● ●●●)
- [x] Streaming text simulation (character-by-character)
- [x] Send on Enter / Shift+Enter for newline
- [x] Custom-drawn Claude spoke logo (no image assets)
- [x] Model selector chip in topbar
- [x] Profile row with avatar placeholder
- [x] StyleBoxFlat overrides everywhere (no theme file needed)
- [x] Auto-scroll to latest message

## Extending

**Add real AI responses**: Replace `RESPONSES` array in `main.gd` and hook into
HTTPRequest node to call `https://api.anthropic.com/v1/messages`.

**Add markdown rendering**: Replace `RichTextLabel` with a custom
`MarkdownLabel` using BBCode translation for `**bold**`, `_italic_`, and
`` `code` `` spans.

**Add file attachments**: Wire the `AttachBtn` to a `FileDialog` node and
encode the result as base64 for the API content array.

## Notes

- Layout uses `HBoxContainer` with `SIZE_EXPAND_FILL` for the responsive split
- No `Theme` resource needed — all style is applied via `add_theme_*_override()`
- The Claude logo is drawn procedurally via `_draw()` — 8-spoke asterisk
- `TextEdit` with `scroll_fit_content_height = true` handles auto-growing input
