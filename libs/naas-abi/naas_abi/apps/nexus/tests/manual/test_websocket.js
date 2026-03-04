/**
 * Test script for WebSocket real-time features
 * 
 * Usage:
 *   node test_websocket.js
 * 
 * Tests:
 * - Connection
 * - Join workspace
 * - Presence tracking
 * - Typing indicators
 * - Message broadcasting
 */

const io = require('socket.io-client');

const API_URL = process.env.API_URL || 'http://localhost:8000';
const USER_ID = 'user-test-' + Math.random().toString(36).substr(2, 9);
const WORKSPACE_ID = 'workspace-nexus';

console.log('🧪 WebSocket Test Script');
console.log('========================\n');
console.log(`API URL: ${API_URL}`);
console.log(`User ID: ${USER_ID}`);
console.log(`Workspace ID: ${WORKSPACE_ID}\n`);

const socket = io(API_URL, {
  path: '/ws/socket.io',
  auth: {
    user_id: USER_ID
  },
  transports: ['websocket', 'polling']
});

let testsPassed = 0;
let testsFailed = 0;

function pass(message) {
  testsPassed++;
  console.log(`✅ ${message}`);
}

function fail(message) {
  testsFailed++;
  console.error(`❌ ${message}`);
}

// Test 1: Connection
socket.on('connect', () => {
  pass('Connected to WebSocket server');
  
  // Test 2: Join workspace
  console.log(`\n📍 Joining workspace: ${WORKSPACE_ID}`);
  socket.emit('join_workspace', { workspace_id: WORKSPACE_ID }, (response) => {
    if (response.workspace_id === WORKSPACE_ID) {
      pass(`Joined workspace (${response.users ? response.users.length : 0} users online)`);
    } else {
      fail('Failed to join workspace');
    }
    
    // Test 3: Typing indicators
    console.log('\n⌨️  Testing typing indicators...');
    socket.emit('typing_start', {
      workspace_id: WORKSPACE_ID,
      conversation_id: 'test-conversation'
    });
    pass('Sent typing_start event');
    
    setTimeout(() => {
      socket.emit('typing_stop', {
        workspace_id: WORKSPACE_ID,
        conversation_id: 'test-conversation'
      });
      pass('Sent typing_stop event');
      
      // Test 4: Message broadcast
      console.log('\n💬 Testing message broadcast...');
      socket.emit('message_created', {
        workspace_id: WORKSPACE_ID,
        conversation_id: 'test-conversation',
        message: {
          role: 'user',
          content: 'Test message from WebSocket script',
          timestamp: new Date().toISOString()
        }
      });
      pass('Sent message broadcast');
      
      // Summary
      setTimeout(() => {
        console.log('\n' + '='.repeat(50));
        console.log(`Tests passed: ${testsPassed}`);
        console.log(`Tests failed: ${testsFailed}`);
        console.log('='.repeat(50));
        
        // Leave workspace and disconnect
        socket.emit('leave_workspace', { workspace_id: WORKSPACE_ID });
        socket.disconnect();
        process.exit(testsFailed > 0 ? 1 : 0);
      }, 1000);
    }, 2000);
  });
});

// Test event listeners
socket.on('user_joined', (data) => {
  pass(`Received user_joined event: ${data.user_id}`);
});

socket.on('user_left', (data) => {
  pass(`Received user_left event: ${data.user_id}`);
});

socket.on('user_typing', (data) => {
  pass(`Received typing event: ${data.user_id} typing=${data.typing}`);
});

socket.on('new_message', (data) => {
  pass('Received new_message event');
});

socket.on('connect_error', (error) => {
  fail(`Connection error: ${error.message}`);
  process.exit(1);
});

socket.on('disconnect', (reason) => {
  console.log(`\n🔌 Disconnected: ${reason}`);
});

// Timeout after 10 seconds
setTimeout(() => {
  fail('Test timeout (10s)');
  socket.disconnect();
  process.exit(1);
}, 10000);
