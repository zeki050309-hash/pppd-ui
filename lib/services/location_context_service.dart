import 'package:flutter/foundation.dart';
import 'package:geolocator/geolocator.dart';
import 'package:cloud_firestore/cloud_firestore.dart';

// ── Firestore에 저장할 위험 지점 모델 ────────────────────────────
class DangerZone {
  final String id;
  final double lat;
  final double lng;
  final String label;     // 예: "교통사고 빈발 구간"
  final int    count;     // 위험 소리 누적 횟수
  final DateTime lastAt;

  DangerZone({
    required this.id,
    required this.lat,
    required this.lng,
    required this.label,
    required this.count,
    required this.lastAt,
  });

  factory DangerZone.fromFirestore(DocumentSnapshot doc) {
    final d = doc.data() as Map<String, dynamic>;
    final geo = d['location'] as GeoPoint;
    return DangerZone(
      id:     doc.id,
      lat:    geo.latitude,
      lng:    geo.longitude,
      label:  d['label']  as String? ?? '위험 구역',
      count:  (d['count'] as num?)?.toInt() ?? 1,
      lastAt: (d['last_at'] as Timestamp?)?.toDate() ?? DateTime.now(),
    );
  }
}

// ── 위치 → context 매핑 규칙 ─────────────────────────────────────
// 서버의 DEFAULT_CONTEXTS와 맞춰야 함
const _contextLabels = {
  'home':             '집',
  'sleeping':         '수면 중',
  'walking_outside':  '야외 보행',
  'driving':          '운전 중',
  'classroom':        '교실',
  'studying':         '공부 중',
  'office':           '사무실',
  'public_transport': '대중교통',
};

class LocationContextService extends ChangeNotifier {
  Position? currentPosition;
  String    currentContext = 'walking_outside';  // 기본값
  List<DangerZone> dangerZones = [];

  bool _tracking = false;

  // ── 위치 추적 시작 ────────────────────────────────────────────────
  Future<void> startTracking() async {
    if (_tracking) return;

    LocationPermission perm = await Geolocator.checkPermission();
    if (perm == LocationPermission.denied) {
      perm = await Geolocator.requestPermission();
    }
    if (perm == LocationPermission.deniedForever) return;

    _tracking = true;

    Geolocator.getPositionStream(
      locationSettings: const LocationSettings(
        accuracy:         LocationAccuracy.high,
        distanceFilter:   10,
      ),
    ).listen((pos) {
      currentPosition = pos;
      notifyListeners();
    });

    _loadDangerZones();
  }

  // ── context 수동 설정 (map 화면에서 사용자가 선택) ──────────────
  void setContext(String context) {
    if (_contextLabels.containsKey(context)) {
      currentContext = context;
      notifyListeners();
    }
  }

  String get contextLabel => _contextLabels[currentContext] ?? currentContext;

  static Map<String, String> get allContextLabels => _contextLabels;

  // ── Firestore에서 위험 지점 로드 ─────────────────────────────────
  // map_widget.dart가 읽는 'danger_places'와 동일한 컬렉션 사용
  Future<void> _loadDangerZones() async {
    try {
      final snap = await FirebaseFirestore.instance
          .collection('danger_places')
          .orderBy('count', descending: true)
          .limit(50)
          .get();
      dangerZones = snap.docs.map(DangerZone.fromFirestore).toList();
      notifyListeners();
    } catch (e) {
      debugPrint('DangerZones load error: $e');
    }
  }

  Future<void> refreshDangerZones() => _loadDangerZones();

  // ── 위험 알림 발생 시 Firestore에 기록 ──────────────────────────
  // 반경 50m 이내에 기존 지점이 있으면 count++, 없으면 신규 생성
  Future<void> recordDangerEvent({
    required double lat,
    required double lng,
    required String label,
  }) async {
    if (currentPosition == null) return;

    try {
      final nearby = dangerZones.where((z) {
        final dist = Geolocator.distanceBetween(lat, lng, z.lat, z.lng);
        return dist < 50;
      });

      if (nearby.isNotEmpty) {
        final zone = nearby.first;
        await FirebaseFirestore.instance
            .collection('danger_places')
            .doc(zone.id)
            .update({
          'count':   FieldValue.increment(1),
          'last_at': FieldValue.serverTimestamp(),
        });
      } else {
        await FirebaseFirestore.instance.collection('danger_places').add({
          'location': GeoPoint(lat, lng),
          'label':    label,
          'count':    1,
          'last_at':  FieldValue.serverTimestamp(),
        });
      }

      await _loadDangerZones();
    } catch (e) {
      debugPrint('recordDangerEvent error: $e');
    }
  }
}
