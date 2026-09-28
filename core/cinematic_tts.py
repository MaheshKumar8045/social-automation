from __future__ import annotations

import argparse
import base64
import json
import shutil
import subprocess
from pathlib import Path
from typing import Any


def _ps_command(text: str, output: Path, voice: str = "", rate: int = 0) -> list[str]:
    encoded = base64.b64encode(text.encode("utf-8")).decode("ascii")
    target = str(output.resolve()).replace("'", "''")
    voice_clause = ""
    if voice:
        voice_encoded = base64.b64encode(voice.encode("utf-8")).decode("ascii")
        voice_clause = (
            "$voice=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
            + voice_encoded
            + "')); $s.SelectVoice($voice); "
        )
    script = (
        "Add-Type -AssemblyName System.Speech; "
        "$s=New-Object System.Speech.Synthesis.SpeechSynthesizer; "
        + voice_clause
        + f"$s.Rate={int(rate)}; "
        + "$t=[Text.Encoding]::UTF8.GetString([Convert]::FromBase64String('"
        + encoded
        + "')); "
        + "$s.SetOutputToWaveFile('"
        + target
        + "'); $s.Speak($t); $s.Dispose();"
    )
    return ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script]


def generate_sapi_audio(
    adaptation: dict[str, Any],
    output_dir: str | Path,
    *,
    voice: str = "",
    rate: int = 0,
) -> dict[str, Any]:
    powershell = shutil.which("powershell.exe")
    if not powershell:
        raise RuntimeError("Windows PowerShell was not found")
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    generated = []
    skipped = []
    for episode in adaptation.get("episodes", []):
        for shot in episode.get("shots", []):
            text = str(shot.get("voiceover_text") or "").strip()
            shot_id = int(shot["shot_id"])
            if not text:
                skipped.append(shot_id)
                continue
            target = out / f"shot_{shot_id:06d}.wav"
            command = _ps_command(text, target, voice=voice, rate=rate)
            subprocess.run(command, check=True)
            generated.append({"shot_id": shot_id, "path": str(target), "text": text})
    manifest = {"voice": voice, "rate": rate, "generated": generated, "skipped": skipped}
    (out / "tts_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate local Windows SAPI narration WAV files from a cinematic adaptation.")
    parser.add_argument("adaptation")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--voice", default="")
    parser.add_argument("--rate", type=int, default=0)
    args = parser.parse_args()
    adaptation = json.loads(Path(args.adaptation).read_text(encoding="utf-8"))
    manifest = generate_sapi_audio(adaptation, args.output_dir, voice=args.voice, rate=max(-10, min(10, args.rate)))
    print(json.dumps({"generated": len(manifest["generated"]), "skipped": len(manifest["skipped"])}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
