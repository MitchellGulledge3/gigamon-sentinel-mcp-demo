from __future__ import annotations

"""Local browser experience for the Gigamon Sentinel MCP demo.

This file intentionally keeps the UI, routing logic, and web endpoints together
so a Gigamon developer can run one file and understand the end-to-end path:
browser prompt -> local API -> Sentinel MCP tool -> Log Analytics result.
"""

import argparse
import html
import json
import os
from typing import Any

from aiohttp import web
from dotenv import load_dotenv

from sentinel_mcp_demo.client import MCPTool, MCPToolResult, SentinelMCPClient
from sentinel_mcp_demo.mock import MockSentinelMCPClient

# Canonical MCP tool names published by `scripts/publish-mcp-tools.py`.
GIGAMON_TOOLS = {
    "visibility": "Gigamon_Visibility_Posture_Summary",
    "lateral": "Gigamon_Lateral_Movement_Triage",
    "dns": "Gigamon_DNS_Anomaly_Hunt",
    "tls": "Gigamon_TLS_Risk_Summary",
    "talkers": "Gigamon_Top_Talkers_By_App",
}

# A simple keyword router keeps the demo deterministic and explainable. It is
# not meant to replace an LLM planner; it shows which tool each prompt triggers.
TOOL_ROUTES = [
    (("lateral", "east-west", "rdp", "smb", "ssh", "movement"), GIGAMON_TOOLS["lateral"]),
    (("dns", "domain", "lookup", "nxdomain", "servfail"), GIGAMON_TOOLS["dns"]),
    (("tls", "ssl", "cert", "certificate", "ja3", "weak key"), GIGAMON_TOOLS["tls"]),
    (("top", "talker", "app", "bytes", "packets", "bandwidth"), GIGAMON_TOOLS["talkers"]),
]


# The demo is a single-page app embedded as a string to keep setup friction low:
# no frontend build chain, no npm install, and no separate static-file server.
HTML = """<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Gigamon Visibility Copilot</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f5f5f5;
      --panel: rgba(255,255,255,.82);
      --text: #1f1f1f;
      --muted: #616161;
      --brand: #6264a7;
      --brand2: #0078d4;
      --line: rgba(0,0,0,.08);
      --shadow: 0 24px 60px rgba(31,31,31,.16);
      --radius: 22px;
    }

    * { box-sizing: border-box; }

    body {
      margin: 0;
      min-height: 100vh;
      font-family: "Segoe UI", system-ui, -apple-system, BlinkMacSystemFont, sans-serif;
      color: var(--text);
      background:
        radial-gradient(circle at 12% 18%, rgba(98,100,167,.22), transparent 28%),
        radial-gradient(circle at 82% 6%, rgba(0,120,212,.2), transparent 26%),
        linear-gradient(135deg, #fbfbfd 0%, #eef3fb 50%, #f7f2fb 100%);
    }

    .shell {
      width: min(1180px, calc(100vw - 40px));
      margin: 0 auto;
      padding: 34px 0 28px;
    }

    header {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 20px;
      margin-bottom: 24px;
    }

    .brand {
      display: flex;
      align-items: center;
      gap: 14px;
    }

    .logo {
      width: 46px;
      height: 46px;
      border-radius: 13px;
      display: grid;
      place-items: center;
      color: white;
      font-weight: 800;
      letter-spacing: -.04em;
      background: linear-gradient(135deg, var(--brand), var(--brand2));
      box-shadow: 0 12px 28px rgba(98,100,167,.3);
    }

    h1 {
      margin: 0;
      font-size: 28px;
      letter-spacing: -.04em;
    }

    .subtitle {
      margin-top: 3px;
      color: var(--muted);
      font-size: 14px;
    }

    .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      padding: 9px 12px;
      border: 1px solid var(--line);
      border-radius: 999px;
      background: rgba(255,255,255,.7);
      color: #242424;
      font-size: 13px;
      box-shadow: 0 8px 24px rgba(0,0,0,.06);
    }

    .dot {
      width: 9px;
      height: 9px;
      border-radius: 999px;
      background: #13a10e;
      box-shadow: 0 0 0 5px rgba(19,161,14,.12);
    }

    .hero {
      display: grid;
      grid-template-columns: 1.05fr .95fr;
      gap: 22px;
    }

    .card {
      border: 1px solid var(--line);
      border-radius: var(--radius);
      background: var(--panel);
      backdrop-filter: blur(18px);
      box-shadow: var(--shadow);
    }

    .conversation {
      min-height: 650px;
      display: flex;
      flex-direction: column;
      overflow: hidden;
    }

    .chat-head {
      padding: 22px 24px;
      border-bottom: 1px solid var(--line);
      display: flex;
      justify-content: space-between;
      gap: 16px;
      align-items: flex-start;
    }

    .chat-title {
      font-weight: 700;
      font-size: 16px;
    }

    .tool-name {
      color: var(--muted);
      font-size: 13px;
      margin-top: 3px;
    }

    .messages {
      flex: 1;
      padding: 22px;
      overflow: auto;
      display: flex;
      flex-direction: column;
      gap: 14px;
    }

    .msg {
      max-width: 88%;
      padding: 14px 16px;
      border-radius: 18px;
      line-height: 1.42;
      white-space: pre-wrap;
    }

    .msg.user {
      align-self: flex-end;
      color: white;
      background: linear-gradient(135deg, var(--brand), var(--brand2));
      border-bottom-right-radius: 6px;
    }

    .msg.assistant {
      align-self: flex-start;
      background: #fff;
      border: 1px solid var(--line);
      border-bottom-left-radius: 6px;
    }

    .composer {
      padding: 18px;
      border-top: 1px solid var(--line);
      background: rgba(255,255,255,.56);
    }

    form {
      display: flex;
      gap: 10px;
    }

    input {
      flex: 1;
      border: 1px solid rgba(0,0,0,.13);
      border-radius: 15px;
      padding: 14px 15px;
      font: inherit;
      outline: none;
      background: white;
    }

    input:focus {
      border-color: var(--brand2);
      box-shadow: 0 0 0 3px rgba(0,120,212,.14);
    }

    button {
      border: 0;
      border-radius: 15px;
      padding: 0 20px;
      color: white;
      font: inherit;
      font-weight: 700;
      cursor: pointer;
      background: linear-gradient(135deg, var(--brand), var(--brand2));
      box-shadow: 0 12px 26px rgba(0,120,212,.22);
    }

    button:disabled {
      cursor: wait;
      filter: grayscale(.25);
      opacity: .7;
    }

    .side {
      display: grid;
      gap: 18px;
      align-content: start;
    }

    .panel {
      padding: 22px;
    }

    .panel h2 {
      margin: 0 0 12px;
      font-size: 18px;
      letter-spacing: -.03em;
    }

    .value-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }

    .metric {
      border: 1px solid var(--line);
      border-radius: 16px;
      padding: 15px;
      background: rgba(255,255,255,.7);
    }

    .metric .label {
      color: var(--muted);
      font-size: 12px;
      text-transform: uppercase;
      letter-spacing: .08em;
    }

    .metric .value {
      margin-top: 7px;
      font-weight: 800;
      font-size: 24px;
      letter-spacing: -.04em;
    }

    .tags {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 10px;
    }

    .tag {
      padding: 7px 10px;
      border-radius: 999px;
      background: rgba(98,100,167,.1);
      color: #464775;
      font-size: 12px;
      font-weight: 650;
    }

    .steps {
      display: grid;
      gap: 12px;
      color: var(--muted);
      font-size: 14px;
    }

    .step {
      display: grid;
      grid-template-columns: 28px 1fr;
      gap: 10px;
      align-items: start;
    }

    .num {
      width: 28px;
      height: 28px;
      border-radius: 10px;
      display: grid;
      place-items: center;
      color: white;
      font-size: 13px;
      font-weight: 800;
      background: linear-gradient(135deg, var(--brand), var(--brand2));
    }

    .examples {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 12px;
    }

    .example {
      border: 1px solid var(--line);
      border-radius: 999px;
      padding: 8px 11px;
      background: white;
      cursor: pointer;
      color: #323130;
      font-size: 12px;
    }

    pre {
      margin: 10px 0 0;
      overflow: auto;
      white-space: pre-wrap;
      font-size: 12px;
      line-height: 1.35;
      color: #242424;
    }

    @media (max-width: 920px) {
      .hero { grid-template-columns: 1fr; }
      header { align-items: flex-start; flex-direction: column; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <header>
      <div class="brand">
        <div class="logo">G</div>
        <div>
          <h1>Gigamon Visibility Copilot</h1>
          <div class="subtitle">ISV custom MCP tool demo on Microsoft Sentinel sample data</div>
        </div>
      </div>
      <div class="pill"><span class="dot"></span><span id="mode">Connecting to Sentinel MCP</span></div>
    </header>

    <section class="hero">
      <div class="card conversation">
        <div class="chat-head">
          <div>
            <div class="chat-title">Ask a security question</div>
            <div class="tool-name" id="toolName">Loading tool...</div>
          </div>
          <div class="pill">local app -> MCP -> Sentinel</div>
        </div>
          <div class="messages" id="messages">
          <div class="msg assistant">Hi, I am wired to a real Gigamon Sentinel MCP collection. Ask about visibility posture, lateral movement, DNS anomalies, TLS risk, or top talkers.</div>
        </div>
        <div class="composer">
          <form id="queryForm">
            <input id="prompt" autocomplete="off" value="Summarize Gigamon visibility posture" />
            <button id="sendButton" type="submit">Ask</button>
          </form>
          <div class="examples">
            <button class="example" type="button">Summarize Gigamon visibility posture</button>
            <button class="example" type="button">Show possible lateral movement</button>
            <button class="example" type="button">Hunt DNS anomalies</button>
            <button class="example" type="button">Summarize TLS risk</button>
            <button class="example" type="button">Show top talkers by app</button>
          </div>
        </div>
      </div>

      <aside class="side">
        <div class="card panel">
          <h2>Live result cards</h2>
          <div class="value-grid">
            <div class="metric"><div class="label" id="metricLabel1">Metric 1</div><div class="value" id="metricValue1">--</div></div>
            <div class="metric"><div class="label" id="metricLabel2">Metric 2</div><div class="value" id="metricValue2">--</div></div>
            <div class="metric"><div class="label" id="metricLabel3">Metric 3</div><div class="value" id="metricValue3">--</div></div>
            <div class="metric"><div class="label" id="metricLabel4">Metric 4</div><div class="value" id="metricValue4">--</div></div>
          </div>
          <div class="tags" id="tags"></div>
        </div>

        <div class="card panel">
          <h2>What this proves</h2>
          <div class="steps">
            <div class="step"><div class="num">1</div><div>ISV publishes a focused Sentinel MCP tool for a high-value question.</div></div>
            <div class="step"><div class="num">2</div><div>A local agent experience calls the tool with a normal prompt.</div></div>
            <div class="step"><div class="num">3</div><div>The response comes from real data in the Microsoft security ecosystem.</div></div>
          </div>
        </div>

        <div class="card panel">
          <h2>Raw MCP response</h2>
          <pre id="raw">Run a prompt to see the formatted MCP tool output.</pre>
        </div>
      </aside>
    </section>
  </main>

  <script>
    const messages = document.getElementById("messages");
    const promptInput = document.getElementById("prompt");
    const sendButton = document.getElementById("sendButton");
    const form = document.getElementById("queryForm");

    function addMessage(role, text) {
      const div = document.createElement("div");
      div.className = `msg ${role}`;
      div.textContent = text;
      messages.appendChild(div);
      messages.scrollTop = messages.scrollHeight;
    }

    function asArray(value) {
      if (Array.isArray(value)) return value;
      if (typeof value !== "string") return [];
      const cleaned = value.trim();
      if (!cleaned.startsWith("[") || !cleaned.endsWith("]")) return cleaned ? [cleaned] : [];
      try {
        return JSON.parse(cleaned.replaceAll("'", '"'));
      } catch {
        return cleaned.slice(1, -1).split(",").map(v => v.trim().replace(/^['"]|['"]$/g, "")).filter(Boolean);
      }
    }

    function updateCards(row) {
      if (!row) return;
      const preferred = [
        "Events", "FlowCount", "Queries", "Sessions", "Flows",
        "TotalBytes", "Bytes", "UniqueSources", "UniqueDestinations",
        "FailedQueries", "SlowQueries", "WeakProtocol", "WeakKey"
      ];
      const keys = preferred.filter(key => row[key] !== undefined).slice(0, 4);
      Object.keys(row).forEach(key => {
        if (keys.length < 4 && !keys.includes(key) && !Array.isArray(row[key])) keys.push(key);
      });
      for (let index = 0; index < 4; index++) {
        const key = keys[index] || `Metric ${index + 1}`;
        document.getElementById(`metricLabel${index + 1}`).textContent = key;
        document.getElementById(`metricValue${index + 1}`).textContent = row[key] ?? "--";
      }

      const tags = document.getElementById("tags");
      tags.replaceChildren();
      const tagValues = [
        ...asArray(row.Protocols),
        ...asArray(row.Apps),
        ...asArray(row.AppFamilies),
        ...asArray(row.Sources),
        ...asArray(row.Destinations),
        ...asArray(row.QueryNames),
        ...asArray(row.ReplyCodes),
        ...asArray(row.CommonNames),
        ...asArray(row.Issuers),
        ...asArray(row.TopSources),
        ...asArray(row.TopDestinations),
      ].slice(0, 10);
      tagValues.forEach(value => {
        const tag = document.createElement("span");
        tag.className = "tag";
        tag.textContent = value;
        tags.appendChild(tag);
      });
    }

    async function loadStatus() {
      const res = await fetch("/api/status");
      const data = await res.json();
      document.getElementById("mode").textContent = `${data.mode.toUpperCase()} mode`;
      document.getElementById("toolName").textContent = `Tool: ${data.tool}`;
    }

    async function ask(prompt) {
      addMessage("user", prompt);
      sendButton.disabled = true;
      sendButton.textContent = "Calling...";
      try {
        const res = await fetch("/api/query", {
          method: "POST",
          headers: {"Content-Type": "application/json"},
          body: JSON.stringify({prompt})
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || "Request failed");
        addMessage("assistant", data.summary);
        document.getElementById("toolName").textContent = `Tool: ${data.tool}`;
        document.getElementById("raw").textContent = data.rawText || "";
        updateCards(data.rows && data.rows[0]);
      } catch (error) {
        addMessage("assistant", `I could not call the MCP tool: ${error.message}`);
      } finally {
        sendButton.disabled = false;
        sendButton.textContent = "Ask";
      }
    }

    form.addEventListener("submit", event => {
      event.preventDefault();
      const prompt = promptInput.value.trim();
      if (prompt) ask(prompt);
    });

    document.querySelectorAll(".example").forEach(button => {
      button.addEventListener("click", () => {
        promptInput.value = button.textContent;
        ask(button.textContent);
      });
    });

    loadStatus().then(() => ask(promptInput.value));
  </script>
</body>
</html>
"""


def parse_json_env(name: str, default: dict[str, Any]) -> dict[str, Any]:
    """Read an environment variable that must contain a JSON object."""

    raw = os.getenv(name)
    if not raw:
        return default
    try:
        value = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{name} must be valid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be a JSON object.")
    return value


def render_arguments(message: str, template: str, defaults: dict[str, Any]) -> dict[str, Any]:
    """Render the MCP argument template and merge demo-wide defaults into it."""

    rendered = template.replace("{message}", message)
    try:
        args = json.loads(rendered)
    except json.JSONDecodeError as exc:
        raise ValueError(f"MCP_TOOL_ARGUMENT_TEMPLATE rendered invalid JSON: {exc}") from exc
    if not isinstance(args, dict):
        raise ValueError("MCP_TOOL_ARGUMENT_TEMPLATE must render to a JSON object.")
    return {**args, **defaults}


def select_tool(prompt: str) -> str:
    """Choose the best Gigamon MCP tool for a natural-language demo prompt."""

    configured = os.getenv("SENTINEL_MCP_TOOL", "").strip()
    prompt_lower = prompt.lower()
    for keywords, tool_name in TOOL_ROUTES:
        if any(keyword in prompt_lower for keyword in keywords):
            return tool_name
    return configured or GIGAMON_TOOLS["visibility"]


def create_mcp_client() -> SentinelMCPClient | MockSentinelMCPClient:
    """Create either the real Sentinel MCP client or the offline mock client."""

    mode = os.getenv("MCP_DEMO_MODE", "mock").strip().lower()
    if mode == "real":
        return SentinelMCPClient(
            collection=os.getenv("SENTINEL_MCP_COLLECTION"),
            server_url=os.getenv("SENTINEL_MCP_SERVER_URL"),
        )
    if mode == "mock":
        return MockSentinelMCPClient()
    raise ValueError("MCP_DEMO_MODE must be 'mock' or 'real'.")


def dataset_rows(result: MCPToolResult) -> list[dict[str, Any]]:
    """Extract Kusto PrimaryResult rows from the raw MCP text content."""

    rows: list[dict[str, Any]] = []
    for item in result.content:
        if item.get("type") != "text":
            continue
        text = str(item.get("text", ""))
        try:
            frames = json.loads(text)
        except json.JSONDecodeError:
            continue
        if not isinstance(frames, list):
            continue
        primary = next(
            (
                frame
                for frame in frames
                if isinstance(frame, dict)
                and frame.get("FrameType") == "DataTable"
                and frame.get("TableKind") == "PrimaryResult"
            ),
            None,
        )
        if not primary:
            continue
        # Convert Kusto's `[columns] + [row arrays]` shape into dictionaries so
        # the browser cards can address fields by name.
        columns = [column.get("ColumnName", "") for column in primary.get("Columns", [])]
        for row in primary.get("Rows", []):
            rows.append({columns[index]: value for index, value in enumerate(row) if index < len(columns)})
    return rows


def summarize(prompt: str, tool_name: str, rows: list[dict[str, Any]], raw_text: str) -> str:
    """Create a presenter-friendly one-paragraph summary from the first result row."""

    if not rows:
        return raw_text or f"{tool_name} completed for: {prompt}"

    row = rows[0]
    if tool_name == GIGAMON_TOOLS["lateral"]:
        return (
            f"Lateral movement triage found {row.get('FlowCount')} candidate flows on destination port "
            f"{row.get('dst_port')}, totaling {row.get('TotalBytes')} bytes. Sources: {row.get('Sources')}. "
            f"Destinations: {row.get('Destinations')}."
        )
    if tool_name == GIGAMON_TOOLS["dns"]:
        return (
            f"DNS anomaly hunt found {row.get('Queries')} {row.get('dns_query_type')} queries, "
            f"with {row.get('FailedQueries')} failed and {row.get('SlowQueries')} slow responses. "
            f"Queries: {row.get('QueryNames')}."
        )
    if tool_name == GIGAMON_TOOLS["tls"]:
        return (
            f"TLS risk summary found {row.get('Sessions')} sessions for {row.get('ProtocolVersion')}. "
            f"Weak protocol sessions: {row.get('WeakProtocol')}; weak key observations: {row.get('WeakKey')}; "
            f"expiring soon: {row.get('ExpiringSoon')}."
        )
    if tool_name == GIGAMON_TOOLS["talkers"]:
        return (
            f"Top talkers shows {row.get('app_name')} / {row.get('app_family')} over {row.get('protocol')} "
            f"with {row.get('Flows')} flows and {row.get('Bytes')} bytes. Top sources: {row.get('TopSources')}."
        )

    return (
        f"Visibility posture found {row.get('Events')} Gigamon events across "
        f"{row.get('UniqueSources')} sources and {row.get('UniqueDestinations')} destinations, "
        f"totaling {row.get('TotalBytes')} bytes. Apps: {row.get('Apps')}."
    )


async def index(_: web.Request) -> web.Response:
    """Serve the single-page browser UI."""

    return web.Response(text=HTML, content_type="text/html")


async def status(_: web.Request) -> web.Response:
    """Return current runtime configuration for the status pill in the UI."""

    return web.json_response(
        {
            "mode": os.getenv("MCP_DEMO_MODE", "mock").strip().lower(),
            "collection": os.getenv("SENTINEL_MCP_COLLECTION", ""),
            "tool": os.getenv("SENTINEL_MCP_TOOL", GIGAMON_TOOLS["visibility"]),
            "tools": list(GIGAMON_TOOLS.values()),
            "workspaceId": parse_json_env("MCP_DEFAULT_ARGUMENTS", {}).get("workspaceId", ""),
        }
    )


async def query(request: web.Request) -> web.Response:
    """Handle a prompt, route it to an MCP tool, and return rows plus summary text."""

    payload = await request.json()
    prompt = str(payload.get("prompt", "")).strip()
    if not prompt:
        return web.json_response({"error": "Prompt is required."}, status=400)

    tool_name = select_tool(prompt)
    if not tool_name:
        return web.json_response({"error": "SENTINEL_MCP_TOOL is not configured."}, status=500)

    template = os.getenv("MCP_TOOL_ARGUMENT_TEMPLATE", '{"query":"{message}"}')
    defaults = parse_json_env("MCP_DEFAULT_ARGUMENTS", {})
    arguments = render_arguments(prompt, template, defaults)

    client = create_mcp_client()
    await client.connect()
    try:
        # The custom tool performs the KQL query inside Sentinel/Log Analytics.
        result = await client.call_tool(tool_name, arguments)
    finally:
        await client.close()

    rows = dataset_rows(result)
    raw_text = result.text or json.dumps(result.content, indent=2)
    return web.json_response(
        {
            "prompt": prompt,
            "tool": tool_name,
            "arguments": arguments,
            "rows": rows,
            "rawText": raw_text,
            "summary": summarize(prompt, tool_name, rows, raw_text),
            "isError": result.is_error,
        },
        status=500 if result.is_error else 200,
    )


def build_app() -> web.Application:
    """Construct the aiohttp application and register browser/API routes."""

    load_dotenv()
    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/api/status", status)
    app.router.add_post("/api/query", query)
    return app


def main() -> None:
    """Parse host/port flags and start the local web server."""

    parser = argparse.ArgumentParser(description="Run the Gigamon Visibility Copilot web demo.")
    parser.add_argument("--host", default=os.getenv("WEB_DEMO_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("WEB_DEMO_PORT", "8765")))
    args = parser.parse_args()
    web.run_app(build_app(), host=args.host, port=args.port)


if __name__ == "__main__":
    main()
