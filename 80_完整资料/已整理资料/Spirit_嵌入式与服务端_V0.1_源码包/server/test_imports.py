import sys
sys.path.insert(0, "D:\\code\\usaki\\usaki_server")
from usaki_server.main import app
from usaki_server.api.voice_input import VoiceConnectionHandler
print('imports OK')
print('routes:', [r.path for r in app.routes if hasattr(r, 'path')])