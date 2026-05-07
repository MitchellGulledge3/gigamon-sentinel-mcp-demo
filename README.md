# Gigamon Sentinel MCP Demo

This repo is a GitHub-ready reference implementation for a Gigamon developer who wants to show an end-to-end Microsoft Sentinel custom MCP tool integration.

## What this demo proves

A Gigamon developer can:

1. Start from the official Sentinel connector table schema.
2. Use Sentinel LogSeeder to create a demo custom table and seed realistic telemetry.
3. Publish high-value KQL questions as Sentinel custom MCP tools.
4. Call those tools from a polished local browser app or any future agent runtime.

## Demo table

The demo table is `GigamonCcfMcpDemo_CL`. It uses the same column names and types as the official Sentinel Gigamon CCF table schema from:

```text
https://raw.githubusercontent.com/Azure/Azure-Sentinel/master/Solutions/Gigamon%20Connector/Data%20Connectors/Gigamon_CCF/Gigamon_table.json
```

The table name is intentionally different from `GigamonV2_CL` so the demo never collides with a production connector table.

## End-to-end use case

**Use case:** a SOC analyst asks whether Gigamon network visibility data shows lateral movement, DNS anomalies, or TLS risk during a suspected intrusion.

The MCP tools expose that investigation as reusable capabilities:

| Tool | Purpose |
| --- | --- |
| `Gigamon_Visibility_Posture_Summary` | Executive posture summary: events, sources, destinations, apps, protocols, bytes |
| `Gigamon_Lateral_Movement_Triage` | Triage SMB/RDP/SSH east-west movement candidates |
| `Gigamon_DNS_Anomaly_Hunt` | Hunt suspicious or slow DNS activity |
| `Gigamon_TLS_Risk_Summary` | Summarize weak TLS, weak keys, expiring certs, JA3/JA3S signals |
| `Gigamon_Top_Talkers_By_App` | Find top applications, sources, destinations, bytes, packets |

## Seed data with LogSeeder

Copy `logseeder/GigamonCcfMcpDemo_CL.json` into your `sentinel-logseeder/schemas/` folder, then run:

```bash
cp /path/to/gigamon-sentinel-mcp-demo/logseeder/GigamonCcfMcpDemo_CL.json ./schemas/
cd /path/to/sentinel-logseeder
pwsh -NoLogo -NoProfile -ExecutionPolicy Bypass \
  -File ./scripts/Invoke-SampleDataIngestion.ps1 \
  -TableName GigamonCcfMcpDemo_CL \
  -Schema ./schemas/GigamonCcfMcpDemo_CL.json \
  -RowCount 250 \
  -TimeWindowMinutes 1440 \
  -Deploy -Ingest
```

Verify rows:

```kql
GigamonCcfMcpDemo_CL
| summarize RowCount=count(), FirstSeen=min(TimeGenerated), LastSeen=max(TimeGenerated)
```

## Publish custom MCP tools

Create a Sentinel custom MCP collection, then publish each file in `mcp-tools/` as a KQL-backed tool. The tool input should include `workspaceId`; the KQL in this repo assumes the table already exists in that workspace.

Suggested collection name:

```text
Gigamon-Sentinel-MCP-Demo
```

This repo includes a helper script that publishes every KQL file in `mcp-tools/`:

```bash
cd /path/to/gigamon-sentinel-mcp-demo
python3 scripts/publish-mcp-tools.py \
  --collection Gigamon-Sentinel-MCP-Demo \
  --workspace-id <log-analytics-workspace-customer-id>
```

## Browser demo

Run the included local browser app:

```bash
cd /path/to/gigamon-sentinel-mcp-demo/web
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` and set:

```text
MCP_DEFAULT_ARGUMENTS={"workspaceId":"<log-analytics-workspace-customer-id>"}
```

Then start the app:

```bash
python3 web_app.py
```

Open:

```text
http://127.0.0.1:8765
```

Type prompts like:

```text
Summarize Gigamon visibility posture
Show possible lateral movement
Hunt DNS anomalies
Summarize TLS risk
Show top talkers by app
```

## Talk track

> Gigamon does not need to ship a whole chatbot to participate in agent workflows. The developer ships focused tools over the data they know best. Microsoft Sentinel handles the data plane, MCP gives the tool contract, and any agent surface can call the capability.

## Files

| Path | Purpose |
| --- | --- |
| `logseeder/GigamonCcfMcpDemo_CL.json` | LogSeeder schema derived from the official Gigamon connector schema |
| `mcp-tools/*.kql` | KQL definitions for custom Sentinel MCP tools |
| `scripts/publish-mcp-tools.py` | Publishes the KQL files as Sentinel custom MCP tools |
| `web/` | Local Edge/browser app that routes prompts to the Gigamon MCP tools |
| `docs/demo-script.md` | Step-by-step presenter script |
