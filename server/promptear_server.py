# promptear_server.py
# PromptEar 통합 서버
# - YAMNet 온톨로지 계층 구조 (main.py)
# - CLAP Transformers 텍스트/오디오 인코더 (동료 파일, ONNX/AudioGen 불필요)
# - Claude API: 온톨로지 분류 + U/X prior 추정 단일 호출 (두 파일 통합)
# - Model A+ sigmoid: 최종 알림 확률 계산 (동료 파일)
# - Context 기반 상황별 알림 조정 (동료 파일)

import os

# ───────────────────────────────────────────────────────────────
# 경로 설정 (하드코딩 대신 상대경로)
# ───────────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

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
import time
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

# CLAP 판단 임계치
CLAP_SINGLE_MIN      = 0.18   # 후보 1개일 때 최소 유사도
CLAP_MULTI_MIN       = 0.12   # 후보 여러 개일 때 최소 유사도
CLAP_MARGIN_MIN      = 0.03   # CLAP 1위-2위 최솟값
CLAP_OVERRIDE_GAP    = 0.05   # CLAP이 YAMNet 오버라이드에 필요한 추가 마진

# Model A+
ALERT_THRESHOLD      = 0.37   # P(Alert) 이상이면 알림

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
# Model A+  (동료 파일)
# P(Alert) = sigmoid(w0 + w1*C + w2*U + w3*S + w4*X + w5*L
#                       + w6*C*S + w7*U*X + w8*C*U)
# threshold = 0.37
# ───────────────────────────────────────────────────────────────
def calculate_alert_probability(
    C: float, U: float, S: float, X: float, L: float
) -> dict[str, Any]:
    C, U, S, X, L = map(clamp01, [C, U, S, X, L])
    CS, UX, CU = C * S, U * X, C * U

    z = (
        2.1888
        - 0.1367 * C
        - 0.3747 * U
        - 0.3124 * S
        + 2.0300 * X
        + 1.2330 * L
        + 0.1701 * CS
        + 0.4520 * UX
        + 1.0777 * CU
    )
    p = sigmoid(z)

    return {
        "C": round(C, 4), "U": round(U, 4), "S": round(S, 4),
        "X": round(X, 4), "L": round(L, 4),
        "CS": round(CS, 4), "UX": round(UX, 4), "CU": round(CU, 4),
        "z": round(z, 4), "p_alert": round(p, 4),
        "threshold": ALERT_THRESHOLD,
        "should_alert": bool(p >= ALERT_THRESHOLD),
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
def get_clap_audio_embedding(audio_48k: np.ndarray) -> np.ndarray:
    """Transformers ClapModel 오디오 인코더로 임베딩 추출"""
    inputs = clap_processor(
        audios=[audio_48k], return_tensors="pt", sampling_rate=48000
    )
    with torch.no_grad():
        # **inputs 대신 명시적 키 전달 — 버전별 API 차이 방지
        feat = clap_model.get_audio_features(
            input_features=inputs.get("input_features"),
            is_longer=inputs.get("is_longer"),
        )
    emb = feat[0].cpu().numpy().astype(np.float32)
    return emb / (np.linalg.norm(emb) + 1e-9)


def get_clap_text_embedding(text: str) -> np.ndarray:
    """CLAP 텍스트 인코더로 텍스트 임베딩 추출"""
    inputs = clap_processor(text=[text], return_tensors="pt", padding=True)
    with torch.no_grad():
        # **inputs 대신 명시적 키 전달 — 버전별 API 차이 방지
        feat = clap_model.get_text_features(
            input_ids=inputs.get("input_ids"),
            attention_mask=inputs.get("attention_mask"),
        )
    emb = feat[0].cpu().numpy().astype(np.float32)
    return emb / (np.linalg.norm(emb) + 1e-9)


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
) -> list[dict[str, Any]]:
    """
    새 프롬프트가 기존 등록 프롬프트와 유사한지 CLAP 임베딩으로 비교.
    유사도 >= threshold이면 해당 항목 리스트 반환.
    """
    duplicates = []
    for pid, data in prompt_store.items():
        emb = data.get("embedding")
        if not emb:
            continue
        try:
            ref = np.array(emb, dtype=np.float32).flatten()  # 혹시 2D면 1D로
            if ref.shape != new_emb.shape:
                continue  # 차원 불일치 시 스킵
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
    # 동물
    "dog": ("Dog", 69), "개": ("Dog", 69),
    "bark": ("Bark", 70), "짖": ("Bark", 70),
    "cat": ("Cat", 76), "고양이": ("Cat", 76),
    "meow": ("Meow", 78), "야옹": ("Meow", 78),
    "bird": ("Bird", 106), "새": ("Bird", 106),
    "chirp": ("Chirp, tweet", 108), "짹": ("Chirp, tweet", 108),
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

    return {
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
    animal_subs = "dog, cat, livestock, wild_large, bird, canidae, rodent, insect, amphibian, reptile, marine"
    contexts_str = json.dumps(contexts, ensure_ascii=False)

    prompt = f"""당신은 PromptEar(청각장애인용 소리 감지 앱)의 오디오 분류 및 알림 우선순위 전문가입니다.
사용자가 등록한 소리 설명을 분석하여 아래 JSON만 반환하세요.

=== 카테고리 ===
{categories_desc}

=== YAMNet 주요 클래스 예시 (총 521개) ===
Animal(67), Dog(69), Bark(70), Cat(76), Meow(78), Horse(82), Bird(106),
Cricket(122), Frog(127), Whale vocalization(131), Car alarm(304),
Fire alarm(394), Gunshot(421), Doorbell(349), Knock(353) 등

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
            model="claude-haiku-4-5-20251001",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}]
        )
        raw = message.content[0].text.strip()
        start, end = raw.find("{"), raw.rfind("}") + 1
        data = json.loads(raw[start:end])

        # 값 보정
        data["alert_prior_u"] = round(clamp01(float(data.get("alert_prior_u", 0.5))), 4)
        raw_x = data.get("context_alert_prior") or {}
        u_val = data["alert_prior_u"]
        data["context_alert_prior"] = {
            ctx: round(clamp01(float(raw_x.get(ctx, u_val))), 4)
            for ctx in contexts
        }
        data["source"] = "claude-haiku"
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
        ref = np.array(d["embedding"], dtype=np.float32)
        ref = ref / (np.linalg.norm(ref) + 1e-9)
        scores[pid] = float(np.dot(audio_emb, ref))

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
            "llm":       "claude-haiku" if anthropic_client else "fallback",
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

    # 3. 기존 프롬프트와 유사도 비교 (중복 감지)
    duplicates = check_duplicate_prompts(req.description, text_emb, threshold=0.88)
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
    새 알림 로직:
      진동(should_alert=True) 조건은 딱 두 가지만
        1. 등록 프롬프트 매칭 (enabled=True인 것)
           - covered_by_yamnet=True  → YAMNet top-k에 해당 클래스가 있으면 즉시
           - covered_by_yamnet=False → 모호할 때 CLAP 서브트리 비교로 매칭 시
        2. 긴급 소리 (URGENT_LABELS) — 항상
      그 외 모든 소리는 로그만 남기고 진동 없음.
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
    should_alert = False
    alert_reason = "no_match"

    # ── 2단계: 긴급 소리 감지 ──────────────────────────────────────
    if yamnet_result["is_urgent"] and top_conf > URGENT_CONF_THRESH:
        should_alert = True
        alert_reason = "urgent"

    # ── 3단계: YAMNet 클래스로 커버되는 등록 프롬프트 매칭 ─────────
    if not should_alert:
        # top-5에서 등록된 YAMNet 클래스 룩업
        yamnet_class_map = get_enabled_yamnet_classes()   # {class_idx: prompt_id}
        for entry in yamnet_result.get("top5", []):
            idx = YAMNET_LABEL_TO_IDX.get(entry["label"], -1)
            if idx in yamnet_class_map and entry["score"] > URGENT_CONF_THRESH:
                matched_pid  = yamnet_class_map[idx]
                should_alert = True
                alert_reason = f"yamnet_class_match:{entry['label']}"
                break

    # ── 4단계: CLAP 서브트리 비교 (미등록/미커버 프롬프트) ──────────
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
                should_alert = True
                alert_reason = "clap_match"

    # ── 5단계: 대표 라벨 선택 ──────────────────────────────────────
    primary = choose_primary_sound(yamnet_result, clap_result)
    if matched_pid and matched_pid in prompt_store:
        primary["prompt_id"] = matched_pid

    # ── 6단계: Model A+ (참고용 — 알림 여부는 위에서 이미 결정) ──────
    U, u_info = get_sound_alert_prior(primary["label"], primary.get("prompt_id"))
    X, x_info = get_context_alert_prior(
        primary["label"], req.context, primary.get("prompt_id"), fallback_u=U
    )
    alert_model = calculate_alert_probability(
        C=top_conf, U=U, S=S, X=X, L=L
    )
    # 최종 should_alert는 위의 명시적 로직이 우선
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
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if api_key:
        anthropic_client = anthropic.Anthropic(api_key=api_key)
        print("Claude API 연결 완료 (온톨로지 분류 + prior 추정 활성화)", flush=True)
    else:
        print("경고: ANTHROPIC_API_KEY 없음 → 키워드/규칙 기반 폴백 사용", flush=True)

    load_prompts()
    print("서버 준비 완료", flush=True)


startup()

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=False)
