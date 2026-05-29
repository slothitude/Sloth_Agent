import sqlite3, json, time

db = sqlite3.connect("/app/backend/data/webui.db")
user_id = "6ae5d78a-71f1-416d-a783-039587f2734b"
now = int(time.time())

agents = [
    {
        "id": "researcher",
        "base_model_id": "zai-glm-5.1",
        "name": "Researcher",
        "meta": json.dumps({
            "profile_image_url": "/static/favicon.png",
            "description": "Deep research specialist - multi-source analysis, fact-checking, synthesis",
            "tools": ["web_search", "url_fetcher"],
        }),
        "params": json.dumps({
            "system_prompt": "You are a research specialist. Thoroughly investigate topics by searching multiple sources, cross-referencing claims, and producing well-cited balanced analyses. Always cite sources. Be thorough but concise.",
            "function_calling": "native",
        }),
    },
    {
        "id": "coder",
        "base_model_id": "zai-glm-5.1",
        "name": "Coder",
        "meta": json.dumps({
            "profile_image_url": "/static/favicon.png",
            "description": "Code specialist - writes clean, tested code across languages",
            "tools": [],
        }),
        "params": json.dumps({
            "system_prompt": "You are a senior software engineer. Write clean, efficient, well-documented code. Consider edge cases, security, and performance. Follow existing style. Test logic before writing.",
            "function_calling": "native",
        }),
    },
    {
        "id": "writer",
        "base_model_id": "zai-glm-5.1",
        "name": "Writer",
        "meta": json.dumps({
            "profile_image_url": "/static/favicon.png",
            "description": "Writing specialist - prose, copy, reports, documentation",
            "tools": ["web_search"],
        }),
        "params": json.dumps({
            "system_prompt": "You are a professional writer and editor. Produce clear, engaging, well-structured content. Adapt tone and style to context. Be concise - every word should earn its place.",
            "function_calling": "native",
        }),
    },
]

for a in agents:
    db.execute(
        "INSERT OR REPLACE INTO model (id, user_id, base_model_id, name, meta, params, created_at, updated_at, is_active) VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1)",
        (a["id"], user_id, a["base_model_id"], a["name"], a["meta"], a["params"], now, now),
    )
    print(f"Created: {a['id']} ({a['name']})")

db.commit()
print("Done - 3 sub-agents created")
