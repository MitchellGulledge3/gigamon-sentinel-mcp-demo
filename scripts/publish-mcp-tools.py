from __future__ import annotations

import argparse
import json
import pathlib
import subprocess
import sys
import urllib.error
import urllib.request

SENTINEL_RESOURCE_ID = "4500ebfb-89b6-4b14-a480-7f749797bfcd"
API_BASE = "https://api.securityplatform.microsoft.com/aiprimitives/mcpToolCollections"

DESCRIPTIONS = {
    "Gigamon_Visibility_Posture_Summary": "Summarize Gigamon visibility posture across events, sources, destinations, protocols, apps, and bytes.",
    "Gigamon_Lateral_Movement_Triage": "Triage possible east-west lateral movement using SMB, RDP, SSH, interfaces, bytes, RTT, and source/destination pairs.",
    "Gigamon_DNS_Anomaly_Hunt": "Hunt DNS anomalies such as failed lookups, slow responses, suspicious query names, and affected source IPs.",
    "Gigamon_TLS_Risk_Summary": "Summarize TLS risk using protocol versions, weak key sizes, expiring certificates, issuers, CNs, and JA3 signals.",
    "Gigamon_Top_Talkers_By_App": "Rank Gigamon-observed applications by bytes, packets, sources, and destinations.",
}


def az_token() -> str:
    completed = subprocess.run(
        [
            "az",
            "account",
            "get-access-token",
            "--resource",
            SENTINEL_RESOURCE_ID,
            "--query",
            "accessToken",
            "-o",
            "tsv",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def request(method: str, url: str, token: str, payload: dict) -> dict:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        details = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"{method} {url} failed: HTTP {exc.code}: {details}") from exc


def tool_payload(collection: str, workspace_id: str, query_path: pathlib.Path) -> dict:
    name = query_path.stem
    return {
        "name": name,
        "title": name.replace("_", " "),
        "description": DESCRIPTIONS[name],
        "collectionName": collection,
        "properties": {
            "mcpToolType": "Kqs",
            "queryFormat": query_path.read_text().strip(),
            "arguments": {
                "type": "object",
                "properties": {
                    "workspaceId": {
                        "type": "string",
                        "description": "Log Analytics workspace/customer ID to query.",
                    }
                },
                "required": ["workspaceId"],
            },
            "defaultArgumentValues": {"workspaceId": workspace_id},
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Publish Gigamon KQL files as Sentinel custom MCP tools.")
    parser.add_argument("--collection", default="Gigamon-Sentinel-MCP-Demo")
    parser.add_argument("--workspace-id", required=True)
    parser.add_argument("--tools-dir", default=str(pathlib.Path(__file__).parents[1] / "mcp-tools"))
    args = parser.parse_args()

    token = az_token()
    collection_payload = {
        "name": args.collection,
        "title": "Gigamon Sentinel MCP Demo",
        "description": "Custom Sentinel MCP tools for a Gigamon CCF end-to-end developer demo.",
    }
    print(f"Publishing collection: {args.collection}")
    print(json.dumps(request("PUT", f"{API_BASE}/{args.collection}", token, collection_payload), indent=2))

    for query_path in sorted(pathlib.Path(args.tools_dir).glob("*.kql")):
        payload = tool_payload(args.collection, args.workspace_id, query_path)
        print(f"\nPublishing tool: {payload['name']}")
        print(json.dumps(request("PUT", f"{API_BASE}/{args.collection}/tools/{payload['name']}", token, payload), indent=2))

    return 0


if __name__ == "__main__":
    sys.exit(main())
