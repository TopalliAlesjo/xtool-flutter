'use strict';
const assert = require('node:assert/strict');
const { test } = require('node:test');
const { PassThrough } = require('node:stream');
const { bridge } = require('../windows/usbmuxd-bridge.cjs');

function fixture() {
  const input = new PassThrough();
  const output = new PassThrough();
  const error = new PassThrough();
  const socket = new PassThrough();
  socket.setNoDelay = () => socket;
  socket.setTimeout = (duration) => { socket.timeoutDuration = duration; return socket; };
  bridge({ input, output, error, connect: () => socket });
  return { input, output, error, socket };
}

test('healthy USB event subscriptions have no inactivity timeout', () => {
  const { socket } = fixture();
  assert.equal(socket.timeoutDuration, 15000);
  socket.emit('connect');
  assert.equal(socket.timeoutDuration, 0);
  socket.destroy();
});

test('binary bytes pass unchanged in the bridge', () => {
  const { input, output, socket } = fixture();
  const received = [];
  output.on('data', (chunk) => received.push(chunk));
  socket.emit('connect');
  const payload = Buffer.from([0, 255, 128, 13, 10, 0, 42]);
  input.write(payload);
  assert.deepEqual(Buffer.concat(received), payload);
  socket.destroy();
});

test('invalid ports fail before opening a socket', () => {
  for (const port of [0, -1, 65536, NaN, 1.5]) {
    assert.throws(() => bridge({ port, connect: () => assert.fail('must not connect') }), /integer/);
  }
});

test('connection errors are reported without dumping payloads', () => {
  const { error, socket } = fixture();
  let message = '';
  error.on('data', (chunk) => { message += chunk; });
  const previous = process.exitCode;
  try {
    socket.emit('error', new Error('synthetic socket failure'));
    assert.equal(process.exitCode, 1);
    assert.match(message, /Cannot reach Apple Mobile Device Service/);
    assert.doesNotMatch(message, /synthetic socket failure/);
  } finally {
    process.exitCode = previous;
    socket.destroy();
  }
});

test('closing the socket releases the input stream', async () => {
  const { input, socket } = fixture();
  await new Promise((resolve) => {
    socket.on('close', resolve);
    socket.destroy();
  });
  assert.equal(input.destroyed, true);
});
