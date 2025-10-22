#!/bin/bash
# Created 2025-09-28 - Wrapper script for Supabase MCP server to avoid argument parsing issues

export SUPABASE_ACCESS_TOKEN="sbp_6c2e02e67fb1ff144f0c06eb8e39ec55e04d90aa"

exec npx -y @supabase/mcp-server-supabase --read-only --project-ref=wdpeoyugsxqnpwwtkqsl "$@"