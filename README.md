# PromptEar

청각장애인용 소리 감지 · 진동 알림 + 음성→텍스트(STT) Flutter 앱.

- **앱(Flutter)**: 마이크로 주변 소리를 1초 단위로 서버에 보내 분석 → 등록한 소리·긴급 소리 감지 시 진동/알림. Speech 탭에서 음성→텍스트.
- **서버(Python/FastAPI)**: YAMNet(소리 분류) + CLAP(유사도) + Claude(분류) + OpenAI(STT).

대상 플랫폼: **Android / iOS** (데스크톱·웹은 제거됨).

---

## 1. 서버 실행 (PC)

```bash
cd server
python -m venv venv
venv\Scripts\activate          # Windows
# source venv/bin/activate     # macOS/Linux
pip install -r requirements.txt
```

`server/.env` 파일에 API 키 입력(따옴표 없이):

```
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
```

```bash
python promptear_server.py
```

시작 로그에 `[분류] LLM 활성화 → ...`, `[STT ] 활성화 → ...` 가 뜨면 정상.
브라우저로 `http://localhost:8000/` 접속 시 `"llm"` 값으로 상태 확인 가능.

> 주의: `tensorflow` 때문에 Python 3.9~3.11 권장.

## 2. 앱 실행 (Android / iOS)

PC와 휴대폰이 **같은 Wi-Fi**에 연결돼야 합니다.

```bash
flutter pub get
flutter run
```

앱의 **맞춤 설정 → 서버 주소**에 PC의 IP를 입력 (`http://192.168.x.x:8000`).

### iOS 추가 절차 (Mac + Xcode)

iOS는 **CocoaPods**로 빌드합니다(Swift Package Manager 비활성).

```bash
flutter config --no-enable-swift-package-manager
cd ios
pod install
cd ..
flutter run
```

- 최소 iOS 버전: **14.0** (Google Maps SDK 요구).
- 권한(마이크·위치·로컬 네트워크) 설명은 `ios/Runner/Info.plist`에 포함됨.
- 지도용 Google Maps 키는 `ios/Runner/AppDelegate.swift`에 설정됨.
- Bundle ID: `com.kwon.promptear` (Firebase `GoogleService-Info.plist`와 일치).
  본인 Firebase 프로젝트를 쓰려면 해당 Bundle ID로 받은 `GoogleService-Info.plist`로 교체하세요.
