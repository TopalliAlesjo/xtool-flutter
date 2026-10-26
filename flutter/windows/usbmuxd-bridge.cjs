'use strict';
// Runs on Windows (node.exe), started by usbmuxd-relay.py inside WSL.
// Pipes stdin/stdout to Apple Mobile Device Service on 127.0.0.1:27015.
// Bytes only: no logging, no file or account access.
const net = require('node:net');
const port = Number(process.env.USBMUXD_WINDOWS_PORT || 27015);
const socket = net.createConnection({ host: '127.0.0.1', port });
socket.setNoDelay(true);
socket.setTimeout(180000, () => socket.destroy());
socket.on('connect', () => {
  process.stdin.pipe(socket);
  socket.pipe(process.stdout);
});
socket.on('error', () => {
  process.stderr.write('Cannot reach Apple Mobile Device Service on 127.0.0.1:' + port + '\n');
  process.exitCode = 1;
});
socket.on('close', () => {
  process.stdin.unpipe(socket);
  process.stdin.destroy();
});
process.stdout.on('error', () => socket.destroy());
process.stdin.on('error', () => socket.destroy());
