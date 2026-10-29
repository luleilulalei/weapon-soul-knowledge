import time
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from usaki_server.api.spirit import router, connections
from usaki_server.devices.spirit import SpiritEffect, SpiritTelemetry


@pytest.fixture
def client():
    app = FastAPI()
    app.include_router(router, prefix='/api/v1/spirit')
    connections.clear()
    with TestClient(app) as client:
        yield client
    connections.clear()


def telemetry(seq=1, **kw):
    return {'id': f't{seq}', 'type': 'spirit.telemetry', 'device_id': 's1', 'seq': seq,
            'data': {'uptime_ms': 1, 'privacy_muted': False, **kw}}


def wait_telemetry():
    deadline = time.monotonic()+2
    while time.monotonic()<deadline:
        if connections.get('s1') and connections['s1'].telemetry:
            return
        time.sleep(.005)
    raise AssertionError('telemetry not received')


def test_round_trip(client):
    with client.websocket_connect('/api/v1/spirit/device?device_id=s1') as ws:
        ws.send_json(telemetry(haptic_ready=True, nfc_uid='01020304'))
        wait_telemetry()
        assert 'nfc_uid' not in client.get('/api/v1/spirit/s1/state').json()['telemetry']
        command = {'command_id':'c1','effect':'haptic','library_effect':1,'duration_ms':100}
        assert client.post('/api/v1/spirit/s1/effects',json=command).status_code == 202
        wire = ws.receive_json()
        assert wire['type'] == 'spirit.effect'
        assert wire['data']['ttl_ms'] == 1000
        ws.send_json({'id':'a1','type':'spirit.ack','device_id':'s1','seq':2,
                      'data':{'command_id':'c1','status':'applied'}})
        assert client.post('/api/v1/spirit/s1/effects',json=command).status_code == 409
    assert client.get('/api/v1/spirit/s1/state').status_code == 404


@pytest.mark.parametrize('state,command,code', [
    ({}, {'effect':'haptic'},409),
    ({'haptic_ready':True,'privacy_muted':True},{'effect':'haptic'},202),
    ({'haptic_ready':True},{'effect':'blade'},422),
    ({'privacy_muted':True},{'effect':'stop'},202),
])
def test_safety_gate(client,state,command,code):
    with client.websocket_connect('/api/v1/spirit/device?device_id=s1') as ws:
        ws.send_json(telemetry(**state)); wait_telemetry()
        assert client.post('/api/v1/spirit/s1/effects',json={'command_id':'c',**command}).status_code == code


@pytest.mark.parametrize('field,value', [('duration_ms',1001),('duration_ms',True),('ttl_ms',99),('library_effect',124),('effect','servo'),('arbitrary_gpio',1)])
def test_reject_unsafe_command(field,value):
    with pytest.raises(ValidationError):
        SpiritEffect.model_validate({'command_id':'c','effect':'haptic',field:value})


@pytest.mark.parametrize('data', [{'accel_raw':[32768,0,0]},{'battery_mv':99999},{'blade_ready':True},{'nfc_uid':'not-authenticated'},{'imu_valid':'true'}])
def test_reject_bad_telemetry(data):
    with pytest.raises(ValidationError):
        SpiritTelemetry.model_validate({'uptime_ms':1,'privacy_muted':False,**data})


def test_spoof_rejected(client):
    from starlette.websockets import WebSocketDisconnect
    with client.websocket_connect('/api/v1/spirit/device?device_id=s1') as ws:
        msg=telemetry(); msg['device_id']='other'; ws.send_json(msg)
        with pytest.raises(WebSocketDisconnect): ws.receive_json()


def test_stale_state_and_single_pending(client):
    with client.websocket_connect('/api/v1/spirit/device?device_id=s1') as ws:
        ws.send_json(telemetry(haptic_ready=True)); wait_telemetry()
        connections['s1'].seen_at-=4
        assert client.post('/api/v1/spirit/s1/effects',json={'command_id':'stale','effect':'haptic'}).status_code==409
        connections['s1'].seen_at=time.monotonic()
        assert client.post('/api/v1/spirit/s1/effects',json={'command_id':'ok','effect':'haptic'}).status_code==202
        assert client.post('/api/v1/spirit/s1/effects',json={'command_id':'busy','effect':'haptic'}).status_code==409


def test_spirit_voice_never_emits_servo(monkeypatch):
    import asyncio
    from tests.test_voice_interaction_body_action import FixedSpeechToTextProvider, FixedLanguageModelProvider, FailingTextToSpeechProvider
    from usaki_server.audio.providers import VoiceProviders
    from usaki_server.audio.voice_session import VoiceSession
    from usaki_server.audio.voice_interaction import VoiceInteractionFlow
    from usaki_server.api.model import VoiceInputStartData, VoiceInputEndData
    from usaki_server.config import Settings
    monkeypatch.setattr('usaki_server.audio.voice_interaction.get_settings',lambda: Settings(device_profile='spirit'))
    async def run():
        flow=VoiceInteractionFlow(VoiceSession(Settings(audio_vad_provider='rms'),VoiceProviders(stt=FixedSpeechToTextProvider(),llm=FixedLanguageModelProvider(),tts=FailingTextToSpeechProvider())))
        flow.start_input(VoiceInputStartData(),device_id='s1')
        flow._session._buffer._append_chunk(b'audio',b'\x00\x00'*960)
        frames=[f async for f in flow.finish_input(VoiceInputEndData(reason='vad_end'),device_id='s1',seq=1)]
        assert frames
        assert all(f.message_type not in {'body.action','motion.servo.batch'} for f in frames)
    asyncio.run(run())


def test_privacy_cancels_processing_and_queue():
    import asyncio
    from usaki_server.api.voice_input import VoiceConnectionHandler
    from usaki_server.audio.providers import VoiceProviders, StubSpeechToTextProvider, StubLanguageModelProvider, SilentTextToSpeechProvider
    from usaki_server.config import Settings
    class FakeSocket:
        query_params={}
    async def run():
        handler=VoiceConnectionHandler(FakeSocket(),Settings(audio_vad_provider='rms'),VoiceProviders(stt=StubSpeechToTextProvider(),llm=StubLanguageModelProvider(),tts=SilentTextToSpeechProvider()))
        task=asyncio.create_task(asyncio.sleep(100))
        handler._process_tasks.add(task)
        handler._send_queue.put_nowait(object())
        handler._cancel_output_tasks()
        await asyncio.sleep(0)
        assert task.cancelled()
        assert handler._send_queue.empty()
    asyncio.run(run())


def test_late_ack_after_stop_does_not_drop_session(client):
    with client.websocket_connect('/api/v1/spirit/device?device_id=s1') as ws:
        ws.send_json(telemetry(haptic_ready=True)); wait_telemetry()
        for cid,effect in [('run','haptic'),('halt','stop')]:
            assert client.post('/api/v1/spirit/s1/effects',json={'command_id':cid,'effect':effect}).status_code==202
            ws.receive_json()
        ws.send_json({'id':'a','type':'spirit.ack','device_id':'s1','seq':2,'data':{'command_id':'run','status':'applied'}})
        ws.send_json({'id':'b','type':'spirit.ack','device_id':'s1','seq':3,'data':{'command_id':'halt','status':'applied'}})
        deadline=time.monotonic()+2
        while time.monotonic()<deadline:
            if connections['s1'].pending is None: break
            time.sleep(.005)
        assert connections['s1'].pending is None
        assert connections['s1'].last_ack.command_id=='halt'
