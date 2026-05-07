# Demo script

## Setup

1. Show the official Gigamon Sentinel connector schema.
2. Show `logseeder/GigamonCcfMcpDemo_CL.json`, derived from that schema.
3. Run LogSeeder to create and seed `GigamonCcfMcpDemo_CL`.
4. Publish the MCP tools from `mcp-tools/`.
5. Start the terminal demo.

## Live prompts

1. `Summarize Gigamon visibility posture`
2. `Show possible lateral movement`
3. `Hunt DNS anomalies`
4. `Summarize TLS risk`
5. `Show top talkers by app`

Run them in one interactive terminal:

```bash
python3 terminal_demo.py --show-raw
```

## Close

This is a developer pattern, not a one-off demo. Gigamon can ship the schema, suggested detections, and MCP tool definitions as developer assets so customer agents can reason over Gigamon visibility data in Sentinel.
