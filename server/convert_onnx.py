import os
os.environ['KMP_DUPLICATE_LIB_OK'] = 'TRUE'

import torch
import numpy as np
from transformers import ClapModel, ClapProcessor

print("모델 로딩...")
model = ClapModel.from_pretrained("laion/clap-htsat-unfused")
processor = ClapProcessor.from_pretrained("laion/clap-htsat-unfused")
model.eval()

# 오디오 인코더만 따로 추출
class ClapAudioEncoder(torch.nn.Module):
    def __init__(self, clap_model):
        super().__init__()
        self.audio_model = clap_model.audio_model
        self.audio_projection = clap_model.audio_projection

    def forward(self, input_features, is_longer=None):
        if is_longer is None:
            is_longer = torch.zeros(input_features.shape[0], dtype=torch.bool)
        outputs = self.audio_model(
            input_features=input_features,
            is_longer=is_longer
        )
        pooled = outputs.pooler_output
        return self.audio_projection(pooled)

audio_encoder = ClapAudioEncoder(model)
audio_encoder.eval()

# 더미 입력으로 ONNX 변환
dummy_audio = np.random.randn(48000).astype(np.float32)
inputs = processor(
    audio=[dummy_audio],
    return_tensors="pt",
    sampling_rate=48000
)

print("ONNX 변환 중...")
with torch.no_grad():
    torch.onnx.export(
        audio_encoder,
        (inputs["input_features"], torch.zeros(1, dtype=torch.bool)),
        "clap_audio_encoder.onnx",
        input_names=["input_features", "is_longer"],
        output_names=["audio_embedding"],
        dynamic_axes={
            "input_features": {0: "batch"},
            "is_longer": {0: "batch"},
        },
        opset_version=14,
    )

print("완료! clap_audio_encoder.onnx 파일 생성됨")