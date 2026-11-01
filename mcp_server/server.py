"""Model Context Protocol (MCP) server exposing NetCoop AI diagnostic and remediation tools."""

from netcoop.mcp.server import NetCoopMCPServer

__all__ = ["NetCoopMCPServer"]

if __name__ == "__main__":
    NetCoopMCPServer.run_stdio_server()
