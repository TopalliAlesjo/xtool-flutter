'use strict';
// Runs on Windows (node.exe), started by usbmuxd-relay.py inside WSL.
// Pipes stdin/stdout to Apple Mobile Device Service on 127.0.0.1:27015.
// Bytes only: no logging, no file or account access.
const net = require('node:net');
function bridge({ port = 27015, input = process.stdin, output = process.stdout,
  error = process.stderr, connect = net.createConnection } = {}) {
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    throw new Error('USBMUXD_WINDOWS_PORT must be an integer from 1 to 65535.');
  }
  const socket = connect({ host: '127.0.0.1', port });
  socket.setNoDelay(true);
  // Timeout only while connecting. Listen/device-event streams can legitimately
  // remain silent for hours; an inactivity timeout drops those healthy streams.
  socket.setTimeout(15000, () => socket.destroy(new Error('Connection timed out')));
  socket.on('connect', () => {
    socket.setTimeout(0);
    input.pipe(socket);
    socket.pipe(output);
  });
  socket.on('error', () => {
    error.write('Cannot reach Apple Mobile Device Service on 127.0.0.1:' + port + '\n');
    process.exitCode = 1;
  });
  socket.on('close', () => {
    input.unpipe(socket);
    input.destroy();
  });
  output.on('error', () => socket.destroy());
  input.on('error', () => socket.destroy());
  return socket;
}

module.exports = { bridge };
if (require.main === module) {
  try {
    bridge({ port: Number(process.env.USBMUXD_WINDOWS_PORT || 27015) });
  } catch (error) {
    process.stderr.write(error.message + '\n');
    process.exitCode = 1;
  }
}
