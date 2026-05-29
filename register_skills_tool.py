"""Register skills tool as OpenWebUI custom tool."""
import json
import urllib.request
import sys

BASE = "http://192.168.0.33:3000"
EMAIL = "aaron@slothitude.com"
PASSWORD = "Sloth2026!"

# Get token
req = urllib.request.Request(
    f"{BASE}/api/v1/auths/signin",
    data=json.dumps({"email": EMAIL, "password": PASSWORD}).encode(),
    headers={"Content-Type": "application/json"},
)
resp = urllib.request.urlopen(req)
token = json.loads(resp.read().decode())["token"]

# Check if skills tool already exists
req = urllib.request.Request(
    f"{BASE}/api/v1/tools/",
    headers={"Authorization": f"Bearer {token}"},
)
resp = urllib.request.urlopen(req)
tools = json.loads(resp.read().decode())

# Delete old skills tool if exists
for t in tools:
    if t.get("name") == "skills" or t.get("id", "").startswith("skills"):
        del_req = urllib.request.Request(
            f"{BASE}/api/v1/tools/{t['id']}",
            headers={"Authorization": f"Bearer {token}"},
            method="DELETE",
        )
        urllib.request.urlopen(del_req)
        print(f"Deleted old tool: {t['id']}")

# Create skills tool
tool_body = {
    "id": "skills",
    "name": "skills",
    "meta": {
        "description": "Skills system — reusable prompt templates from vault/skills/. Load, list, and execute skill templates with variables.",
    },
    "content": '''"""
title: Skills
description: Reusable prompt templates loadable on demand from vault/skills/
required_open_webui_version: 0.3.0
version: 0.1.0
"""

import json
import urllib.request


SKILLS_BASE = "http://localhost:7700"


class Tools:
    def __init__(self):
        pass

    def skill_list(self) -> str:
        """
        List all available skills (reusable prompt templates).
        :return: JSON list of skills with names, descriptions, and categories.
        """
        req = urllib.request.Request(f"{SKILLS_BASE}/skills/list")
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.read().decode()

    def skill_load(self, name: str) -> str:
        """
        Load a skill template by name to see its content and required variables.
        :param name: Skill name (e.g. 'landing-page', 'chart', 'email-draft').
        :return: Skill template content with metadata.
        """
        req = urllib.request.Request(
            f"{SKILLS_BASE}/skills/load?name={name}"
        )
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.read().decode()

    def skill_execute(self, name: str, variables: str = "") -> str:
        """
        Execute a skill: renders the template with variables and returns the prompt.
        Use this to load a reusable workflow (landing page, chart, form, email, etc).
        :param name: Skill name (e.g. 'landing-page', 'chart', 'form', 'email-draft', 'report', 'summarize').
        :param variables: JSON object or comma-separated key=value pairs for template variables.
            Example: '{"topic":"SaaS product","style":"minimal"}' or 'topic=SaaS product,style=minimal'
        :return: Rendered prompt ready to execute.
        """
        body = json.dumps({"name": name, "variables": variables}).encode()
        req = urllib.request.Request(
            f"{SKILLS_BASE}/skills/execute",
            data=body,
            headers={"Content-Type": "application/json"},
        )
        resp = urllib.request.urlopen(req, timeout=10)
        return resp.read().decode()
''',
    "access_control": None,
}

req = urllib.request.Request(
    f"{BASE}/api/v1/tools/create",
    data=json.dumps(tool_body).encode(),
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    },
    method="POST",
)
try:
    resp = urllib.request.urlopen(req)
    result = json.loads(resp.read().decode())
    print(f"Skills tool registered: {result.get('id', 'ok')}")
except urllib.error.HTTPError as e:
    err = e.read().decode()
    print(f"Error: {e.code} {err}")
