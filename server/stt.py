import os
import tempfile
import wave

import sounddevice as sd
from openai import OpenAI


SAMPLE_RATE = 16000
CHANNELS = 1
RECORD_SECONDS = 5

MODEL = "gpt-4o-mini-transcribe"
# 정확도 더 필요하면:
# MODEL = "gpt-4o-transcribe"


client = OpenAI()


def record_audio(seconds: int = RECORD_SECONDS) -> str:
    print(f"{seconds}초 동안 말하세요...")

    audio = sd.rec(
        int(seconds * SAMPLE_RATE),
        samplerate=SAMPLE_RATE,
        channels=CHANNELS,
        dtype="int16",
    )
    sd.wait()

    temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp_file.close()

    with wave.open(temp_file.name, "wb") as wf:
        wf.setnchannels(CHANNELS)
        wf.setsampwidth(2)  # int16 = 2 bytes
        wf.setframerate(SAMPLE_RATE)
        wf.writeframes(audio.tobytes())

    return temp_file.name


def transcribe_audio(file_path: str) -> str:
    with open(file_path, "rb") as audio_file:
        result = client.audio.transcriptions.create(
            model=MODEL,
            file=audio_file,
            language="ko",
            response_format="json",
        )

    return result.text


def main():
    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY 환경변수가 설정되지 않았습니다.")
        return

    while True:
        input("\nEnter를 누르면 녹음 시작, Ctrl+C로 종료: ")

        wav_path = record_audio()

        try:
            text = transcribe_audio(wav_path)
            print("\n[인식 결과]")
            print(text)

        finally:
            try:
                os.remove(wav_path)
            except OSError:
                pass


if __name__ == "__main__":
    main()