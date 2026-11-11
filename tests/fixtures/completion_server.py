"""Deterministic stdio LSP peer; exercise the real client, not its callbacks."""
import json
from pathlib import Path
import sys


scenario = json.loads(Path(sys.argv[1]).read_text())
log = Path(sys.argv[2])
while True:
    headers = {}
    while True:
        line = sys.stdin.buffer.readline()
        if not line:
            sys.exit(0)
        if line == b'\r\n':
            break
        name, value = line.decode().split(':', 1)
        headers[name.lower()] = value.strip()
    message = json.loads(sys.stdin.buffer.read(int(headers['content-length'])))
    with log.open('a') as stream:
        stream.write(json.dumps(message) + '\n')
    if 'id' not in message:
        continue
    method = message['method']
    if method == 'initialize':
        result = {'capabilities': {
            'textDocumentSync': 1,
            'completionProvider': {'triggerCharacters': ['"', '#'], 'resolveProvider': True},
        }}
    elif method == 'textDocument/completion':
        result = {'items': scenario['items'], 'isIncomplete': False}
    elif method == 'completionItem/resolve':
        result = dict(message['params'], **scenario.get('resolved', {}))
    else:
        result = None
    payload = json.dumps({'jsonrpc': '2.0', 'id': message['id'], 'result': result}).encode()
    sys.stdout.buffer.write(f'Content-Length: {len(payload)}\r\n\r\n'.encode() + payload)
    sys.stdout.buffer.flush()
