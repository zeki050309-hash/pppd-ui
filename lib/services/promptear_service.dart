import 'dart:async';
import 'dart:convert';
import 'dart:math' as math;
import 'dart:typed_data';
import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:record/record.dart';
import 'package:http/http.dart' as http;
import 'package:vibration/vibration.dart';
import 'package:shared_preferences/shared_preferences.dart';

// ── 알림 모델 ────────────────────────────────────────────────────
enum AlertPriority { urgent, normal, weak }

class SoundAlert {
  final String label;
  final String source;
  final String category;
  final double confidence;
  final double pAlert;
  final AlertPriority priority;
  final DateTime timestamp;
  final String emoji;

  SoundAlert({
    required this.label,
    required this.source,
    required this.category,
    required this.confidence,
    required this.pAlert,
    required this.priority,
    required this.timestamp,
    required this.emoji,
  });
}

// ── PromptEarService ─────────────────────────────────────────────
class PromptEarService extends ChangeNotifier with WidgetsBindingObserver {
  // ── 설정 ────────────────────────────────────────────────────────
  static const int _sampleRate  = 16000;
  static const int _chunkMs     = 1000;   // 서버로 보내는 청크 길이 (1초)
  static const int _maxAlerts   = 50;
  // 같은 카테고리 소리는 이 시간(ms) 안에 재진동하지 않음
  static const int _cooldownMs  = 10000;

  // ── 공개 상태 ────────────────────────────────────────────────────
  bool   isListening     = false;
  double currentDb       = 0.0;
  bool   serverConnected = false;
  String? currentContext;

  double _dbThreshold = 40.0;
  double get dbThreshold => _dbThreshold;
  set dbThreshold(double v) {
    _dbThreshold = v.clamp(20.0, 80.0);
    notifyListeners();
  }

  String _serverUrl = 'http://192.168.0.1:8000';
  String get serverUrl => _serverUrl;
  set serverUrl(String v) { _serverUrl = v; }

  List<SoundAlert> alerts = [];

  // ── 내부 ─────────────────────────────────────────────────────────
  final AudioRecorder _recorder  = AudioRecorder();
  StreamSubscription<Uint8List>? _audioStreamSub;
  StreamSubscription<Amplitude>? _ampSub;
  Timer?    _chunkTimer;

  // PCM16 샘플 누적 버퍼 (float -1~1)
  final List<double> _audioBuffer = [];

  // 진동 cooldown (category → 마지막 진동 시각)
  final Map<String, DateTime> _lastVibrated = {};

  // ── 초기화 ───────────────────────────────────────────────────────
  PromptEarService() {
    WidgetsBinding.instance.addObserver(this);
    _loadPrefs();
    _checkServer();
  }

  Future<void> _loadPrefs() async {
    final prefs = await SharedPreferences.getInstance();
    _dbThreshold = (prefs.getDouble('db_threshold') ?? 40.0).clamp(20.0, 80.0);
    _serverUrl   = prefs.getString('server_url') ?? 'http://192.168.0.1:8000';
    notifyListeners();
  }

  Future<void> savePrefs() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setDouble('db_threshold', dbThreshold);
    await prefs.setString('server_url',   serverUrl);
  }

  // ── 앱 생명주기: 백그라운드 전환 시 녹음 중지 ────────────────────
  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused ||
        state == AppLifecycleState.detached) {
      if (isListening) stopListening();
    }
  }

  // ── 서버 헬스 체크 ───────────────────────────────────────────────
  Future<void> _checkServer() async {
    try {
      final res = await http
          .get(Uri.parse(serverUrl))
          .timeout(const Duration(seconds: 3));
      serverConnected = res.statusCode == 200;
    } catch (_) {
      serverConnected = false;
    }
    notifyListeners();
  }

  Future<void> checkServer() => _checkServer();

  // ── 녹음 시작 ────────────────────────────────────────────────────
  Future<void> startListening() async {
    if (isListening) return;

    // 웹에서는 오디오 기능이 제한적 — 서버 통신만 시뮬레이션
    if (kIsWeb) {
      isListening = true;
      notifyListeners();
      return;
    }

    final hasPermission = await _recorder.hasPermission();
    if (!hasPermission) return;

    // startStream()이 Stream<Uint8List>를 반환 — 반드시 구독해야 버퍼에 쌓임
    final audioStream = await _recorder.startStream(
      const RecordConfig(
        encoder:     AudioEncoder.pcm16bits,
        sampleRate:  _sampleRate,
        numChannels: 1,
      ),
    );

    _audioBuffer.clear();

    // ── PCM16 바이트 → float 샘플로 변환하여 버퍼에 누적 ─────────
    _audioStreamSub = audioStream.listen((Uint8List bytes) {
      for (int i = 0; i + 1 < bytes.length; i += 2) {
        // little-endian int16
        final raw = bytes[i] | (bytes[i + 1] << 8);
        final signed = raw > 32767 ? raw - 65536 : raw;
        _audioBuffer.add(signed / 32768.0);
      }
    });

    // ── amplitude 구독 → dB 실시간 표시 ─────────────────────────
    _ampSub = _recorder
        .onAmplitudeChanged(const Duration(milliseconds: 100))
        .listen((amp) {
      // amp.current 는 dBFS (-∞ ~ 0). 청각적 dB로 변환 (0~120 범위 근사)
      final dbfs   = amp.current.isInfinite ? -90.0 : amp.current;
      currentDb    = (dbfs + 90.0).clamp(0.0, 120.0);
      notifyListeners();
    });

    // ── 1초 주기 청크 처리 타이머 ──────────────────────────────────
    _chunkTimer = Timer.periodic(
      const Duration(milliseconds: _chunkMs),
      (_) => _processChunk(),
    );

    isListening = true;
    notifyListeners();
  }

  // ── 녹음 중지 ────────────────────────────────────────────────────
  Future<void> stopListening() async {
    _chunkTimer?.cancel();
    _chunkTimer = null;
    await _audioStreamSub?.cancel();
    _audioStreamSub = null;
    _ampSub?.cancel();
    _ampSub = null;
    if (!kIsWeb) await _recorder.stop();
    _audioBuffer.clear();
    isListening = false;
    currentDb   = 0.0;
    notifyListeners();
  }

  // ── 청크 처리 ────────────────────────────────────────────────────
  Future<void> _processChunk() async {
    // dB가 임계값 미만이거나 버퍼/서버 없으면 스킵
    if (currentDb < dbThreshold)  return;
    if (!serverConnected)          return;
    if (_audioBuffer.length < 100) return; // 100샘플 미만이면 너무 짧음

    // 버퍼 복사 후 비우기 (다음 청크 동안 계속 쌓임)
    final samples = List<double>.from(_audioBuffer);
    _audioBuffer.clear();

    try {
      final result = await _analyzeOnServer(samples, currentContext);
      if (result != null) _handleResult(result);
    } catch (e) {
      debugPrint('[PromptEar] 서버 오류: $e');
      serverConnected = false;
      notifyListeners();
    }
  }

  // ── 서버 /analyze 호출 ───────────────────────────────────────────
  Future<Map<String, dynamic>?> _analyzeOnServer(
    List<double> audio,
    String?      context,
  ) async {
    final body = jsonEncode({
      'audio':       audio,
      'sample_rate': _sampleRate,
      if (context != null) 'context': context,
    });

    final res = await http.post(
      Uri.parse('$serverUrl/analyze'),
      headers: {'Content-Type': 'application/json'},
      body:    body,
    ).timeout(const Duration(seconds: 10));

    if (res.statusCode == 200) {
      return jsonDecode(res.body) as Map<String, dynamic>;
    }
    return null;
  }

  // ── 결과 처리 & 진동 ─────────────────────────────────────────────
  void _handleResult(Map<String, dynamic> result) {
    final primary = result['primary'];
    if (primary == null) return;

    final shouldAlert = result['should_alert'] == true;
    final pAlert      = (result['alert_model']?['p_alert'] as num?)?.toDouble() ?? 0.0;
    final priorityStr = primary['priority'] as String? ?? 'weak_candidate';
    final category    = primary['category']  as String? ?? 'unknown';
    final label       = primary['label']     as String? ?? 'Unknown';
    final source      = primary['source']    as String? ?? 'yamnet';
    final confidence  = (primary['confidence'] as num?)?.toDouble() ?? 0.0;

    final priority = priorityStr == 'urgent'
        ? AlertPriority.urgent
        : (shouldAlert ? AlertPriority.normal : AlertPriority.weak);

    final alert = SoundAlert(
      label:      label,
      source:     source,
      category:   category,
      confidence: confidence,
      pAlert:     pAlert,
      priority:   priority,
      timestamp:  DateTime.now(),
      emoji:      _emojiFor(category, label),
    );

    alerts.insert(0, alert);
    if (alerts.length > _maxAlerts) alerts.removeLast();

    if (shouldAlert) _triggerVibration(priority, category);

    notifyListeners();
  }

  // ── 진동 (cooldown + 패턴) ───────────────────────────────────────
  Future<void> _triggerVibration(AlertPriority priority, String category) async {
    // 웹은 진동 미지원
    if (kIsWeb) return;

    final hasVibrator = await Vibration.hasVibrator() ?? false;
    if (!hasVibrator) return;

    // urgent는 cooldown 없이 항상 진동
    if (priority != AlertPriority.urgent) {
      final last = _lastVibrated[category];
      if (last != null &&
          DateTime.now().difference(last).inMilliseconds < _cooldownMs) {
        return;
      }
    }
    _lastVibrated[category] = DateTime.now();

    switch (priority) {
      case AlertPriority.urgent:
        // 3회 짧은 진동 — 즉각적인 위험 신호
        await Vibration.vibrate(
          pattern:    [0, 300, 150, 300, 150, 300],
          intensities:[0, 255,   0, 255,   0, 255],
        );
      case AlertPriority.normal:
        // 1회 중간 진동
        await Vibration.vibrate(duration: 200, amplitude: 128);
      case AlertPriority.weak:
        break;
    }
  }

  // ── 프롬프트 등록 / 삭제 / 목록 ─────────────────────────────────
  Future<Map<String, dynamic>> registerPrompt(
    String promptId,
    String description,
  ) async {
    final res = await http.post(
      Uri.parse('$serverUrl/prompt/register'),
      headers: {'Content-Type': 'application/json'},
      body:    jsonEncode({'prompt_id': promptId, 'description': description}),
    ).timeout(const Duration(seconds: 30));
    return jsonDecode(res.body) as Map<String, dynamic>;
  }

  Future<bool> deletePrompt(String promptId) async {
    final res = await http
        .delete(Uri.parse('$serverUrl/prompt/$promptId'))
        .timeout(const Duration(seconds: 5));
    return res.statusCode == 200;
  }

  Future<List<Map<String, dynamic>>> fetchPrompts() async {
    final res = await http
        .get(Uri.parse('$serverUrl/prompts'))
        .timeout(const Duration(seconds: 5));
    final data = jsonDecode(res.body) as Map<String, dynamic>;
    return List<Map<String, dynamic>>.from(data['prompts'] ?? []);
  }

  // ── 알림 목록 초기화 ─────────────────────────────────────────────
  void clearAlerts() {
    alerts.clear();
    notifyListeners();
  }

  // ── 카테고리 → 이모지 ────────────────────────────────────────────
  static String _emojiFor(String category, String label) {
    final l = label.toLowerCase();
    if (l.contains('fire') || l.contains('smoke'))        return '🔥';
    if (l.contains('siren') || l.contains('ambulance'))   return '🚨';
    if (l.contains('gunshot') || l.contains('explosion')) return '💥';
    if (l.contains('scream') || l.contains('cry'))        return '😱';
    if (l.contains('car alarm'))                          return '🚗';
    if (l.contains('doorbell'))                           return '🔔';
    if (l.contains('knock'))                              return '🚪';
    if (l.contains('baby'))                               return '👶';
    switch (category) {
      case 'animal':    return '🐾';
      case 'music':     return '🎵';
      case 'vehicle':   return '🚌';
      case 'nature':    return '🌿';
      case 'speech':    return '💬';
      case 'machinery': return '⚙️';
      case 'weapon':    return '⚠️';
      default:          return '🔊';
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _chunkTimer?.cancel();
    _audioStreamSub?.cancel();
    _ampSub?.cancel();
    _recorder.dispose();
    super.dispose();
  }
}
