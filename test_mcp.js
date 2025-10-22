#!/usr/bin/env node
// Created 2025-09-28 - Script to test Supabase MCP server installation and connection

const { spawn } = require('child_process');

console.log('🔄 Testing Supabase MCP Server...');
console.log('Project Ref: wdpeoyugsxqnpwwtkqsl');
console.log('Mode: Read-only');

// Set environment variable
process.env.SUPABASE_ACCESS_TOKEN = 'sbp_6c2e02e67fb1ff144f0c06eb8e39ec55e04d90aa';

// Run the MCP server with test parameters
const mcpProcess = spawn('npx', [
  '-y',
  '@supabase/mcp-server-supabase',
  '--read-only',
  '--project-ref=wdpeoyugsxqnpwwtkqsl'
], {
  stdio: 'inherit',
  env: process.env
});

mcpProcess.on('close', (code) => {
  console.log(`\n📊 MCP server exited with code ${code}`);
  if (code === 0) {
    console.log('✅ MCP server test completed successfully');
  } else {
    console.log('❌ MCP server test failed');
  }
});

mcpProcess.on('error', (error) => {
  console.error('❌ Error starting MCP server:', error.message);
});

// Graceful shutdown
process.on('SIGINT', () => {
  console.log('\n🛑 Stopping MCP server test...');
  mcpProcess.kill();
  process.exit(0);
});