import 'package:flutter/foundation.dart';
import 'package:flutter_local_notifications/flutter_local_notifications.dart';

/// 로컬 알림 서비스.
///
/// 소리 감지 알림(진동)이 발생할 때 동시에 로컬 알림을 띄운다.
/// iOS: Apple Watch가 알림을 자동으로 미러링 → Watch에서도 진동.
/// Android: Wear OS / Galaxy Watch 등이 알림을 자동으로 미러링.
class NotificationService {
  NotificationService._();
  static final NotificationService instance = NotificationService._();

  final FlutterLocalNotificationsPlugin _plugin =
      FlutterLocalNotificationsPlugin();

  bool _initialized = false;

  static const String _channelId   = 'promptear_alerts';
  static const String _channelName = 'PromptEar 소리 알림';
  static const String _channelDesc = '감지된 소리 알림 — Apple Watch / Wear OS로 자동 미러링됩니다.';

  Future<void> initialize() async {
    if (_initialized || kIsWeb) return;

    const androidSettings =
        AndroidInitializationSettings('@mipmap/ic_launcher');
    const iosSettings = DarwinInitializationSettings(
      requestAlertPermission: true,
      requestBadgePermission: false,
      // 청각장애인 앱이므로 알림 소리는 끔
      requestSoundPermission: false,
    );

    await _plugin.initialize(
      const InitializationSettings(
        android: androidSettings,
        iOS: iosSettings,
      ),
    );

    // Android 알림 채널 생성 (API 26+)
    final androidPlugin =
        _plugin.resolvePlatformSpecificImplementation<
            AndroidFlutterLocalNotificationsPlugin>();
    if (androidPlugin != null) {
      await androidPlugin.createNotificationChannel(
        const AndroidNotificationChannel(
          _channelId,
          _channelName,
          description: _channelDesc,
          importance: Importance.high,
          // 소리 없이 진동만 — Watch는 자체 햅틱을 씀
          playSound: false,
          enableVibration: false,
        ),
      );
      // Android 13+ 알림 권한 요청
      await androidPlugin.requestNotificationsPermission();
    }

    // iOS 알림 권한 요청
    final iosPlugin =
        _plugin.resolvePlatformSpecificImplementation<
            IOSFlutterLocalNotificationsPlugin>();
    await iosPlugin?.requestPermissions(
      alert: true,
      badge: false,
      sound: false,
    );

    _initialized = true;
  }

  /// 소리 감지 알림 표시.
  /// [emoji] + [label] 을 제목으로, [category] 를 본문으로 사용.
  /// Apple Watch 는 이 알림을 자동으로 수신해 햅틱을 발생시킨다.
  Future<void> showAlertNotification({
    required String label,
    required String emoji,
    required String category,
    bool isUrgent = false,
  }) async {
    if (!_initialized || kIsWeb) return;

    final androidDetails = AndroidNotificationDetails(
      _channelId,
      _channelName,
      channelDescription: _channelDesc,
      importance: isUrgent ? Importance.max : Importance.high,
      priority:   isUrgent ? Priority.max  : Priority.high,
      playSound:       false,
      enableVibration: false,
      // 긴급 알림은 상단 팝업(heads-up) 으로 표시
      fullScreenIntent: isUrgent,
    );

    const iosDetails = DarwinNotificationDetails(
      presentAlert: true,
      presentBadge: false,
      presentSound: false,
    );

    await _plugin.show(
      // id: category 해시로 같은 카테고리의 이전 알림 자동 덮어쓰기
      category.hashCode & 0x7FFFFFFF,
      '$emoji $label',
      category,
      NotificationDetails(android: androidDetails, iOS: iosDetails),
    );
  }
}
