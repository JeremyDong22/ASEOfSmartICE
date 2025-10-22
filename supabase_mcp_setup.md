# Supabase MCP (Model Context Protocol) Setup Guide

*Created 2025-09-28 - Complete setup guide for Supabase MCP integration*

## Overview

This project now includes Supabase MCP (Model Context Protocol) integration, allowing AI assistants to directly interact with the Supabase database through a standardized protocol.

## Installation

The Supabase MCP server has been installed at the project level:

```bash
# Package installed
npm install @supabase/mcp-server-supabase
```

## Configuration

### Project Details
- **Project Reference**: `wdpeoyugsxqnpwwtkqsl`
- **Access Token**: `sbp_6c2e02e67fb1ff144f0c06eb8e39ec55e04d90aa`
- **Mode**: Read-only (for security)

### MCP Configuration (claude_mcp_config.json)
```json
{
  "mcpServers": {
    "supabase": {
      "command": "npx",
      "args": [
        "-y",
        "@supabase/mcp-server-supabase",
        "--read-only",
        "--project-ref=wdpeoyugsxqnpwwtkqsl"
      ],
      "env": {
        "SUPABASE_ACCESS_TOKEN": "sbp_6c2e02e67fb1ff144f0c06eb8e39ec55e04d90aa"
      }
    }
  }
}
```

## Usage

### Testing the MCP Server
```bash
# Run the test script
node test_mcp.js

# Or test directly
SUPABASE_ACCESS_TOKEN="sbp_6c2e02e67fb1ff144f0c06eb8e39ec55e04d90aa" npx @supabase/mcp-server-supabase --read-only --project-ref=wdpeoyugsxqnpwwtkqsl
```

### Integration with AI Tools

#### Claude Desktop
Copy the contents of `claude_mcp_config.json` to your Claude Desktop configuration file:
- **macOS**: `~/Library/Application Support/Claude/claude_desktop_config.json`
- **Windows**: `%APPDATA%\Claude\claude_desktop_config.json`

#### Cursor IDE
Add the MCP server configuration to your Cursor settings.

## Security Features

- **Read-only mode**: Prevents accidental database modifications
- **Project-scoped**: Limited to the specific Supabase project
- **Token-based authentication**: Secure access control

## Database Access

With MCP enabled, AI assistants can:
- Query the `ase_snapshot` table
- Fetch database schema information
- Analyze surveillance data patterns
- Generate reports from captured data

## Troubleshooting

### Common Issues
1. **Node.js Version**: Ensure Node.js 20+ is installed
2. **Network Access**: Verify connection to Supabase
3. **Token Validity**: Check access token permissions

### Verification Commands
```bash
# Check Node.js version
node --version

# Test package installation
npm list @supabase/mcp-server-supabase

# Verify MCP server starts
timeout 5s npx @supabase/mcp-server-supabase --read-only --project-ref=wdpeoyugsxqnpwwtkqsl
```

## Next Steps

1. Configure your preferred AI tool with the MCP server
2. Test database queries through the MCP interface
3. Explore advanced MCP features for data analysis

---

**Note**: This configuration uses read-only access for security. For write operations, modify the MCP configuration to remove the `--read-only` flag (not recommended for production).