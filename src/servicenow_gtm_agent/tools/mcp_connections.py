"""MCP (Model Context Protocol) connections for external data sources.

These connect the agent to live CRM and conversation intelligence data
without embedding credentials in code. Auth is handled via Unity Catalog
credential store.

Databricks tech: MCP Server Connections + Unity Catalog Credentials
"""

from databricks.agents.mcp import MCPServerConnection


def get_salesforce_mcp() -> MCPServerConnection:
    """Connect to Salesforce CRM via managed MCP.

    Provides live read/write access to opportunities, contacts, and activities.
    Auth: OAuth via Unity Catalog credential store — no secrets in code.
    """
    return MCPServerConnection(
        name="salesforce-crm",
        server_url="https://salesforce.mcp.databricks.com/sse",
        auth_type="oauth",
        allowed_tools=[
            "salesforce__get_opportunity",
            "salesforce__get_contacts",
            "salesforce__update_next_step",
            "salesforce__add_activity",
        ],
    )


def get_gong_mcp() -> MCPServerConnection:
    """Connect to Gong conversation intelligence via managed MCP.

    Provides access to call transcripts, deal signals, and account call history.
    Auth: API key via Unity Catalog credential store.
    """
    return MCPServerConnection(
        name="gong-calls",
        server_url="https://gong.mcp.databricks.com/sse",
        auth_type="api_key",
        allowed_tools=[
            "gong__get_call_transcript",
            "gong__get_account_calls",
            "gong__get_deal_signals",
        ],
    )
