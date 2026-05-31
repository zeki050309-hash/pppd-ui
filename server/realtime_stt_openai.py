import os
import queue
import tempfile
import threading
import wave
from dataclasses import dataclass

import numpy as np
import sounddevice as sd
import torch
from dotenv import load_dotenv
from openai import OpenAI
from scipy import signal


# ============================================================
# 환경 변수 / OpenAI 설정
# ============================================================

load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY가 없습니다. .env 파일을 확인하세요.")

client = OpenAI(api_key=OPENAI_API_KEY)


# ============================================================
# 설정
# ============================================================

@dataclass
class Config:
    sample_rate: int = 16000
    channels: int = 1

    # Silero VAD는 16kHz에서 정확히 512 samples 필요
    vad_frame_samples: int = 512

    # Wake Trigger: 사람 말이 시작됐는지 판단
    wake_speech_prob_threshold: float = 0.45
    wake_required_frames: int = 2

    # VAD: 말이 끝났는지 판단
    vad_speech_prob_threshold: float = 0.35
    silence_end_seconds: float = 0.7
    min_record_seconds: float = 0.7
    max_record_seconds: float = 6.0
    pre_roll_seconds: float = 0.5

    # 정확도 우선 모델
    stt_model: str = "gpt-4o-transcribe"
    language: str = "ko"

    # 정확도 우선이면 True, 속도 우선이면 False
    use_denoise: bool = True

    # 정확도 우선이면 True, 속도 우선이면 False
    use_correction: bool = True
    correction_model: str = "gpt-4o-mini"

    # 로그
    print_prob: bool = True

    # 마이크 번호 직접 지정하고 싶으면 1, 5, 9 등으로 변경
    input_device: int | None = None


CFG = Config()

audio_queue: queue.Queue[np.ndarray] = queue.Queue()
stop_event = threading.Event()


# ============================================================
# Silero VAD 로드
# ============================================================

print("Silero VAD 로딩 중...")

vad_model, utils = torch.hub.load(
    repo_or_dir="snakers4/silero-vad",
    model="silero_vad",
    force_reload=False,
    trust_repo=True,
)

vad_model.eval()

print("Silero VAD 로딩 완료")


# ============================================================
# 유틸
# ============================================================

def normalize_audio(audio: np.ndarray, target_peak: float = 0.9) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)
    audio = np.nan_to_num(audio, nan=0.0, posinf=0.0, neginf=0.0)

    peak = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0

    if peak > 1e-6:
        audio = audio / peak * target_peak

    return np.clip(audio, -1.0, 1.0).astype(np.float32)


def save_wav(audio: np.ndarray, sample_rate: int) -> str:
    audio = normalize_audio(audio)
    audio_int16 = (audio * 32767).astype(np.int16)

    temp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    temp.close()

    with wave.open(temp.name, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(audio_int16.tobytes())

    return temp.name


def highpass_filter(audio: np.ndarray, sample_rate: int, cutoff: float = 80.0) -> np.ndarray:
    if len(audio) < sample_rate * 0.1:
        return audio.astype(np.float32)

    sos = signal.butter(
        4,
        cutoff,
        btype="highpass",
        fs=sample_rate,
        output="sos",
    )

    return signal.sosfilt(sos, audio).astype(np.float32)


def speech_probability(frame: np.ndarray) -> float:
    """
    Silero VAD가 현재 512-sample frame이 사람 말인지 확률로 판단.
    16kHz에서는 frame 길이가 반드시 512여야 함.
    """
    frame = np.asarray(frame, dtype=np.float32).reshape(-1)

    if len(frame) != CFG.vad_frame_samples:
        raise ValueError(
            f"Silero VAD frame length must be {CFG.vad_frame_samples}, got {len(frame)}"
        )

    frame = np.nan_to_num(frame, nan=0.0, posinf=0.0, neginf=0.0)
    frame = np.clip(frame, -1.0, 1.0)

    tensor = torch.from_numpy(frame).float()

    with torch.no_grad():
        prob = vad_model(tensor, CFG.sample_rate).item()

    return float(prob)


# ============================================================
# AI Wake Trigger
# ============================================================

class AIWakeTrigger:
    """
    Wake Up Trigger:
    사람이 말하기 시작했는지 Silero VAD가 판단.
    """

    def __init__(self, threshold: float, required_frames: int):
        self.threshold = threshold
        self.required_frames = required_frames
        self.count = 0

    def reset(self):
        self.count = 0

    def check(self, frame: np.ndarray) -> tuple[bool, float]:
        prob = speech_probability(frame)

        if prob >= self.threshold:
            self.count += 1
        else:
            self.count = 0

        return self.count >= self.required_frames, prob


# ============================================================
# AI VAD
# ============================================================

class AIVAD:
    """
    VAD:
    AI가 말이 계속되는지, 끝났는지 판단.
    """

    def __init__(
        self,
        speech_threshold: float,
        silence_end_seconds: float,
        sample_rate: int,
        frame_samples: int,
        min_record_seconds: float,
        max_record_seconds: float,
    ):
        self.speech_threshold = speech_threshold

        frame_seconds = frame_samples / sample_rate

        self.silence_end_frames = max(1, int(silence_end_seconds / frame_seconds))
        self.min_frames = max(1, int(min_record_seconds / frame_seconds))
        self.max_frames = max(1, int(max_record_seconds / frame_seconds))

        self.total_frames = 0
        self.silent_frames = 0

    def reset(self):
        self.total_frames = 0
        self.silent_frames = 0

    def update(self, frame: np.ndarray) -> tuple[bool, float]:
        prob = speech_probability(frame)

        self.total_frames += 1

        if prob < self.speech_threshold:
            self.silent_frames += 1
        else:
            self.silent_frames = 0

        if self.total_frames < self.min_frames:
            return False, prob

        if self.silent_frames >= self.silence_end_frames:
            return True, prob

        if self.total_frames >= self.max_frames:
            return True, prob

        return False, prob


# ============================================================
# Denoise
# ============================================================

def estimate_noise_level(audio: np.ndarray) -> float:
    if len(audio) < 10:
        return 0.0

    abs_audio = np.abs(audio)
    quiet = audio[abs_audio <= np.percentile(abs_audio, 25)]

    if len(quiet) == 0:
        return 0.0

    return float(np.sqrt(np.mean(quiet ** 2) + 1e-12))


def denoise_audio(audio: np.ndarray) -> np.ndarray:
    audio = np.asarray(audio, dtype=np.float32).reshape(-1)

    # 기본적으로 저주파 잡음 제거
    audio = highpass_filter(audio, CFG.sample_rate)

    if not CFG.use_denoise:
        return normalize_audio(audio)

    noise_level = estimate_noise_level(audio)
    print(f"[Denoise 판단] noise_level={noise_level:.5f}")

    try:
        import noisereduce as nr

        if noise_level >= 0.003:
            print("[Denoise] 적용")
            audio = nr.reduce_noise(
                y=audio,
                sr=CFG.sample_rate,
                stationary=False,
                prop_decrease=0.65,
            ).astype(np.float32)
        else:
            print("[Denoise] 노이즈 낮음 → 생략")

    except ImportError:
        print("[Denoise] noisereduce 미설치 → high-pass만 적용")

    except Exception as e:
        print(f"[Denoise] 실패 → 원본 사용: {e}")

    return normalize_audio(audio)


# ============================================================
# STT
# ============================================================

def transcribe(audio: np.ndarray) -> str:
    wav_path = None

    try:
        wav_path = save_wav(audio, CFG.sample_rate)

        with open(wav_path, "rb") as f:
            result = client.audio.transcriptions.create(
                model=CFG.stt_model,
                file=f,
                language=CFG.language,
                prompt=(
                    "한국어 일상 대화를 정확히 받아쓰기. "
                    "짧은 발화, 주변 소음 속 말소리, 도움 요청, 경고 표현을 자연스럽게 전사한다. "
                    "들은 내용만 전사하고, 들리지 않는 말은 추측하지 않는다. "
                    "한국어 문장부호와 띄어쓰기를 자연스럽게 적용한다."
                ),
                response_format="json",
            )

        return result.text.strip()

    finally:
        if wav_path and os.path.exists(wav_path):
            try:
                os.remove(wav_path)
            except OSError:
                pass


# ============================================================
# LLM 오타 보정
# ============================================================

def correct_text(text: str) -> str:
    if not CFG.use_correction:
        return text

    if not text.strip():
        return text

    try:
        response = client.responses.create(
            model=CFG.correction_model,
            input=f"""
다음은 한국어 STT 결과입니다.

너의 역할:
STT 결과의 띄어쓰기, 조사, 명백한 오타만 자연스럽게 보정한다.

규칙:
1. 새로운 내용을 추가하지 마라.
2. 의미를 바꾸지 마라.
3. 들리지 않은 내용을 추측하지 마라.
4. 결과 문장만 출력하라.
5. 위험 상황 관련 단어를 임의로 추가하거나 삭제하지 마라.

STT 결과:
{text}
""".strip(),
        )

        corrected = response.output_text.strip()

        return corrected if corrected else text

    except Exception as e:
        print(f"[LLM 보정 경고] 보정 실패 → 원문 사용: {e}")
        return text


# ============================================================
# STT Worker
# ============================================================

def stt_worker():
    """
    녹음된 발화를 백그라운드에서 STT 처리.
    이 스레드가 느려도 마이크 녹음 루프는 계속 돌아가므로 다음 발화를 놓치지 않음.
    """
    print("[STT Worker] 시작")

    while not stop_event.is_set():
        try:
            audio = audio_queue.get(timeout=0.5)
        except queue.Empty:
            continue

        try:
            print("\n" + "-" * 60)
            print(f"[STT Worker] 처리 시작 | 대기 중인 발화 수: {audio_queue.qsize()}")
            print(f"[STT Worker] 오디오 길이: {len(audio) / CFG.sample_rate:.2f}초")

            cleaned = denoise_audio(audio)

            print("[STT] OpenAI STT 변환 중...")
            raw_text = transcribe(cleaned)

            if not raw_text:
                print("[STT] 인식 결과 없음")
                continue

            print(f"[STT 원문] {raw_text}")

            if CFG.use_correction:
                print("[LLM] 오타/띄어쓰기 보정 중...")
                final_text = correct_text(raw_text)
            else:
                final_text = raw_text

            print(f"[최종 텍스트] {final_text}")
            print("-" * 60)

        except Exception as e:
            print(f"[STT Worker 오류] {e}")

        finally:
            audio_queue.task_done()


# ============================================================
# 마이크 녹음 루프
# ============================================================

def listen_once(stream, wake: AIWakeTrigger, vad: AIVAD) -> np.ndarray | None:
    frame_size = CFG.vad_frame_samples
    frame_seconds = frame_size / CFG.sample_rate
    pre_roll_max_frames = max(1, int(CFG.pre_roll_seconds / frame_seconds))

    pre_roll: list[np.ndarray] = []
    recorded: list[np.ndarray] = []

    wake.reset()
    vad.reset()

    print("\n[대기] AI Wake Trigger 작동 중...")

    # 1. AI Wake Trigger
    while not stop_event.is_set():
        frame, overflowed = stream.read(frame_size)
        frame = frame.reshape(-1).astype(np.float32)

        if overflowed:
            print("\n[경고] 오디오 입력 overflow")

        pre_roll.append(frame.copy())

        if len(pre_roll) > pre_roll_max_frames:
            pre_roll.pop(0)

        triggered, prob = wake.check(frame)

        if CFG.print_prob:
            print(f"\r[Wake 판단] speech_prob={prob:.3f}", end="")

        if triggered:
            print("\n[Wake] AI가 발화 시작으로 판단")
            break

    if stop_event.is_set():
        return None

    # 2. AI VAD
    recorded.extend(pre_roll)

    print("[녹음] AI VAD로 발화 종료 판단 중...")

    while not stop_event.is_set():
        frame, overflowed = stream.read(frame_size)
        frame = frame.reshape(-1).astype(np.float32)

        if overflowed:
            print("\n[경고] 오디오 입력 overflow")

        recorded.append(frame.copy())

        should_stop, prob = vad.update(frame)

        if CFG.print_prob:
            print(f"\r[VAD 판단] speech_prob={prob:.3f}", end="")

        if should_stop:
            print("\n[VAD] AI가 발화 종료로 판단")
            break

    audio = np.concatenate(recorded) if recorded else np.array([], dtype=np.float32)

    duration = len(audio) / CFG.sample_rate
    print(f"[녹음 완료] {duration:.2f}초")

    if duration < CFG.min_record_seconds:
        print("[무시] 너무 짧은 발화")
        return None

    return audio


def recorder_loop():
    frame_size = CFG.vad_frame_samples

    wake = AIWakeTrigger(
        threshold=CFG.wake_speech_prob_threshold,
        required_frames=CFG.wake_required_frames,
    )

    vad = AIVAD(
        speech_threshold=CFG.vad_speech_prob_threshold,
        silence_end_seconds=CFG.silence_end_seconds,
        sample_rate=CFG.sample_rate,
        frame_samples=CFG.vad_frame_samples,
        min_record_seconds=CFG.min_record_seconds,
        max_record_seconds=CFG.max_record_seconds,
    )

    with sd.InputStream(
        samplerate=CFG.sample_rate,
        channels=CFG.channels,
        dtype="float32",
        blocksize=frame_size,
        device=CFG.input_device,
    ) as stream:

        while not stop_event.is_set():
            audio = listen_once(stream, wake, vad)

            if audio is None:
                continue

            audio_queue.put(audio)
            print(f"[Queue] 발화 추가 | 현재 대기 수: {audio_queue.qsize()}")


# ============================================================
# main
# ============================================================

def main():
    print("=" * 60)
    print("PromptEar High-Accuracy STT Pipeline")
    print("=" * 60)
    print("Wake model: Silero VAD")
    print("VAD model: Silero VAD")
    print(f"STT model: {CFG.stt_model}")
    print(f"Correction model: {CFG.correction_model}")
    print(f"Sample rate: {CFG.sample_rate}")
    print(f"VAD frame samples: {CFG.vad_frame_samples}")
    print(f"Denoise: {CFG.use_denoise}")
    print(f"Correction: {CFG.use_correction}")
    print("=" * 60)

    print("\n사용 가능한 오디오 장치:")
    print(sd.query_devices())

    if CFG.input_device is not None:
        sd.default.device = CFG.input_device
        print(f"\n입력 장치 직접 지정: {CFG.input_device}")

    worker = threading.Thread(target=stt_worker, daemon=True)
    worker.start()

    try:
        recorder_loop()

    except KeyboardInterrupt:
        print("\n종료 요청")

    finally:
        stop_event.set()
        print("\n종료합니다.")


if __name__ == "__main__":
    try:
        main()

    except Exception as e:
        stop_event.set()
        print(f"\n[오류] {e}")
        print("마이크 번호를 직접 지정해야 할 수 있습니다.")
        print("Config의 input_device 값을 1, 5, 9 등으로 바꿔보세요.")