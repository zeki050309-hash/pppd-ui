import os
os.environ['TFHUB_CACHE_DIR'] = 'C:/tfhub_cache'
os.environ['TMP'] = 'C:/tmp'
os.environ['TEMP'] = 'C:/tmp'
os.environ['TF_ENABLE_ONEDNN_OPTS'] = '0'

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np
import torch
import tensorflow as tf
import tensorflow_hub as hub
from transformers import ClapModel, ClapProcessor
from scipy import signal
import uvicorn
import json
import os
import requests

def text_to_audio_sample(description: str) -> np.ndarray:
    response = requests.post(
        "https://api.elevenlabs.io/v1/sound-generation",
        headers={"xi-api-key": "YOUR_API_KEY"},
        json={
            "text": description,
            "duration_seconds": 3.0,
        }
    )
    # 반환된 오디오를 numpy 배열로 변환
    audio_bytes = response.content
    # ... wav 디코딩
    return audio_array

app = FastAPI(title="PromptEar Server")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

print("=" * 50)
print("PromptEar 서버 시작")
print("=" * 50)

print("YAMNet 모델 로딩 중...")
yamnet_model = hub.load('C:/tfhub_cache/google_yamnet_1')

class_map_path = yamnet_model.class_map_path().numpy().decode('utf-8')
yamnet_labels = []
with tf.io.gfile.GFile(class_map_path) as f:
    next(f)
    for line in f:
        yamnet_labels.append(line.strip().split(',')[2])
print(f"YAMNet 로딩 완료 (클래스 {len(yamnet_labels)}개)")

print("CLAP 모델 로딩 중... (첫 실행은 2~3분)")
clap_model = ClapModel.from_pretrained("laion/clap-htsat-unfused")
clap_processor = ClapProcessor.from_pretrained("laion/clap-htsat-unfused")
clap_model.eval()
print("CLAP 로딩 완료")

URGENT_LABELS = {
    "Car alarm", "Vehicle horn, car horn, honking, honk",
    "Ambulance (siren)", "Fire alarm", "Smoke detector, smoke alarm",
    "Civil defense siren", "Screaming", "Glass break, glass breaking",
    "Gunshot, gunfire", "Siren", "Emergency vehicle"
}

PROMPTS_FILE = "prompts.json"
prompt_store = {}

def save_prompts():
    serializable = {
        pid: {
            "description": data["description"],
            "embedding": data["embedding"]
        }
        for pid, data in prompt_store.items()
    }
    with open(PROMPTS_FILE, 'w', encoding='utf-8') as f:
        json.dump(serializable, f, ensure_ascii=False)

def load_prompts():
    global prompt_store
    if os.path.exists(PROMPTS_FILE):
        with open(PROMPTS_FILE, 'r', encoding='utf-8') as f:
            prompt_store = json.load(f)
        print(f"저장된 프롬프트 {len(prompt_store)}개 불러옴")

load_prompts()


class PromptRegisterRequest(BaseModel):
    prompt_id: str
    description: str


class AudioAnalyzeRequest(BaseModel):
    audio: list[float]
    sample_rate: int = 16000


def resample_audio(audio: np.ndarray, orig_sr: int, target_sr: int) -> np.ndarray:
    if orig_sr == target_sr:
        return audio
    num_samples = int(len(audio) * target_sr / orig_sr)
    return signal.resample(audio, num_samples).astype(np.float32)


def run_yamnet(audio_16k: np.ndarray) -> dict:
    waveform = tf.constant(audio_16k, dtype=tf.float32)
    scores, _, _ = yamnet_model(waveform)
    mean_scores = tf.reduce_mean(scores, axis=0).numpy()

    top_idx = int(np.argmax(mean_scores))
    top_score = float(mean_scores[top_idx])
    top_label = yamnet_labels[top_idx]

    top5_indices = np.argsort(mean_scores)[-5:][::-1]
    top5 = [
        {"label": yamnet_labels[int(i)], "score": float(mean_scores[int(i)])}
        for i in top5_indices
    ]

    return {
        "label": top_label,
        "confidence": top_score,
        "is_urgent": top_label in URGENT_LABELS,
        "top5": top5
    }


import onnxruntime as ort

# 서버 시작 시 ONNX 세션 로드 (clap_model 로드 아래에 추가)
print("CLAP ONNX 세션 로딩 중...")
ort_session = ort.InferenceSession(
    "clap_audio_encoder.onnx",
    providers=["CPUExecutionProvider"]
)
print("CLAP ONNX 로딩 완료")

def run_clap(audio_48k: np.ndarray) -> dict | None:
    import time
    if not prompt_store:
        return None

    start = time.time()

    audio_inputs = clap_processor(
        audio=[audio_48k],
        return_tensors="np",
        sampling_rate=48000
    )

    # ONNX 추론 (PyTorch 대비 3~5배 빠름)
    ort_inputs = {
        "input_features": audio_inputs["input_features"].astype(np.float32),
        "is_longer": np.zeros(1, dtype=bool),
    }
    audio_emb_np = ort_session.run(["audio_embedding"], ort_inputs)[0][0]

    print(f"CLAP ONNX 추론 시간: {time.time() - start:.2f}초")

    best_match = None
    best_score = -1.0

    for prompt_id, data in prompt_store.items():
        text_emb_np = np.array(data["embedding"][0])
        score = float(np.dot(audio_emb_np, text_emb_np) / (
            np.linalg.norm(audio_emb_np) * np.linalg.norm(text_emb_np) + 1e-9
        ))
        if score > best_score:
            best_score = score
            best_match = {
                "prompt_id": prompt_id,
                "description": data["description"],
                "similarity": round(score, 4)
            }

    CLAP_THRESHOLD = 0.25
    if best_match and best_score >= CLAP_THRESHOLD:
        return best_match
    if best_match:
        print(f"CLAP 매칭 실패 - 최고 유사도: {best_score:.4f} ({best_match['description']})")
    return None

@app.get("/")
def health():
    return {
        "status": "ok",
        "yamnet": "loaded",
        "clap": "loaded",
        "prompts_count": len(prompt_store)
    }


@app.get("/prompts")
def list_prompts():
    return {
        "prompts": [
            {"prompt_id": pid, "description": data["description"]}
            for pid, data in prompt_store.items()
        ]
    }


@app.post("/prompt/register")
def register_prompt(req: PromptRegisterRequest):
    # 1. 텍스트를 오디오로 변환
    generated_audio = text_to_audio_sample(req.description)
    
    # 2. 생성된 오디오를 CLAP으로 임베딩
    audio_48k = resample_audio(generated_audio, 44100, 48000)
    audio_inputs = clap_processor(
        audio=[audio_48k],
        return_tensors="np",
        sampling_rate=48000
    )
    ort_inputs = {
        "input_features": audio_inputs["input_features"].astype(np.float32),
        "is_longer": np.zeros(1, dtype=bool),
    }
    audio_emb = ort_session.run(["audio_embedding"], ort_inputs)[0][0]
    audio_emb = audio_emb / (np.linalg.norm(audio_emb) + 1e-9)
    
    # 3. 오디오 임베딩 저장 (텍스트 임베딩 대신)
    prompt_store[req.prompt_id] = {
        "description": req.description,
        "embedding": [audio_emb.tolist()]
    }
    save_prompts()
    return {"success": True}


@app.delete("/prompt/{prompt_id}")
def delete_prompt(prompt_id: str):
    if prompt_id in prompt_store:
        del prompt_store[prompt_id]
        save_prompts()
        return {"success": True}
    raise HTTPException(status_code=404, detail="프롬프트를 찾을 수 없습니다")


@app.post("/analyze")
def analyze_audio(req: AudioAnalyzeRequest):
    audio = np.array(req.audio, dtype=np.float32)

    max_val = np.abs(audio).max()
    if max_val > 0:
        audio = audio / max_val

    audio_16k = resample_audio(audio, req.sample_rate, 16000)

    YAMNET_HIGH_CONFIDENCE = 0.7
    YAMNET_LOW_CONFIDENCE  = 0.4

    # 1단계: YAMNet 먼저 실행
    yamnet_result = run_yamnet(audio_16k)

    response = {"yamnet": yamnet_result, "clap": None}

    # 1순위: 긴급 소리 → 즉시 반환 (CLAP 실행 안 함)
    if yamnet_result["is_urgent"] and yamnet_result["confidence"] > 0.3:
        response["primary"] = {
            "label": yamnet_result["label"],
            "confidence": yamnet_result["confidence"],
            "source": "yamnet",
            "priority": "urgent"
        }
        return response

    # 2순위: YAMNet 신뢰도 70% 이상 → 즉시 반환 (CLAP 실행 안 함)
    if yamnet_result["confidence"] >= YAMNET_HIGH_CONFIDENCE:
        response["primary"] = {
            "label": yamnet_result["label"],
            "confidence": yamnet_result["confidence"],
            "source": "yamnet",
            "priority": "normal"
        }
        return response

    # 3단계: YAMNet 신뢰도 낮을 때만 CLAP 실행
    if prompt_store:
        audio_48k = resample_audio(audio, req.sample_rate, 48000)
        clap_result = run_clap(audio_48k)
        response["clap"] = clap_result
    else:
        clap_result = None

    # YAMNet 40~70% 구간
    if yamnet_result["confidence"] >= YAMNET_LOW_CONFIDENCE:
        if clap_result and clap_result["similarity"] > yamnet_result["confidence"]:
            response["primary"] = {
                "label": clap_result["description"],
                "confidence": clap_result["similarity"],
                "source": "clap",
                "priority": "normal"
            }
        else:
            response["primary"] = {
                "label": yamnet_result["label"],
                "confidence": yamnet_result["confidence"],
                "source": "yamnet",
                "priority": "normal"
            }
        return response

    # YAMNet 40% 미만
    if clap_result:
        response["primary"] = {
            "label": clap_result["description"],
            "confidence": clap_result["similarity"],
            "source": "clap",
            "priority": "normal"
        }
    else:
        response["primary"] = None

    return response

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)