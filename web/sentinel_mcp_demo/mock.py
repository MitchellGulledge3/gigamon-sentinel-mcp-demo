from __future__ import annotations

import json
from typing import Any

from .client import MCPTool, MCPToolResult


class MockSentinelMCPClient:
    def __init__(self) -> None:
        self.tools = [
            MCPTool(
                name="Recovery_Confidence_Summary",
                description="Summarize backup and restore readiness for an impacted asset.",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}, "hostName": {"type": "string"}},
                },
            ),
            MCPTool(
                name="Sensitive_Data_Blast_Radius",
                description="Summarize sensitive data touched by a user or device during an incident window.",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}, "userId": {"type": "string"}},
                },
            ),
            MCPTool(
                name="Edge_Attack_Summary",
                description="Summarize WAF, DDoS, DNS, or edge traffic signals for an investigation.",
                input_schema={
                    "type": "object",
                    "properties": {"query": {"type": "string"}, "domain": {"type": "string"}},
                },
            ),
        ]

    async def connect(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def list_tools(self) -> list[MCPTool]:
        return self.tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any] | None = None) -> MCPToolResult:
        args = arguments or {}
        subject = args.get("hostName") or args.get("userId") or args.get("domain") or args.get("query") or "demo target"
        text = {
            "Recovery_Confidence_Summary": (
                f"Recovery confidence for {subject}: HIGH\n"
                "- Last successful immutable backup: 2 hours ago\n"
                "- No suspicious backup deletion activity detected\n"
                "- Recommended action: proceed with restore validation and preserve current snapshot"
            ),
            "Sensitive_Data_Blast_Radius": (
                f"Sensitive data blast radius for {subject}: MEDIUM\n"
                "- 17 sensitive files accessed in the incident window\n"
                "- 3 external sharing changes require review\n"
                "- Recommended action: revoke stale permissions and open insider-risk review"
            ),
            "Edge_Attack_Summary": (
                f"Edge attack summary for {subject}: ELEVATED\n"
                "- WAF rule hits increased 4.2x over baseline\n"
                "- Top sources concentrated in 3 ASNs\n"
                "- Recommended action: review bot mitigation policy and block high-risk ASN cluster"
            ),
        }.get(tool_name, f"Mock result for {tool_name}:\\n{json.dumps(args, indent=2)}")

        return MCPToolResult(
            tool_name=tool_name,
            content=[{"type": "text", "text": text}],
            is_error=False,
        )
