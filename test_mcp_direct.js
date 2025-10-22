#!/usr/bin/env node
// Created 2025-09-28 - Direct test of Supabase MCP server connection

const { spawn } = require('child_process');

console.log('🔄 Testing Supabase MCP Server Direct Connection...');
console.log('Using wrapper script: ./supabase-mcp-wrapper.sh');

// Test the MCP server directly
const mcpProcess = spawn('./supabase-mcp-wrapper.sh', {
  stdio: ['pipe', 'pipe', 'inherit']
});

// Send a simple MCP initialization request
const initRequest = JSON.stringify({
  jsonrpc: "2.0",
  id: 1,
  method: "initialize",
  params: {
    protocolVersion: "2024-11-05",
    capabilities: {},
    clientInfo: {
      name: "test-client",
      version: "1.0.0"
    }
  }
}) + '\n';

mcpProcess.stdin.write(initRequest);

let response = '';
mcpProcess.stdout.on('data', (data) => {
  response += data.toString();
  console.log('📥 Response:', data.toString());
});

mcpProcess.on('close', (code) => {
  console.log(`\n📊 MCP server exited with code ${code}`);
});

// Close after 5 seconds
setTimeout(() => {
  console.log('\n🛑 Closing test...');
  mcpProcess.kill();
}, 5000);