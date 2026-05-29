"""Add ai.retromonkey.com.au route to Traefik for OpenWebUI."""
import yaml

ROUTE_FILE = "C:/traefik/routes.yml"

with open(ROUTE_FILE, "r") as f:
    config = yaml.safe_load(f)

http = config["http"]

# Add openwebui service
http["services"]["openwebui"] = {
    "loadBalancer": {
        "servers": [{"url": "http://127.0.0.1:3000"}]
    }
}

# Add HTTPS router
http["routers"]["https_openwebui"] = {
    "rule": "Host(`ai.retromonkey.com.au`)",
    "service": "openwebui",
    "entryPoints": ["websecure"],
    "tls": {"certResolver": "letsencrypt"},
}

# Add HTTP→HTTPS redirect router
http["routers"]["openwebui_http"] = {
    "rule": "Host(`ai.retromonkey.com.au`)",
    "service": "openwebui",
    "entryPoints": ["web"],
    "middlewares": ["redirect-to-https"],
}

# Add redirect middleware
http["middlewares"]["redirect-to-https"] = {
    "redirectScheme": {"scheme": "https", "permanent": True}
}

with open(ROUTE_FILE, "w") as f:
    yaml.dump(config, f, default_flow_style=False, sort_keys=False)

print("Done. Traefik will auto-reload.")
