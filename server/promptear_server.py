# promptear_server.py
# PromptEar 통합 서버
# - YAMNet 온톨로지 계층 구조 (main.py)
# - CLAP Transformers 텍스트/오디오 인코더 (동료 파일, ONNX/AudioGen 불필요)
# - Claude API: 온톨로지 분류 + U/X prior 추정 단일 호출 (두 파일 통합)
# - Model A+ sigmoid: 최종 알림 확률 계산 (동료 파일)
# - Context 기반 상황별 알림 조정 (동료 파일)

import os
import sys

# ───────────────────────────────────────────────────────────────
# Windows 콘솔 인코딩 보정 (중요)
# 기본 콘솔이 cp949 면 print 에 cp949 밖 문자(이모지·일부 기호·LLM 응답 등)가
# 섞이는 순간 UnicodeEncodeError 가 나서, 그 print 가 요청 핸들러 안이면
# 500 에러로 이어질 수 있다. stdout/stderr 를 UTF-8 로 강제해 방지한다.
# ───────────────────────────────────────────────────────────────
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")  # py3.7+
    except Exception:
        pass

# ───────────────────────────────────────────────────────────────
# 경로 설정 (하드코딩 대신 상대경로)
# ───────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ── .env 파일 자동 로드 ────────────────────────────────────────────
# server/.env 또는 프로젝트 루트/.env 에 API 키를 넣어두면 자동으로 읽힌다.
#
# 중요: python-dotenv 에 의존하지 않고 직접 파싱한다. 서버를 띄우는 Python
# 환경에 python-dotenv 가 없으면 예전엔 .env 가 통째로 무시돼서(키 둘 다 미로드)
# LLM/STT 가 다 fallback 으로 빠졌다. 이제 어떤 환경에서도 .env 가 읽힌다.
def _parse_env_file(path: str) -> int:
    """간단한 .env 파서. KEY=VALUE 형식을 읽어 os.environ 에 주입(override)."""
    loaded = 0
    try:
        with open(path, "r", encoding="utf-8-sig") as fh:
            for line in fh:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                if line.lower().startswith("export "):
                    line = line[len("export "):].lstrip()
                key, _, val = line.partition("=")
                key = key.strip()
                # 양끝 따옴표/공백 제거, 인라인 주석은 건드리지 않음(키 값에 # 가능)
                val = val.strip().strip('"').strip("'").strip()
                if key:
                    os.environ[key] = val      # .env 가 환경변수보다 우선
                    loaded += 1
    except OSError:
        return 0
    return loaded


def _load_dotenv_if_present() -> None:
    # 1순위: server/.env, 2순위: 프로젝트 루트/.env
    _f1 = os.path.join(BASE_DIR, ".env")
    _f2 = os.path.join(os.path.dirname(BASE_DIR), ".env")
    for _f in (_f1, _f2):
        if os.path.exists(_f):
            n = _parse_env_file(_f)
            print(f"[env] .env 로드: {_f} (키 {n}개)", flush=True)
            return
    print(f"[env] .env 파일을 찾지 못함 (확인 경로: {_f1})", flush=True)

_load_dotenv_if_present()


def _clean_api_key(raw: str) -> str:
    """
    API 키를 정리/검증한다. 빈 값, 미입력, 예시 placeholder(sk-...)는
    "키 없음"으로 간주해 빈 문자열을 반환한다.
    (실수로 따옴표를 붙인 경우도 제거)
    """
    key = (raw or "").strip().strip('"').strip("'").strip()
    if not key:
        return ""
    # 예시/placeholder 패턴 거르기
    if key in ("sk-...", "sk-ant-...") or key.endswith("...") or "여기에" in key:
        return ""
    return key

# ── YAMNet 모델 탐색 우선순위 ──────────────────────────────────────
# 1) 기존 절대 경로 (이미 다운로드된 경우)
# 2) BASE_DIR 상대 경로
# 3) TF Hub URL 자동 다운로드
_YAMNET_LOCAL_CANDIDATES = [
    "C:/tfhub_cache/google_yamnet_1",
    os.path.join(BASE_DIR, "tfhub_cache", "google_yamnet_1"),
]
_YAMNET_HUB_URL = "https://tfhub.dev/google/yamnet/1"

# TF Hub 캐시: 기존 C:/tfhub_cache가 있으면 재사용
if os.path.exists("C:/tfhub_cache"):
    os.environ["TFHUB_CACHE_DIR"] = "C:/tfhub_cache"
else:
    os.environ["TFHUB_CACHE_DIR"] = os.path.join(BASE_DIR, "tfhub_cache")

os.environ["TMP"]  = os.path.join(BASE_DIR, "tmp")
os.environ["TEMP"] = os.path.join(BASE_DIR, "tmp")

# HF 캐시: 시스템 기본 경로에 모델이 있으면 그대로 사용, 없으면 로컬 경로
_sys_hf = os.path.join(os.path.expanduser("~"), ".cache", "huggingface")
_local_hf = os.path.join(BASE_DIR, "hf_cache")
_clap_in_sys   = os.path.exists(os.path.join(_sys_hf, "hub", "models--laion--clap-htsat-unfused"))
_clap_in_local = os.path.exists(os.path.join(_local_hf, "hub", "models--laion--clap-htsat-unfused"))

if _clap_in_sys:
    os.environ["HF_HOME"] = _sys_hf          # 이미 시스템 캐시에 있음
elif _clap_in_local:
    os.environ["HF_HOME"] = _local_hf        # 로컬 캐시에 있음
else:
    os.environ["HF_HOME"] = _local_hf        # 없으면 로컬에 다운로드

os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"
os.environ["TF_ENABLE_ONEDNN_OPTS"]           = "0"
os.environ["KMP_DUPLICATE_LIB_OK"]            = "TRUE"

os.makedirs(os.environ["TFHUB_CACHE_DIR"], exist_ok=True)
os.makedirs(os.environ["TMP"],             exist_ok=True)
os.makedirs(os.environ["HF_HOME"],         exist_ok=True)

# ───────────────────────────────────────────────────────────────
# Imports
# ───────────────────────────────────────────────────────────────
import json
import math
import tempfile
import threading
import time
import wave
from typing import Any

import anthropic
import numpy as np
import tensorflow as tf
import tensorflow_hub as hub
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from scipy import signal
from transformers import ClapModel, ClapProcessor

# ───────────────────────────────────────────────────────────────
# 설정값 / 임계치
# ───────────────────────────────────────────────────────────────
PROMPTS_FILE = os.path.join(BASE_DIR, "prompts.json")

# YAMNet 판단 임계치
YAMNET_HIGH          = 0.70   # 고신뢰도: 바로 반환
YAMNET_MID           = 0.40   # 중신뢰도: CLAP이 더 확신할 때만 오버라이드
AMBIGUITY_MARGIN     = 0.15   # 서브트리 1위-2위 차이가 이 이하면 모호 판정
URGENT_CONF_THRESH   = 0.30   # 긴급 소리 최소 신뢰도
# 등록 프롬프트와 YAMNet을 "카테고리(서브트리) 단위"로 매칭할 때
# top-k 라벨이 가져야 하는 최소 점수. 너무 정밀하게 라벨이 일치하지
# 않아도(예: Speech↔Conversation↔Narration) 같은 카테고리면 매칭한다.
YAMNET_CATEGORY_MATCH_MIN = 0.20

# CLAP 판단 임계치
CLAP_SINGLE_MIN      = 0.18   # 후보 1개일 때 최소 유사도
CLAP_MULTI_MIN       = 0.12   # 후보 여러 개일 때 최소 유사도
CLAP_MARGIN_MIN      = 0.03   # CLAP 1위-2위 최솟값
CLAP_OVERRIDE_GAP    = 0.05   # CLAP이 YAMNet 오버라이드에 필요한 추가 마진

# Model A+
ALERT_THRESHOLD      = 0.37   # P(Alert) 이상이면 알림

# 소리 등록 분류용 LLM 모델.
# 약한 모델(haiku)은 같은 의미의 단어(개/강아지)를 들쭉날쭉 분류해서
# 등록 구조가 불안정했음 → 기본을 더 강한 모델로. 환경변수로 변경 가능.
LLM_MODEL = os.environ.get("PROMPTEAR_LLM_MODEL", "claude-haiku-4-5-20251001")

# 유효 카테고리 (아래 YAMNET_ONTOLOGY 키와 동일하게 유지)
VALID_CATEGORIES = {
    "speech", "human_voice", "animal", "music", "nature",
    "vehicle", "machinery", "weapon", "physical", "ambient",
}

# 기본 Context 목록
DEFAULT_CONTEXTS = [
    "home", "sleeping", "walking_outside", "driving",
    "classroom", "studying", "office", "public_transport",
]

# ───────────────────────────────────────────────────────────────
# 긴급 라벨 (두 파일 병합, 더 포괄적으로)
# ───────────────────────────────────────────────────────────────
URGENT_LABELS = {
    "Car alarm",
    "Vehicle horn, car horn, honking",
    "Vehicle horn, car horn, honking, honk",
    "Ambulance (siren)",
    "Fire alarm",
    "Smoke detector, smoke alarm",
    "Civil defense siren",
    "Screaming",
    "Glass break, glass breaking",
    "Gunshot, gunfire",
    "Siren",
    "Emergency vehicle",
    "Police car (siren)",
    "Fire engine, fire truck (siren)",
}

# ───────────────────────────────────────────────────────────────
# 소리별 Alert prior (동료 파일)
# U = P(Alert=1 | Sound)
# ───────────────────────────────────────────────────────────────
SOUND_ALERT_PRIOR: dict[str, float] = {
    "Car alarm":                              0.95,
    "Vehicle horn, car horn, honking":        0.90,
    "Vehicle horn, car horn, honking, honk":  0.90,
    "Ambulance (siren)":                      0.95,
    "Fire alarm":                             0.98,
    "Smoke detector, smoke alarm":            0.98,
    "Civil defense siren":                    0.95,
    "Screaming":                              0.92,
    "Glass break, glass breaking":            0.88,
    "Gunshot, gunfire":                       0.98,
    "Siren":                                  0.90,
    "Emergency vehicle":                      0.90,
    "Baby cry, infant cry":                   0.75,
    "Doorbell":                               0.70,
    "Knock":                                  0.65,
    "Telephone bell ringing":                 0.55,
    "Alarm clock":                            0.72,
    "Typing":                                 0.08,
    "Music":                                  0.10,
    "Rain":                                   0.08,
    "Wind":                                   0.08,
    "Conversation":                           0.20,
}

# X = P(Alert=1 | Sound, Context)
SOUND_CONTEXT_ALERT_PRIOR: dict[tuple[str, str], float] = {
    ("Vehicle horn, car horn, honking", "walking_outside"): 0.95,
    ("Vehicle horn, car horn, honking", "driving"):         0.95,
    ("Vehicle horn, car horn, honking", "home"):            0.35,
    ("Doorbell", "home"):                                   0.85,
    ("Doorbell", "sleeping"):                               0.90,
    ("Doorbell", "classroom"):                              0.25,
    ("Knock", "home"):                                      0.82,
    ("Knock", "sleeping"):                                  0.88,
    ("Knock", "classroom"):                                 0.25,
    ("Alarm clock", "sleeping"):                            0.95,
    ("Telephone bell ringing", "classroom"):                0.25,
    ("Telephone bell ringing", "studying"):                 0.45,
}

# ───────────────────────────────────────────────────────────────
# YAMNet 온톨로지 계층 구조 (main.py)
# AudioSet 521개 클래스를 의미 단위로 묶은 최상위 카테고리
# ───────────────────────────────────────────────────────────────
YAMNET_ONTOLOGY: dict[str, set[int]] = {
    "speech":        set(range(0,  12)) | {63, 64, 65, 66},
    "human_voice":   set(range(12, 63)),
    "animal":        set(range(67, 132)),
    "music":         set(range(132, 277)),
    "nature":        set(range(277, 294)),
    "vehicle":       set(range(294, 337)),
    "machinery":     set(range(337, 412)),
    "weapon":        set(range(412, 431)),
    "physical":      set(range(431, 494)),
    "ambient":       set(range(494, 521)),
}

ANIMAL_SUBCATEGORIES: dict[str, set[int]] = {
    "dog":       {69, 70, 71, 72, 73, 74, 75},
    "cat":       {76, 77, 78, 79, 80},
    "livestock": set(range(81, 103)),
    "wild_large":{103, 104, 105},
    "bird":      set(range(106, 117)),
    "canidae":   {117},
    "rodent":    {118, 119, 120},
    "insect":    set(range(121, 127)),
    "amphibian": {127, 128},
    "reptile":   {129, 130},
    "marine":    {131},
}

# 인덱스 → 카테고리 역방향 맵
INDEX_TO_CATEGORY: dict[int, str] = {
    idx: cat
    for cat, indices in YAMNET_ONTOLOGY.items()
    for idx in indices
}

# 이 클래스가 나오면 "대분류는 맞혔지만 세부 불명확"으로 간주
YAMNET_PARENT_NODES = {
    "Animal", "Domestic animals, pets",
    "Livestock, farm animals, working animals", "Wild animals",
    "Bird", "Canidae, dogs, wolves", "Rodents, rats, mice", "Insect",
    "Vehicle", "Motor vehicle (road)", "Engine", "Mechanisms", "Tools",
    "Musical instrument", "Music",
}

# ───────────────────────────────────────────────────────────────
# FastAPI 앱
# ───────────────────────────────────────────────────────────────
app = FastAPI(title="PromptEar Server")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ───────────────────────────────────────────────────────────────
# 전역 모델 변수
# ───────────────────────────────────────────────────────────────
yamnet_model   = None
yamnet_labels: list[str] = []
YAMNET_LABEL_TO_IDX: dict[str, int] = {}

clap_processor = None
clap_model     = None

anthropic_client = None
openai_client    = None   # STT(음성→텍스트)용. OPENAI_API_KEY 있을 때만 활성화.

# YAMNet/CLAP 추론 직렬화 락.
# FastAPI 는 sync 엔드포인트를 스레드풀에서 병렬 실행하므로, 홈 탭의 /analyze
# 와 /register 가 동시에 같은 torch/tf 모델을 호출하면 충돌(텐서 오류 등)이
# 날 수 있다. 단일 사용자 로컬 서버이므로 추론을 직렬화해 안전하게 만든다.
_infer_lock = threading.Lock()

# STT 모델 (stt.py 와 동일 기본값)
STT_MODEL = "gpt-4o-mini-transcribe"

# ───────────────────────────────────────────────────────────────
# 프롬프트 저장소
# ───────────────────────────────────────────────────────────────
prompt_store: dict[str, dict[str, Any]] = {}


def save_prompts() -> None:
    serializable = {}
    for pid, d in prompt_store.items():
        serializable[pid] = {
            "description":        d.get("description"),
            "embedding":          d.get("embedding"),
            "category":           d.get("category", "unknown"),
            "sub_category":       d.get("sub_category"),
            "covered_by_yamnet":  d.get("covered_by_yamnet", False),
            "yamnet_class":       d.get("yamnet_class"),
            "yamnet_class_idx":   d.get("yamnet_class_idx"),   # 빠른 매칭용 인덱스
            "parent_node":        d.get("parent_node"),
            "alert_prior":        d.get("alert_prior", 0.5),
            "context_alert_prior":d.get("context_alert_prior", {}),
            "prior_source":       d.get("prior_source", ""),
            "prior_reason":       d.get("prior_reason", ""),
            "risk_level":         d.get("risk_level", "medium"),
            "enabled":            d.get("enabled", True),      # 진동 on/off
            "created_at_unix":    d.get("created_at_unix", time.time()),
        }
    with open(PROMPTS_FILE, "w", encoding="utf-8") as f:
        json.dump(serializable, f, ensure_ascii=False, indent=2)


def _migrate_embedding(raw: Any) -> list[float]:
    """
    이전 서버(AudioGen 기반)가 [[...]] 형태로 저장한 임베딩을 flat [...]으로 변환.
    이미 flat이면 그대로 반환.
    """
    if isinstance(raw, list) and len(raw) == 1 and isinstance(raw[0], list):
        return raw[0]
    return raw


def load_prompts() -> None:
    global prompt_store
    if not os.path.exists(PROMPTS_FILE):
        return
    with open(PROMPTS_FILE, "r", encoding="utf-8") as f:
        raw = json.load(f)

    migrated = 0
    for _, data in raw.items():
        emb = data.get("embedding")
        if emb is not None:
            fixed = _migrate_embedding(emb)
            if fixed is not emb:
                data["embedding"] = fixed
                migrated += 1
    prompt_store = raw
    print(
        f"저장된 프롬프트 {len(prompt_store)}개 불러옴"
        + (f" (임베딩 포맷 {migrated}개 변환)" if migrated else ""),
        flush=True,
    )


def _migrate_prompt_embeddings() -> None:
    """
    서버 시작 시 호출.
    저장된 임베딩이 CLAP projection 차원(512)과 맞지 않으면
    현재 text_model → text_projection 경로로 재생성한다.
    """
    proj_dim = _get_clap_projection_dim()
    to_regen: list[str] = []

    for pid, data in prompt_store.items():
        emb = data.get("embedding")
        if not emb:
            to_regen.append(pid)
            continue
        arr = np.array(emb, dtype=np.float32).flatten()
        if arr.shape[0] != proj_dim:
            to_regen.append(pid)

    if not to_regen:
        return

    print(f"임베딩 마이그레이션 필요: {len(to_regen)}개 (shape ≠ {proj_dim})", flush=True)
    success = 0
    for pid in to_regen:
        desc = prompt_store[pid].get("description", "")
        try:
            new_emb = get_clap_text_embedding(desc)
            prompt_store[pid]["embedding"] = new_emb.tolist()
            success += 1
        except Exception as e:
            print(f"  재생성 실패 ({pid}: '{desc}'): {e}", flush=True)

    if success:
        save_prompts()
        print(f"임베딩 마이그레이션 완료: {success}개 재생성", flush=True)


# ───────────────────────────────────────────────────────────────
# 유틸 함수
# ───────────────────────────────────────────────────────────────
def clamp01(x: float) -> float:
    try:
        return float(max(0.0, min(1.0, x)))
    except Exception:
        return 0.5


def sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-z))
    ez = math.exp(z)
    return ez / (1.0 + ez)


def normalize_audio(audio: np.ndarray) -> np.ndarray:
    """NaN/inf 처리 후 peak normalization"""
    audio = np.nan_to_num(audio.astype(np.float32), nan=0.0, posinf=0.0, neginf=0.0)
    peak = float(np.max(np.abs(audio))) if len(audio) > 0 else 0.0
    return (audio / peak).astype(np.float32) if peak > 0 else audio


def resample_audio(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    if orig_sr == target_sr or len(audio) == 0:
        return audio.astype(np.float32)
    n = max(1, int(len(audio) * target_sr / orig_sr))
    return signal.resample(audio, n).astype(np.float32)


def compute_normalized_loudness(audio: np.ndarray) -> float:
    """RMS 기반 0~1 음량 (RMS 0.35 이상 = 1.0으로 포화)"""
    if len(audio) == 0:
        return 0.0
    rms = float(np.sqrt(np.mean(np.square(audio)) + 1e-12))
    return clamp01(rms / 0.35)


def compute_normalized_snr(audio: np.ndarray) -> float:
    """
    노이즈 샘플 없이 하위 20% 진폭을 노이즈로 근사.
    SNR -5dB ~ 30dB 를 0~1 로 매핑.
    """
    if len(audio) < 10:
        return 0.5
    abs_a    = np.abs(audio)
    thresh   = np.percentile(abs_a, 20)
    noise    = audio[abs_a <= thresh]
    np_pwr   = float(np.mean(np.square(noise)) + 1e-9) if len(noise) >= 5 \
               else float(np.percentile(np.square(audio), 10) + 1e-9)
    sig_pwr  = float(np.mean(np.square(audio)) + 1e-9)
    snr_db   = 10.0 * math.log10(max(sig_pwr / np_pwr, 1e-9))
    return clamp01((snr_db + 5.0) / 35.0)


# ───────────────────────────────────────────────────────────────
# 알림 확률 계산 (신뢰도 게이트 버전)
#
# 문제: 이전 공식 z = -2.0 + 3.5*X + 1.0*L + 0.5*C 은 탐지 신뢰도 C의
#       가중치가 0.5뿐이라, 소리를 0.05 신뢰도로 "겨우" 탐지해도
#       prior(X)만 높으면 P(Alert)가 90% 넘게 나왔다.
#       (= "신뢰도가 매우 낮은데 높게 나오는" 현상)
#       또한 절편/계수 합이 커서 상위 구간이 97~98%에 몰려 포화됐다.
#
# 해결: P(Alert)을 "탐지가 맞다는 확신(C)" × "그 소리가 알림감일 확률(X)"의
#       결합으로 본다. C가 낮으면 X가 아무리 높아도 P(Alert)가 눌리도록
#       C에 큰 가중치와 C·X 상호작용항을 둔다.
#
#   z = -4.0 + 4.0*C + 2.5*X + 1.0*(C*X) + 0.5*L
#   P(Alert) = sigmoid(z)   (threshold = 0.50)
#
# 대표적 결과:
#   저신뢰 탐지 (C=0.10, X=0.95, L=0.8) → z≈-0.73 → 33%   ← 더 이상 높지 않음
#   조용한 배경 (C=0.30, X=0.10, L=0.2) → z≈-2.43 → 8%
#   중립 미상   (C=0.50, X=0.50, L=0.5) → z≈-0.25 → 44%
#   초인종(집)  (C=0.70, X=0.85, L=0.6) → z≈ 1.82 → 86%
#   화재경보    (C=0.90, X=0.98, L=0.9) → z≈ 3.28 → 96%
#
# 주의: 최종 알림 여부(should_alert)는 /analyze 에서 "등록된 프롬프트 매칭"
#       으로 별도 결정한다. 여기 p_alert/should_alert 는 참고용 점수다.
# ───────────────────────────────────────────────────────────────
def calculate_alert_probability(
    C: float, U: float, S: float, X: float, L: float
) -> dict[str, Any]:
    C, U, S, X, L = map(clamp01, [C, U, S, X, L])

    z = -4.0 + 4.0 * C + 2.5 * X + 1.0 * (C * X) + 0.5 * L
    p = sigmoid(z)

    return {
        "C": round(C, 4), "U": round(U, 4), "S": round(S, 4),
        "X": round(X, 4), "L": round(L, 4),
        "z": round(z, 4), "p_alert": round(p, 4),
        "threshold": 0.50,
        "should_alert": bool(p >= 0.50),
    }


# ───────────────────────────────────────────────────────────────
# Prior 조회 함수 (동료 파일)
# ───────────────────────────────────────────────────────────────
def get_sound_alert_prior(
    sound_label: str, prompt_id: str | None
) -> tuple[float, dict[str, Any]]:
    """U = P(Alert=1 | Sound). 등록 prompt가 있으면 저장된 값 우선."""
    if prompt_id and prompt_id in prompt_store:
        data = prompt_store[prompt_id]
        if "alert_prior" in data:
            return clamp01(float(data["alert_prior"])), {
                "source": data.get("prior_source", "custom_prompt"),
                "reason": data.get("prior_reason", ""),
                "risk_level": data.get("risk_level", ""),
            }
    if sound_label in SOUND_ALERT_PRIOR:
        return clamp01(SOUND_ALERT_PRIOR[sound_label]), {
            "source": "static_table",
            "reason": "기본 소리별 prior 테이블",
            "risk_level": "",
        }
    return 0.5, {"source": "default", "reason": "알 수 없는 소리, 중립값 사용", "risk_level": ""}


def get_context_alert_prior(
    sound_label: str,
    context: str | None,
    prompt_id: str | None,
    fallback_u: float,
) -> tuple[float, dict[str, Any]]:
    """X = P(Alert=1 | Sound, Context). context 없으면 X=U."""
    if not context:
        return fallback_u, {"source": "no_context", "reason": "context 없음, X=U"}
    if prompt_id and prompt_id in prompt_store:
        ctx_prior = (prompt_store[prompt_id].get("context_alert_prior") or {})
        if context in ctx_prior:
            return clamp01(float(ctx_prior[context])), {
                "source": "custom_prompt_context",
                "reason": prompt_store[prompt_id].get("prior_reason", ""),
            }
    if (sound_label, context) in SOUND_CONTEXT_ALERT_PRIOR:
        return clamp01(SOUND_CONTEXT_ALERT_PRIOR[(sound_label, context)]), {
            "source": "static_table",
            "reason": "기본 소리-상황 prior 테이블",
        }
    return fallback_u, {"source": "context_missing", "reason": "해당 context prior 없음, X=U"}


# ───────────────────────────────────────────────────────────────
# CLAP 임베딩 (Transformers 전용, ONNX/AudioGen 불필요)
# ───────────────────────────────────────────────────────────────
def _get_clap_projection_dim() -> int:
    """CLAP 모델의 실제 projection 차원을 반환 (보통 512)"""
    try:
        return clap_model.text_projection.out_features
    except Exception:
        return 512


def get_clap_audio_embedding(audio_48k: np.ndarray) -> np.ndarray:
    """
    CLAP 오디오 임베딩 추출.
    반환: shape (projection_dim,) — 보통 (512,)

    HTSAT 모델은 pooler_output이 None일 수 있으므로
    None이면 last_hidden_state를 mean-pool해서 대체한다.
    """
    with _infer_lock:
        inputs = clap_processor(
            audios=[audio_48k], return_tensors="pt", sampling_rate=48000
        )
        with torch.no_grad():
            audio_out = clap_model.audio_model(
                input_features=inputs.get("input_features"),
                is_longer=inputs.get("is_longer"),
            )
            # pooler_output이 None이면 last_hidden_state 평균으로 대체
            if audio_out.pooler_output is not None:
                pooled = audio_out.pooler_output          # (batch, hidden_dim)
            else:
                pooled = audio_out.last_hidden_state.mean(dim=1)  # (batch, hidden_dim)
            proj = clap_model.audio_projection(pooled)    # (batch, projection_dim)
            proj = proj / proj.norm(p=2, dim=-1, keepdim=True)
        emb = proj[0].cpu().numpy().astype(np.float32)
    return emb / (np.linalg.norm(emb) + 1e-9)


def get_clap_text_embedding(text: str) -> np.ndarray:
    """
    CLAP 텍스트 임베딩 추출.
    get_text_features() API 변경에 대비해 내부 경로(text_model → text_projection)를 직접 사용.
    반환: shape (projection_dim,) — 보통 (512,)
    """
    with _infer_lock:
        inputs = clap_processor(text=[text], return_tensors="pt", padding=True)
        with torch.no_grad():
            text_out = clap_model.text_model(
                input_ids=inputs.get("input_ids"),
                attention_mask=inputs.get("attention_mask"),
            )
            # pooler_output: CLS 토큰 (batch, hidden_dim)
            pooled  = text_out.pooler_output
            # 프로젝션: (batch, projection_dim)
            proj    = clap_model.text_projection(pooled)
            proj    = proj / proj.norm(p=2, dim=-1, keepdim=True)
        emb = proj[0].cpu().numpy().astype(np.float32)
    return emb / (np.linalg.norm(emb) + 1e-9)


def _resolve_yamnet_idx(class_name: str | None) -> int | None:
    """
    YAMNet 라벨 문자열 → 인덱스. 정확히 일치하지 않으면 부분 일치로 관대하게 매칭.
    (LLM이 'Speech' 처럼 라벨만 줘도 인덱스를 찾아준다)
    """
    if not class_name:
        return None
    # 1) 정확 일치
    idx = YAMNET_LABEL_TO_IDX.get(class_name)
    if idx is not None:
        return idx
    # 2) 대소문자 무시 + 부분 일치
    cl = class_name.strip().lower()
    if not cl:
        return None
    for label, i in YAMNET_LABEL_TO_IDX.items():
        ll = label.lower()
        if ll == cl or cl in ll or ll.split(",")[0].strip() == cl:
            return i
    return None


_YAMNET_CATALOG_CACHE: str | None = None


def _yamnet_label_catalog() -> str:
    """LLM 프롬프트에 넣을 'idx:label' 전체 목록 문자열 (1회 캐시)."""
    global _YAMNET_CATALOG_CACHE
    if _YAMNET_CATALOG_CACHE is None:
        _YAMNET_CATALOG_CACHE = ", ".join(
            f"{i}:{lab}" for i, lab in enumerate(yamnet_labels)
        )
    return _YAMNET_CATALOG_CACHE


def _canonicalize_ontology(data: dict[str, Any]) -> dict[str, Any]:
    """
    LLM/폴백 분류 결과를 온톨로지와 100% 일치하도록 정규화한다.

    핵심: yamnet_class 가 실제 YAMNet 클래스로 해석되면, category/sub_category 를
    그 인덱스로부터 강제 재계산한다. 이렇게 하면 '개'/'강아지'/'puppy' 처럼
    표현이 달라도, 같은 YAMNet 클래스(Dog)로 해석되는 한 동일한 구조(category=
    animal, sub_category=dog, covered=True)를 보장한다. 또 등록 시점 category 가
    탐지 시점 INDEX_TO_CATEGORY 와 항상 일치해 매칭이 안정적이다.
    """
    idx = _resolve_yamnet_idx(data.get("yamnet_class"))
    if idx is not None:
        canonical_label = yamnet_labels[idx]
        data["yamnet_class"]      = canonical_label          # 표준 라벨로 교정
        data["yamnet_class_idx"]  = idx
        data["covered_by_yamnet"] = True
        data["category"]          = INDEX_TO_CATEGORY.get(idx, "unknown")
        data["sub_category"]      = (
            get_animal_subcategory(canonical_label)
            if data["category"] == "animal" else data.get("sub_category")
        )
    else:
        # YAMNet 클래스로 해석 불가 → CLAP 추론에 맡김
        data["yamnet_class_idx"]  = None
        data["covered_by_yamnet"] = False
        if data.get("category") not in VALID_CATEGORIES:
            data["category"] = "unknown"
    return data


def get_animal_subcategory(label: str) -> str | None:
    idx = YAMNET_LABEL_TO_IDX.get(label)
    if idx is None:
        return None
    for sub, indices in ANIMAL_SUBCATEGORIES.items():
        if idx in indices:
            return sub
    return None


def check_duplicate_prompts(
    new_text: str,
    new_emb: np.ndarray,
    threshold: float = 0.88,
    category: str | None = None,
) -> list[dict[str, Any]]:
    """
    새 프롬프트가 기존 등록 프롬프트와 유사한지 CLAP 임베딩으로 비교.
    유사도 >= threshold이면 해당 항목 리스트 반환.

    category 가 주어지면 "같은 카테고리"끼리만 비교한다. CLAP 텍스트 임베딩은
    한국어 단어에서 부정확해서(예: 오토바이↔피아노) 카테고리가 다른데도 높게
    나오는 오탐을 막기 위함.
    """
    duplicates = []
    for pid, data in prompt_store.items():
        emb = data.get("embedding")
        if not emb:
            continue
        # 카테고리가 다르면 비교하지 않음 (서로 다른 종류의 소리는 중복 아님)
        if category and data.get("category") and data.get("category") != category:
            continue
        try:
            ref = np.array(emb, dtype=np.float32).flatten()
            # 둘 다 같은 1D shape여야 유효한 비교
            if ref.ndim != 1 or new_emb.ndim != 1 or ref.shape != new_emb.shape:
                continue
            ref = ref / (np.linalg.norm(ref) + 1e-9)
            sim = float(np.dot(new_emb, ref))
        except Exception:
            continue
        if sim >= threshold:
            duplicates.append({
                "prompt_id":   pid,
                "description": data.get("description", ""),
                "similarity":  round(sim, 4),
            })
    return sorted(duplicates, key=lambda x: x["similarity"], reverse=True)


def get_enabled_yamnet_classes() -> dict[int, str]:
    """
    covered_by_yamnet=True이고 enabled=True인 프롬프트의
    {yamnet_class_idx: prompt_id} 맵 반환.
    (분석 시 빠른 룩업에 사용)
    """
    result: dict[int, str] = {}
    for pid, data in prompt_store.items():
        if (data.get("covered_by_yamnet") and
                data.get("enabled", True) and
                data.get("yamnet_class_idx") is not None):
            result[int(data["yamnet_class_idx"])] = pid
    return result


def match_registered_by_category(
    yamnet_result: dict[str, Any],
) -> dict[str, Any] | None:
    """
    YAMNet 결과를 등록 프롬프트와 "카테고리(서브트리) 단위"로 매칭.

    라벨이 정확히 같지 않아도(예: 등록='Speech' 인데 탐지='Conversation')
    같은 온톨로지 카테고리면 매칭한다. animal은 서브카테고리까지 같을 때만.
    enabled=True 이고 covered_by_yamnet=True 인 프롬프트만 대상.

    반환: {prompt_id, label(매칭된 YAMNet 라벨), score, category} | None
    """
    covered = [
        (pid, d) for pid, d in prompt_store.items()
        if d.get("enabled", True) and d.get("covered_by_yamnet", False)
    ]
    if not covered:
        return None

    for entry in yamnet_result.get("top5", []):
        score = float(entry.get("score", 0.0))
        if score < YAMNET_CATEGORY_MATCH_MIN:
            continue
        label = entry["label"]
        idx   = YAMNET_LABEL_TO_IDX.get(label)
        if idx is None:
            continue
        ent_cat = INDEX_TO_CATEGORY.get(idx, "unknown")
        ent_sub = get_animal_subcategory(label) if ent_cat == "animal" else None

        for pid, d in covered:
            if d.get("category") != ent_cat:
                continue
            # animal: 등록 프롬프트가 서브카테고리를 지정했으면 일치해야 함
            if ent_cat == "animal":
                want_sub = d.get("sub_category")
                if want_sub and ent_sub and want_sub != ent_sub:
                    continue
            return {
                "prompt_id": pid,
                "label":     label,
                "score":     score,
                "category":  ent_cat,
            }
    return None


# ───────────────────────────────────────────────────────────────
# LLM: 온톨로지 분류 + U/X prior 추정 (Claude 단일 호출)
# ───────────────────────────────────────────────────────────────

# API 없을 때 키워드 폴백
_KEYWORD_MAP: list[tuple[list[str], str, str | None]] = [
    (["dog", "개", "bark", "howl", "woof"],                    "animal",    "dog"),
    (["cat", "고양이", "meow", "purr", "hiss"],                "animal",    "cat"),
    (["bird", "새", "chirp", "tweet", "crow", "owl"],          "animal",    "bird"),
    (["insect", "곤충", "cricket", "mosquito", "bee", "buzz"], "animal",    "insect"),
    (["frog", "개구리", "snake", "뱀", "whale", "고래"],        "animal",    None),
    (["animal", "동물", "beast", "wildlife", "야생"],           "animal",    None),
    (["rain", "비", "wind", "바람", "thunder", "천둥", "불"],   "nature",    None),
    (["water", "물", "wave", "파도", "waterfall"],             "nature",    None),
    (["car", "자동차", "truck", "train", "기차", "plane", "비행기"], "vehicle", None),
    (["music", "음악", "guitar", "piano", "drum", "violin"],   "music",     None),
    (["speech", "말", "talk", "대화", "shout", "scream"],      "speech",    None),
    (["machine", "기계", "engine", "엔진", "alarm", "알람"],    "machinery", None),
    (["explosion", "폭발", "gunshot", "총", "bang"],            "weapon",    None),
]

# YAMNet에 이미 있는 주요 소리 → (yamnet_class_name, yamnet_class_idx)
# (확장 가능 — 자주 등록될 만한 소리들 선제 목록)
_YAMNET_COVERAGE_MAP: dict[str, tuple[str, int]] = {
    # 악기
    "violin": ("Violin, fiddle", 186), "바이올린": ("Violin, fiddle", 186),
    "piano": ("Piano", 148), "피아노": ("Piano", 148),
    "guitar": ("Guitar", 135), "기타": ("Guitar", 135),
    "drum": ("Drum", 159), "드럼": ("Drum", 159),
    "saxophone": ("Saxophone", 192), "색소폰": ("Saxophone", 192),
    "trumpet": ("Trumpet", 182), "트럼펫": ("Trumpet", 182),
    "cello": ("Cello", 188), "첼로": ("Cello", 188),
    "flute": ("Flute", 191), "플루트": ("Flute", 191),
    # 동물 (동의어/지소어 포함 — 같은 의미는 같은 클래스로)
    "dog": ("Dog", 69), "개": ("Dog", 69), "강아지": ("Dog", 69),
    "멍멍": ("Dog", 69), "멍멍이": ("Dog", 69), "puppy": ("Dog", 69), "doggy": ("Dog", 69),
    "bark": ("Bark", 70), "짖": ("Bark", 70),
    "cat": ("Cat", 76), "고양이": ("Cat", 76), "야옹이": ("Cat", 76), "kitten": ("Cat", 76),
    "meow": ("Meow", 78), "야옹": ("Meow", 78),
    "bird": ("Bird", 106), "새": ("Bird", 106), "부엉이": ("Owl", 112), "owl": ("Owl", 112),
    "chirp": ("Chirp, tweet", 108), "짹": ("Chirp, tweet", 108),
    # 탈것
    "motorcycle": ("Motorcycle", 343), "오토바이": ("Motorcycle", 343), "바이크": ("Motorcycle", 343),
    "car": ("Car", 300), "자동차": ("Car", 300), "승용차": ("Car", 300),
    "truck": ("Truck", 325), "트럭": ("Truck", 325),
    "train": ("Train", 328), "기차": ("Train", 328), "열차": ("Train", 328),
    "bus": ("Bus", 324), "버스": ("Bus", 324),
    # 긴급
    "siren": ("Siren", 390), "사이렌": ("Siren", 390),
    "fire alarm": ("Fire alarm", 394), "화재경보": ("Fire alarm", 394),
    "smoke detector": ("Smoke detector, smoke alarm", 393), "연기감지": ("Smoke detector, smoke alarm", 393),
    "car alarm": ("Car alarm", 304), "자동차경보": ("Car alarm", 304),
    "ambulance": ("Ambulance (siren)", 318), "구급차": ("Ambulance (siren)", 318),
    "gunshot": ("Gunshot, gunfire", 421), "총소리": ("Gunshot, gunfire", 421),
    "scream": ("Screaming", 11), "비명": ("Screaming", 11),
    # 생활
    "doorbell": ("Doorbell", 349), "초인종": ("Doorbell", 349),
    "knock": ("Knock", 353), "노크": ("Knock", 353),
    "baby": ("Baby cry, infant cry", 20), "아기": ("Baby cry, infant cry", 20),
    "cry": ("Crying, sobbing", 19), "울음": ("Crying, sobbing", 19),
    "cough": ("Cough", 42), "기침": ("Cough", 42),
    "sneeze": ("Sneeze", 44), "재채기": ("Sneeze", 44),
    "rain": ("Rain", 283), "비": ("Rain", 283),
    "thunder": ("Thunder", 281), "천둥": ("Thunder", 281),
    "phone": ("Telephone bell ringing", 384), "전화": ("Telephone bell ringing", 384),
    "alarm clock": ("Alarm clock", 389), "알람": ("Alarm clock", 389),
    # 사람 음성 (speech 계열) ← 자주 등록하는 케이스
    "speech": ("Speech", 0), "말하": ("Speech", 0), "말소리": ("Speech", 0),
    "사람 목소리": ("Speech", 0), "목소리": ("Speech", 0), "인간 목소리": ("Speech", 0),
    "대화 소리": ("Conversation", 2), "conversation": ("Conversation", 2),
    "사람 말": ("Speech", 0), "언어": ("Speech", 0), "발화": ("Speech", 0),
    # '사람' 단독은 너무 광범위하니 복합어만 매핑
    "사람이 말": ("Speech", 0), "사람이 대화": ("Conversation", 2),
    "아이 말": ("Child speech, kid speaking", 1), "어린이 말": ("Child speech, kid speaking", 1),
    "속삭": ("Whispering", 12), "속삭임": ("Whispering", 12),
    "웃음": ("Laughter", 13), "笑": ("Laughter", 13),
    "노래": ("Singing", 24), "노래하": ("Singing", 24),
}

_HIGH_RISK_KW   = ["siren","alarm","fire","smoke","scream","glass break","gunshot",
                   "crash","horn","ambulance","emergency","explosion"]
_MED_HIGH_KW    = ["baby","cry","doorbell","knock","timer","phone","ringing","boiling"]
_LOW_KW         = ["keyboard","typing","music","rain","wind","fan","conversation",
                   "footstep","background","noise"]


def _fallback_classify_and_estimate(
    description: str, contexts: list[str]
) -> dict[str, Any]:
    """Claude API 없을 때 키워드 기반 분류 + 규칙 기반 prior 추정 통합 폴백"""
    desc = description.lower()

    # 온톨로지 분류
    category, sub_category = "unknown", None
    for keywords, cat, sub in _KEYWORD_MAP:
        if any(kw in desc for kw in keywords):
            category, sub_category = cat, sub
            break

    # U 추정
    if any(kw in desc for kw in _HIGH_RISK_KW):
        u, risk = 0.90, "high"
        reason = "위험·긴급 키워드 감지"
    elif any(kw in desc for kw in _MED_HIGH_KW):
        u, risk = 0.72, "medium_high"
        reason = "생활 알림성 키워드 감지"
    elif any(kw in desc for kw in _LOW_KW):
        u, risk = 0.18, "low"
        reason = "배경음·저우선순위 키워드 감지"
    else:
        u, risk = 0.50, "medium"
        reason = "명확한 키워드 없음, 중립값 사용"

    # X 추정 (context별 보정)
    x_by_context: dict[str, float] = {}
    for ctx in contexts:
        x = u
        if ctx in {"sleeping", "driving", "walking_outside"}:
            x += 0.08
        if ctx in {"classroom", "studying", "office"}:
            x -= 0.08
        if ctx == "home" and any(kw in desc for kw in ["doorbell","knock","baby","cry","timer"]):
            x += 0.12
        if ctx in {"walking_outside","driving"} and any(
            kw in desc for kw in ["horn","siren","crash","ambulance"]
        ):
            x += 0.12
        x_by_context[ctx] = round(clamp01(x), 4)

    # YAMNet 커버리지 확인 (fallback에서도 주요 소리는 감지)
    covered, yamnet_class, yamnet_class_idx = False, None, None
    for kw, (cls_name, cls_idx) in _YAMNET_COVERAGE_MAP.items():
        if kw in desc:
            covered, yamnet_class, yamnet_class_idx = True, cls_name, cls_idx
            break

    result = {
        "category":           category,
        "sub_category":       sub_category,
        "covered_by_yamnet":  covered,
        "yamnet_class":       yamnet_class,
        "yamnet_class_idx":   yamnet_class_idx,
        "parent_node":        category.capitalize() if category != "unknown" else None,
        "alert_prior_u":      round(clamp01(u), 4),
        "context_alert_prior":x_by_context,
        "risk_level":         risk,
        "reason":             reason,
        "source":             "fallback",
    }
    # 온톨로지 정규화 (yamnet_class 로부터 category/sub_category 강제 일치)
    return _canonicalize_ontology(result)


def _pick_working_llm_model(client: Any, preferred: str) -> str | None:
    """
    실제로 호출되는 모델을 startup 때 한 번 확인한다.
    preferred(예: claude-sonnet-4-6)가 거부되면 알려진 안전한 모델로 순차 폴백.
    하나도 성공 못 하면 None (→ 규칙 기반 fallback).
    """
    # 검증된 모델만 후보로 (claude-3-5-*-latest 는 404로 확인됨)
    candidates: list[str] = []
    for m in (preferred, "claude-sonnet-4-6", "claude-haiku-4-5-20251001"):
        if m and m not in candidates:
            candidates.append(m)
    for m in candidates:
        try:
            client.messages.create(
                model=m, max_tokens=4,
                messages=[{"role": "user", "content": "ping"}],
            )
            return m
        except Exception as e:
            print(f"  LLM 모델 '{m}' 사용 불가: {e}", flush=True)
    return None


def classify_and_estimate_with_llm(
    description: str, contexts: list[str]
) -> dict[str, Any]:
    """
    Claude 단일 호출로 두 가지 작업을 동시에 처리:
      1. YAMNet 온톨로지 분류 (category, covered_by_yamnet 등)
      2. Alert prior 추정 (U, X_by_context, risk_level)
    실패 시 fallback 반환.
    """
    if not anthropic_client:
        result = _fallback_classify_and_estimate(description, contexts)
        result["source"] = "fallback_no_api_key"
        return result

    categories_desc = (
        "speech: 말하기·대화·외침 등 언어적 음성\n"
        "human_voice: 웃음·울음·노래·호흡 등 비언어적 인간 소리\n"
        "animal: 동물 소리 (개, 고양이, 새, 곤충, 야생동물 등)\n"
        "music: 악기 연주, 음악 장르\n"
        "nature: 바람, 비, 천둥, 물소리, 불 등\n"
        "vehicle: 자동차, 기차, 비행기, 배\n"
        "machinery: 엔진, 가전제품, 기계, 알람\n"
        "weapon: 공구, 폭발음, 총소리\n"
        "physical: 충돌, 유리, 액체, 긁힘 등 물리적 소리\n"
        "ambient: 정적, 소음, 배경음"
    )
    contexts_str = json.dumps(contexts, ensure_ascii=False)
    catalog = _yamnet_label_catalog()
    n = len(yamnet_labels)

    prompt = f"""당신은 PromptEar(청각장애인용 소리 감지 앱)의 오디오 분류 및 알림 우선순위 전문가입니다.
사용자가 등록한 소리 설명을 분석하여 아래 JSON만 반환하세요.

=== 카테고리 ===
{categories_desc}

=== YAMNet 클래스 전체 목록 (idx:label, 총 {n}개) ===
아래 목록에서만 yamnet_class 를 고르세요. 반드시 label 을 "그대로" 복사하세요.
{catalog}

=== 분류 규칙 (매우 중요) ===
1. 동의어·지소어·다른 표기를 같은 클래스로 정규화하세요. 표현이 달라도
   의미가 같으면 똑같은 yamnet_class 를 고릅니다. 예:
   · 개 = 강아지 = 멍멍이 = puppy = doggy → "Dog"
   · 고양이 = 야옹이 = kitten → "Cat"
   · 오토바이 = 바이크 = motorcycle → "Motorcycle"
   · 사람 말소리 = 대화 = 목소리 = 언어를 구사하는 사람 = 발화 → "Speech"
   · 아이/어린이 말 → "Child speech, kid speaking"
2. 위 목록에 의미가 통하는 클래스가 하나라도 있으면 covered_by_yamnet=true 로,
   yamnet_class 를 그 label 로 정확히 채웁니다. (대부분의 일상 소리는 여기 해당)
3. 목록 어디에도 대응되는 클래스가 정말 없을 때만 covered_by_yamnet=false 로 두고
   yamnet_class=null 로 둡니다(매우 특수한 기계음/특정 멜로디 등 → CLAP 추론).
4. category 는 yamnet_class 가 속한 대분류와 일치해야 합니다.

=== Alert prior 기준 ===
0.00~0.20: 배경음, 음악, 잡담, 키보드 등 대부분 알림 불필요
0.21~0.40: 일부 상황에서만 필요
0.41~0.60: 중립
0.61~0.80: 초인종, 노크, 아기 울음, 타이머 등 대체로 필요
0.81~1.00: 경보, 비명, 사이렌, 화재 등 매우 높은 필요

=== context 목록 ===
{contexts_str}

=== 소리 설명 ===
"{description}"

반드시 아래 형식의 JSON만 반환 (다른 텍스트 없이):
{{
  "category": "...",
  "sub_category": "...",
  "covered_by_yamnet": true/false,
  "yamnet_class": "...",
  "parent_node": "...",
  "alert_prior_u": 0.XX,
  "context_alert_prior": {{{", ".join(f'"{c}": 0.XX' for c in contexts)}}},
  "risk_level": "low|medium|medium_high|high",
  "reason": "한 줄 설명"
}}"""

    try:
        message = anthropic_client.messages.create(
            model=LLM_MODEL,
            max_tokens=512,
            temperature=0,   # 결정론적 분류 (같은 입력 → 같은 결과)
            messages=[{"role": "user", "content": prompt}]
        )
        raw = message.content[0].text.strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        data = json.loads(raw[start:end])

        # 온톨로지 정규화: yamnet_class 로부터 category/sub_category/idx 강제 결정.
        # 이게 동의어(개/강아지)를 같은 구조로 만들고, 등록·탐지 카테고리를 일치시킨다.
        data = _canonicalize_ontology(data)

        # 값 보정
        data["alert_prior_u"] = round(clamp01(float(data.get("alert_prior_u", 0.5))), 4)
        raw_x = data.get("context_alert_prior") or {}
        u_val = data["alert_prior_u"]
        data["context_alert_prior"] = {
            ctx: round(clamp01(float(raw_x.get(ctx, u_val))), 4)
            for ctx in contexts
        }
        data["source"] = LLM_MODEL
        return data

    except Exception as e:
        print(f"LLM 분류 실패 ({e}) → 폴백 사용", flush=True)
        result = _fallback_classify_and_estimate(description, contexts)
        result["source"] = f"fallback_after_error:{e}"
        return result


# ───────────────────────────────────────────────────────────────
# 추론 함수
# ───────────────────────────────────────────────────────────────
def run_yamnet(audio_16k: np.ndarray) -> dict[str, Any]:
    audio_16k = normalize_audio(audio_16k)
    with _infer_lock:
        scores, _, _ = yamnet_model(tf.constant(audio_16k, dtype=tf.float32))
        mean_scores: np.ndarray = tf.reduce_mean(scores, axis=0).numpy()

    top_idx        = int(np.argmax(mean_scores))
    top_label      = yamnet_labels[top_idx]
    top_confidence = float(mean_scores[top_idx])
    category       = INDEX_TO_CATEGORY.get(top_idx, "unknown")

    # 서브트리 내 1위-2위 마진 (모호성 지표)
    subtree_scores = sorted(
        [float(mean_scores[i]) for i in YAMNET_ONTOLOGY.get(category, set())],
        reverse=True,
    )
    subtree_margin = subtree_scores[0] - subtree_scores[1] if len(subtree_scores) >= 2 else 1.0

    top5 = [
        {"label": yamnet_labels[int(i)], "score": float(mean_scores[int(i)])}
        for i in np.argsort(mean_scores)[-5:][::-1]
    ]

    return {
        "label":               top_label,
        "confidence":          top_confidence,
        "category":            category,
        "is_urgent":           top_label in URGENT_LABELS,
        "is_parent_node":      top_label in YAMNET_PARENT_NODES,
        "subtree_top2_margin": subtree_margin,
        "top5":                top5,
    }


def run_clap_in_subtree(
    audio_48k:    np.ndarray,
    category:     str,
    sub_category: str | None = None,
) -> dict[str, Any] | None:
    """
    YAMNet이 지목한 카테고리 서브트리 내 사용자 프롬프트와만 CLAP 비교.
    covered_by_yamnet=True 프롬프트는 YAMNet이 이미 처리하므로 제외.
    """
    # 카테고리 필터 + YAMNet 커버 제외 + 비활성화 제외
    candidates = {
        pid: d for pid, d in prompt_store.items()
        if d.get("category") == category
        and not d.get("covered_by_yamnet", False)
        and d.get("enabled", True)
    }
    # animal: 서브카테고리로 추가 축소
    if sub_category and len(candidates) > 1:
        sub_cands = {p: d for p, d in candidates.items() if d.get("sub_category") == sub_category}
        if sub_cands:
            candidates = sub_cands

    if not candidates:
        return None

    t0 = time.time()
    audio_emb = get_clap_audio_embedding(audio_48k)
    print(f"CLAP 오디오 임베딩: {time.time()-t0:.2f}초, 후보 {len(candidates)}개", flush=True)

    scores: dict[str, float] = {}
    for pid, d in candidates.items():
        try:
            ref = np.array(d["embedding"], dtype=np.float32).flatten()
            if ref.ndim != 1 or ref.shape != audio_emb.shape:
                continue  # 잘못된 shape 스킵
            ref = ref / (np.linalg.norm(ref) + 1e-9)
            scores[pid] = float(np.dot(audio_emb, ref))
        except Exception:
            continue

    if not scores:
        print("CLAP: 유효한 후보 없음 (shape 불일치 등)", flush=True)
        return None

    ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_id, best_score = ranked[0]

    print(f"CLAP 점수: {[(prompt_store[p]['description'][:20], f'{s:.3f}') for p, s in ranked]}", flush=True)

    if len(ranked) == 1:
        if best_score < CLAP_SINGLE_MIN:
            return None
    else:
        margin = best_score - ranked[1][1]
        if best_score < CLAP_MULTI_MIN or margin < CLAP_MARGIN_MIN:
            return None

    return {
        "prompt_id":   best_id,
        "description": candidates[best_id]["description"],
        "similarity":  round(best_score, 4),
        "category":    category,
        "sub_category":candidates[best_id].get("sub_category"),
    }


def choose_primary_sound(
    yamnet_result: dict[str, Any],
    clap_result:   dict[str, Any] | None,
) -> dict[str, Any]:
    """
    분류 결과를 결합해 대표 라벨 선택.
    알림 여부 최종 결정은 Model A+가 담당.
    """
    if yamnet_result["is_urgent"] and yamnet_result["confidence"] >= URGENT_CONF_THRESH:
        return {
            "label":      yamnet_result["label"],
            "confidence": yamnet_result["confidence"],
            "source":     "yamnet",
            "priority":   "urgent_candidate",
            "prompt_id":  None,
            "category":   yamnet_result["category"],
        }

    if yamnet_result["confidence"] >= YAMNET_HIGH:
        return {
            "label":      yamnet_result["label"],
            "confidence": yamnet_result["confidence"],
            "source":     "yamnet",
            "priority":   "normal_candidate",
            "prompt_id":  None,
            "category":   yamnet_result["category"],
        }

    # CLAP이 YAMNet보다 유의미하게 높으면 사용자 정의 소리 우선
    if clap_result and clap_result["similarity"] > yamnet_result["confidence"] + CLAP_OVERRIDE_GAP:
        return {
            "label":      clap_result["description"],
            "confidence": clap_result["similarity"],
            "source":     "clap",
            "priority":   "custom_candidate",
            "prompt_id":  clap_result["prompt_id"],
            "category":   clap_result["category"],
        }

    # 그 외 YAMNet 결과 사용 (신뢰도 낮으면 weak)
    priority = (
        "normal_candidate" if yamnet_result["confidence"] >= YAMNET_MID
        else "weak_candidate"
    )
    return {
        "label":      yamnet_result["label"],
        "confidence": yamnet_result["confidence"],
        "source":     "yamnet",
        "priority":   priority,
        "prompt_id":  None,
        "category":   yamnet_result["category"],
    }


# ───────────────────────────────────────────────────────────────
# 요청 / 응답 모델
# ───────────────────────────────────────────────────────────────
class PromptRegisterRequest(BaseModel):
    prompt_id:   str   = Field(..., description="사용자 정의 소리 ID")
    description: str   = Field(..., description="소리 설명")
    # 선택: 직접 prior를 지정하면 LLM 추정 건너뜀
    alert_prior:         float | None             = Field(None, ge=0.0, le=1.0)
    context_alert_prior: dict[str, float] | None  = None
    contexts:            list[str] | None         = None


class AudioAnalyzeRequest(BaseModel):
    audio:       list[float] = Field(..., description="PCM float 오디오 샘플")
    sample_rate: int         = Field(16000, description="입력 오디오 샘플레이트")
    context:     str | None  = Field(None,  description="home | sleeping | walking_outside 등")


class STTRequest(BaseModel):
    audio:       list[float] = Field(..., description="PCM float 오디오 샘플 (-1~1)")
    sample_rate: int         = Field(16000, description="입력 오디오 샘플레이트")
    language:    str         = Field("ko",  description="인식 언어 (ISO-639-1)")


# ───────────────────────────────────────────────────────────────
# API 엔드포인트
# ───────────────────────────────────────────────────────────────
@app.get("/")
def health():
    return {
        "status": "ok",
        "models": {
            "yamnet":    "loaded" if yamnet_model  else "not_loaded",
            "clap":      "loaded" if clap_model    else "not_loaded",
            "llm":       LLM_MODEL if anthropic_client else "fallback",
            "stt":       STT_MODEL if openai_client else "disabled",
        },
        "paths":          {"base_dir": BASE_DIR},
        "prompts_count":  len(prompt_store),
        "alert_threshold":ALERT_THRESHOLD,
    }


@app.get("/prompts")
def list_prompts():
    return {
        "prompts": [
            {
                "prompt_id":           pid,
                "description":         d.get("description"),
                "category":            d.get("category"),
                "sub_category":        d.get("sub_category"),
                "covered_by_yamnet":   d.get("covered_by_yamnet", False),
                "yamnet_class":        d.get("yamnet_class"),
                "yamnet_class_idx":    d.get("yamnet_class_idx"),
                "parent_node":         d.get("parent_node"),
                "alert_prior":         d.get("alert_prior"),
                "risk_level":          d.get("risk_level"),
                "prior_reason":        d.get("prior_reason"),
                "enabled":             d.get("enabled", True),
            }
            for pid, d in prompt_store.items()
        ]
    }


@app.patch("/prompt/{prompt_id}/toggle")
def toggle_prompt(prompt_id: str):
    """프롬프트 진동 on/off 토글"""
    if prompt_id not in prompt_store:
        raise HTTPException(status_code=404, detail="프롬프트를 찾을 수 없습니다.")
    prompt_store[prompt_id]["enabled"] = not prompt_store[prompt_id].get("enabled", True)
    save_prompts()
    return {"success": True, "enabled": prompt_store[prompt_id]["enabled"]}


@app.post("/prompt/register")
def register_prompt(req: PromptRegisterRequest):
    if not req.prompt_id.strip() or not req.description.strip():
        raise HTTPException(status_code=400, detail="prompt_id와 description은 필수입니다.")

    print(f"\n[프롬프트 등록] '{req.description}'", flush=True)
    contexts = req.contexts or DEFAULT_CONTEXTS

    # 1. Prior 결정 (직접 입력 우선, 없으면 LLM 추정)
    if req.alert_prior is not None:
        classification = _fallback_classify_and_estimate(req.description, contexts)
        classification["alert_prior_u"]      = clamp01(req.alert_prior)
        classification["context_alert_prior"] = {
            k: clamp01(v) for k, v in (req.context_alert_prior or {}).items()
        }
        classification["source"] = "user_provided"
    else:
        classification = classify_and_estimate_with_llm(req.description, contexts)

    print(f"  분류: {classification.get('category')}/{classification.get('sub_category')}, "
          f"covered={classification.get('covered_by_yamnet')}, "
          f"yamnet_class='{classification.get('yamnet_class')}'", flush=True)

    # 2. CLAP 텍스트 임베딩 생성
    try:
        print("  CLAP 텍스트 임베딩 생성 중...", flush=True)
        text_emb = get_clap_text_embedding(req.description)
        print(f"  임베딩 완료 (shape={text_emb.shape})", flush=True)
    except Exception as e:
        import traceback
        print(f"  임베딩 오류:\n{traceback.format_exc()}", flush=True)
        raise HTTPException(status_code=500, detail=f"텍스트 임베딩 실패: {e}")

    # 3. 기존 프롬프트와 유사도 비교 (중복 감지 — 같은 카테고리 내에서만)
    duplicates = check_duplicate_prompts(
        req.description, text_emb, threshold=0.88,
        category=classification.get("category"),
    )
    if duplicates:
        best = duplicates[0]
        print(f"  → 유사 프롬프트 발견: '{best['description']}' (유사도 {best['similarity']:.3f})", flush=True)

    # 4. 저장 (enabled=True 기본)
    prompt_store[req.prompt_id] = {
        "description":        req.description,
        "embedding":          text_emb.tolist(),
        "category":           classification.get("category", "unknown"),
        "sub_category":       classification.get("sub_category"),
        "covered_by_yamnet":  classification.get("covered_by_yamnet", False),
        "yamnet_class":       classification.get("yamnet_class"),
        "yamnet_class_idx":   classification.get("yamnet_class_idx"),
        "parent_node":        classification.get("parent_node"),
        "alert_prior":        classification.get("alert_prior_u", 0.5),
        "context_alert_prior":classification.get("context_alert_prior", {}),
        "prior_source":       classification.get("source", "unknown"),
        "prior_reason":       classification.get("reason", ""),
        "risk_level":         classification.get("risk_level", "medium"),
        "enabled":            True,
        "created_at_unix":    time.time(),
    }
    save_prompts()

    return {
        "success":          True,
        "prompt_id":        req.prompt_id,
        "description":      req.description,
        "classification":   {k: v for k, v in classification.items() if k != "source"},
        # 어떤 경로로 분류됐는지(LLM 모델명 또는 fallback) — 디버깅/확인용
        "classified_by":    classification.get("source", "unknown"),
        # 기존 프롬프트와 유사한 게 있으면 경고
        "duplicate_warning": duplicates if duplicates else None,
    }


@app.delete("/prompt/{prompt_id}")
def delete_prompt(prompt_id: str):
    if prompt_id not in prompt_store:
        raise HTTPException(status_code=404, detail="프롬프트를 찾을 수 없습니다.")
    del prompt_store[prompt_id]
    save_prompts()
    return {"success": True}


@app.delete("/prompts/all")
def clear_all_prompts():
    global prompt_store
    prompt_store = {}
    if os.path.exists(PROMPTS_FILE):
        os.remove(PROMPTS_FILE)
    return {"success": True}


@app.post("/analyze")
def analyze_audio(req: AudioAnalyzeRequest):
    """
    알림 로직 (등록된 소리만 진동):
      진동(should_alert=True) 은 "사용자가 등록했고 enabled=True 인 프롬프트"가
      매칭됐을 때에만 발생한다.
        1. covered_by_yamnet=True  → YAMNet top-k 이 같은 카테고리(서브트리)면 매칭
        2. covered_by_yamnet=False → 모호할 때 CLAP 서브트리 비교로 매칭
      긴급 안전 소리(URGENT_LABELS)는 항상 진동.
      그 외 등록되지 않은 소리는 로그(alerts)에만 남기고 진동하지 않는다.
    """
    if not req.audio:
        raise HTTPException(status_code=400, detail="audio가 비어 있습니다.")

    audio = normalize_audio(np.array(req.audio, dtype=np.float32))
    audio_16k = resample_audio(audio, req.sample_rate, 16000)

    # ── 1단계: YAMNet 분류 ─────────────────────────────────────────
    yamnet_result = run_yamnet(audio_16k)
    S = compute_normalized_snr(audio)
    L = compute_normalized_loudness(audio)
    category    = yamnet_result["category"]
    top_label   = yamnet_result["label"]
    top_conf    = yamnet_result["confidence"]

    clap_result  = None
    matched_pid: str | None = None
    matched_conf: float | None = None
    should_alert = False
    alert_reason = "no_match"

    # ── 2단계: 긴급 안전 소리 — 등록 여부와 무관하게 항상 진동 ────────
    if yamnet_result["is_urgent"] and top_conf > URGENT_CONF_THRESH:
        should_alert = True
        alert_reason = "urgent"

    # ── 3단계: 등록(covered) 프롬프트 카테고리 매칭 ─────────────────
    #   라벨 정밀 일치가 아니라 같은 온톨로지 카테고리면 매칭(speech 등 개선).
    cat_match = match_registered_by_category(yamnet_result)
    if not should_alert and cat_match:
        matched_pid  = cat_match["prompt_id"]
        matched_conf = cat_match["score"]
        should_alert = True
        alert_reason = f"yamnet_category_match:{cat_match['label']}"

    # ── 3단계: CLAP 서브트리 비교 (미커버 등록 프롬프트) ────────────
    if not should_alert and prompt_store and category != "unknown":
        is_ambiguous = (
            yamnet_result["is_parent_node"]
            or yamnet_result["subtree_top2_margin"] < AMBIGUITY_MARGIN
            or top_conf < YAMNET_MID
        )
        if is_ambiguous:
            sub_cat = get_animal_subcategory(top_label) if category == "animal" else None
            audio_48k   = resample_audio(audio, req.sample_rate, 48000)
            clap_result = run_clap_in_subtree(audio_48k, category, sub_cat)
            if clap_result:
                matched_pid  = clap_result["prompt_id"]
                matched_conf = clap_result["similarity"]
                should_alert = True
                alert_reason = "clap_match"

    # ── 4단계: 대표 라벨 선택 ──────────────────────────────────────
    primary = choose_primary_sound(yamnet_result, clap_result)
    if matched_pid and matched_pid in prompt_store:
        primary["prompt_id"] = matched_pid
        # 등록된 소리는 사용자가 적은 설명으로 보여주는 편이 직관적
        primary["label"] = prompt_store[matched_pid].get("description", primary["label"])
        if matched_conf is not None:
            primary["confidence"] = matched_conf

    # ── 5단계: Model A+ (참고용 점수 — 알림 여부는 위에서 이미 결정) ─
    U, u_info = get_sound_alert_prior(primary["label"], primary.get("prompt_id"))
    X, x_info = get_context_alert_prior(
        primary["label"], req.context, primary.get("prompt_id"), fallback_u=U
    )
    # C(탐지 신뢰도)는 실제로 매칭된 소리의 신뢰도를 사용해야 P(Alert)가
    # 신뢰도를 제대로 반영한다(매칭 안 됐으면 YAMNet top 신뢰도).
    detect_conf = matched_conf if matched_conf is not None else top_conf
    alert_model = calculate_alert_probability(
        C=detect_conf, U=U, S=S, X=X, L=L
    )
    # 최종 should_alert는 "등록 프롬프트 매칭" 로직이 우선
    alert_model["should_alert"] = should_alert
    alert_model["alert_reason"] = alert_reason

    return {
        "yamnet":       yamnet_result,
        "clap":         clap_result,
        "primary":      primary,
        "context":      req.context,
        "alert_model":  alert_model,
        "prior_info":   {"U": u_info, "X": x_info},
        "should_alert": should_alert,
        "alert_reason": alert_reason,
    }


# ───────────────────────────────────────────────────────────────
# STT (음성 → 텍스트) — Speech 탭 전용, 추론 파이프라인과 완전 분리
# ───────────────────────────────────────────────────────────────
@app.post("/stt")
def speech_to_text(req: STTRequest):
    if openai_client is None:
        raise HTTPException(
            status_code=503,
            detail="STT 비활성화: 서버에 OPENAI_API_KEY가 설정되어 있지 않습니다.",
        )
    if not req.audio:
        raise HTTPException(status_code=400, detail="audio가 비어 있습니다.")

    # float(-1~1) → int16 PCM WAV (OpenAI 전사 API는 파일 입력 필요)
    audio = np.nan_to_num(np.array(req.audio, dtype=np.float32),
                          nan=0.0, posinf=0.0, neginf=0.0)
    pcm16 = np.clip(audio, -1.0, 1.0)
    pcm16 = (pcm16 * 32767.0).astype(np.int16)

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tf_file:
            tmp_path = tf_file.name
        with wave.open(tmp_path, "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)            # int16 = 2 bytes
            wf.setframerate(int(req.sample_rate))
            wf.writeframes(pcm16.tobytes())

        with open(tmp_path, "rb") as audio_file:
            result = openai_client.audio.transcriptions.create(
                model=STT_MODEL,
                file=audio_file,
                language=req.language,
                response_format="json",
            )
        text = (getattr(result, "text", "") or "").strip()
        print(f"[STT] '{text}'", flush=True)
        return {"text": text}

    except Exception as e:
        print(f"[STT] 실패: {e}", flush=True)
        raise HTTPException(status_code=500, detail=f"STT 처리 실패: {e}")
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


# ───────────────────────────────────────────────────────────────
# 서버 시작
# ───────────────────────────────────────────────────────────────
def startup() -> None:
    global yamnet_model, yamnet_labels, YAMNET_LABEL_TO_IDX
    global clap_processor, clap_model, anthropic_client

    print("=" * 60, flush=True)
    print("PromptEar 통합 서버 시작", flush=True)
    print(f"BASE_DIR = {BASE_DIR}", flush=True)
    print("=" * 60, flush=True)

    # ── YAMNet: 로컬 경로 순서대로 시도 → 없으면 Hub에서 다운로드 ──
    print("YAMNet 로딩 중...", flush=True)
    yamnet_path = next(
        (p for p in _YAMNET_LOCAL_CANDIDATES if os.path.exists(p)),
        _YAMNET_HUB_URL,
    )
    print(f"  경로: {yamnet_path}", flush=True)
    yamnet_model = hub.load(yamnet_path)
    with tf.io.gfile.GFile(yamnet_model.class_map_path().numpy().decode()) as f:
        next(f)
        for line in f:
            yamnet_labels.append(line.strip().split(",")[2])
    YAMNET_LABEL_TO_IDX = {label: i for i, label in enumerate(yamnet_labels)}
    print(f"YAMNet 완료 ({len(yamnet_labels)}개 클래스)", flush=True)

    # ── CLAP (Transformers 전용, ONNX 불필요) ─────────────────────
    print(f"CLAP 로딩 중 (HF_HOME={os.environ['HF_HOME']})...", flush=True)
    clap_processor = ClapProcessor.from_pretrained("laion/clap-htsat-unfused")
    clap_model     = ClapModel.from_pretrained("laion/clap-htsat-unfused")
    clap_model.eval()
    print("CLAP 완료", flush=True)

    # Claude API
    global LLM_MODEL
    api_key = _clean_api_key(os.environ.get("ANTHROPIC_API_KEY", ""))
    env_file = os.path.join(BASE_DIR, ".env")
    if api_key:
        client = anthropic.Anthropic(api_key=api_key)
        working = _pick_working_llm_model(client, LLM_MODEL)
        if working:
            anthropic_client = client
            LLM_MODEL = working
            print(f"Claude API 연결 완료 (분류 모델={LLM_MODEL})", flush=True)
        else:
            anthropic_client = None
            print(
                "경고: Claude API 키는 있으나 사용 가능한 모델이 없거나 인증 실패\n"
                "  → 분류가 규칙 기반(fallback)으로 동작. 위의 모델 오류 메시지와\n"
                f"  {env_file} 의 ANTHROPIC_API_KEY 값을 확인하세요.",
                flush=True,
            )
    else:
        print(
            "경고: ANTHROPIC_API_KEY 없음/미입력 → 분류가 규칙 기반(fallback)으로 동작\n"
            f"  해결: {env_file} 파일의 'ANTHROPIC_API_KEY=' 뒤에 실제 키를 붙여넣고 서버 재시작\n"
            "  (개=강아지 같은 분류는 이 키가 있어야 LLM으로 정확히 처리됩니다)",
            flush=True,
        )

    # OpenAI API (STT 전용)
    global openai_client
    openai_key = _clean_api_key(os.environ.get("OPENAI_API_KEY", ""))
    if openai_key:
        try:
            from openai import OpenAI
            openai_client = OpenAI(api_key=openai_key)
            print(f"OpenAI STT 연결 완료 (model={STT_MODEL})", flush=True)
        except Exception as e:
            print(f"경고: OpenAI 클라이언트 초기화 실패 ({e}) → STT 비활성화", flush=True)
    else:
        env_file = os.path.join(BASE_DIR, ".env")
        print(
            "경고: OPENAI_API_KEY 없음 → Speech 탭 STT 비활성화\n"
            f"  해결: {env_file} 파일에 OPENAI_API_KEY=sk-... 추가\n"
            f"  또는 서버 실행 전 환경변수로 설정 (set OPENAI_API_KEY=sk-...)",
            flush=True,
        )

    load_prompts()
    _migrate_prompt_embeddings()  # 잘못된 shape 임베딩 자동 재생성

    # ── 최종 상태 배너 (LLM 사용 여부를 한눈에) ────────────────────
    print("=" * 60, flush=True)
    if anthropic_client:
        print(f"[분류] LLM 활성화  → {LLM_MODEL}", flush=True)
    else:
        print("[분류] LLM 비활성화 → 규칙 기반(fallback) 사용 중 (개/강아지 등 부정확)", flush=True)
    print(f"[STT ] {'활성화 → ' + STT_MODEL if openai_client else '비활성화'}", flush=True)
    print("상태 확인: 브라우저로 http://localhost:8000/ 접속 → models.llm 값 확인", flush=True)
    print("=" * 60, flush=True)
    print("서버 준비 완료", flush=True)


startup()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
