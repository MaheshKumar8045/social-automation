from core.cinematic_tts import _ps_command


def test_sapi_command_contains_base64_payload_and_wave_target(tmp_path):
    output = tmp_path / "shot.wav"
    command = _ps_command("Tomorrow is my funeral.", output, voice="Test Voice", rate=-1)
    joined = " ".join(command)
    assert "SpeechSynthesizer" in joined
    assert "SetOutputToWaveFile" in joined
    assert "shot.wav" in joined
    assert "Test Voice" not in joined
