import '/flutter_flow/flutter_flow_util.dart';
import '/index.dart';
import '/shared/pppd_design.dart';
import '/services/promptear_service.dart';
import '/services/location_context_service.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'home_page_model.dart';
export 'home_page_model.dart';

class HomePageWidget extends StatefulWidget {
  const HomePageWidget({super.key});

  static String routeName = 'HomePage';
  static String routePath = '/homePage';

  @override
  State<HomePageWidget> createState() => _HomePageWidgetState();
}

class _HomePageWidgetState extends State<HomePageWidget> {
  late HomePageModel _model;
  final scaffoldKey = GlobalKey<ScaffoldState>();

  @override
  void initState() {
    super.initState();
    _model = createModel(context, () => HomePageModel());
    WidgetsBinding.instance.addPostFrameCallback((_) {
      // 서버 연결 확인
      context.read<PromptEarService>().checkServer();
      // 위치 추적 시작
      context.read<LocationContextService>().startTracking();
    });
  }

  @override
  void dispose() {
    _model.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final svc  = context.watch<PromptEarService>();
    final latest = svc.alerts.isNotEmpty ? svc.alerts.first : null;

    return GestureDetector(
      onTap: () {
        FocusScope.of(context).unfocus();
        FocusManager.instance.primaryFocus?.unfocus();
      },
      child: Scaffold(
        key: scaffoldKey,
        backgroundColor: PppdColors.lavender,
        body: SafeArea(
          child: Container(
            decoration: const BoxDecoration(
              gradient: LinearGradient(
                begin: Alignment.topLeft,
                end: Alignment.bottomRight,
                colors: [Color(0xFFFCFAFF), Color(0xFFF1ECFF)],
              ),
            ),
            child: SingleChildScrollView(
              padding: const EdgeInsets.fromLTRB(20, 22, 20, 28),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  // ── 헤더 ──────────────────────────────────────────
                  Row(
                    children: [
                      Container(
                        width: 54, height: 54,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(20),
                          gradient: const LinearGradient(
                            colors: [Color(0xFF7B61FF), Color(0xFFB59CFF)],
                          ),
                        ),
                        child: Padding(
                          padding: const EdgeInsets.all(10),
                          child: Image.asset('assets/images/pppd_butterfly.png'),
                        ),
                      ),
                      const SizedBox(width: 14),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text('PromptEar', style: pppdText(size: 28, weight: FontWeight.w900)),
                            Text('소리와 위치를 더 직관적으로', style: pppdText(size: 13, color: PppdColors.muted)),
                          ],
                        ),
                      ),
                      // 서버 연결 상태 표시
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                        decoration: BoxDecoration(
                          color: svc.serverConnected ? PppdColors.safe.withOpacity(0.15) : PppdColors.danger.withOpacity(0.12),
                          borderRadius: BorderRadius.circular(20),
                        ),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Icon(
                              svc.serverConnected ? Icons.wifi_rounded : Icons.wifi_off_rounded,
                              size: 14,
                              color: svc.serverConnected ? PppdColors.safe : PppdColors.danger,
                            ),
                            const SizedBox(width: 4),
                            Text(
                              svc.serverConnected ? '서버 연결됨' : '서버 없음',
                              style: pppdText(
                                size: 11,
                                color: svc.serverConnected ? PppdColors.safe : PppdColors.danger,
                                weight: FontWeight.w600,
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 20),

                  // ── 소리 감지 카드 ─────────────────────────────────
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(30),
                      gradient: LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: svc.isListening
                            ? [const Color(0xFF3CCB8E), const Color(0xFF2BA874)]
                            : [const Color(0xFF6C4DFF), const Color(0xFF9E7BFF)],
                      ),
                      boxShadow: [
                        BoxShadow(
                          color: (svc.isListening ? PppdColors.safe : const Color(0xFF7B61FF)).withOpacity(0.35),
                          blurRadius: 28, offset: const Offset(0, 16),
                        ),
                      ],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(
                              child: Column(
                                crossAxisAlignment: CrossAxisAlignment.start,
                                children: [
                                  Text(
                                    svc.isListening ? '소리 감지 중…' : '소리 감지 준비됨',
                                    style: pppdText(size: 22, weight: FontWeight.w900, color: Colors.white, height: 1.2),
                                  ),
                                  const SizedBox(height: 6),
                                  Text(
                                    svc.isListening
                                        ? '현재 dB: ${svc.currentDb.toStringAsFixed(1)} dB'
                                        : '버튼을 눌러 감지를 시작하세요',
                                    style: pppdText(size: 13, color: Colors.white70, height: 1.4),
                                  ),
                                ],
                              ),
                            ),
                            // Start / Stop 버튼
                            GestureDetector(
                              onTap: svc.serverConnected
                                  ? () async {
                                      if (svc.isListening) {
                                        await svc.stopListening();
                                      } else {
                                        await svc.startListening();
                                      }
                                    }
                                  : () => ScaffoldMessenger.of(context).showSnackBar(
                                        const SnackBar(content: Text('서버에 연결되지 않았습니다. 설정에서 서버 IP를 확인해 주세요.')),
                                      ),
                              child: Container(
                                width: 64, height: 64,
                                decoration: BoxDecoration(
                                  color: Colors.white,
                                  shape: BoxShape.circle,
                                  boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.1), blurRadius: 8)],
                                ),
                                child: Icon(
                                  svc.isListening ? Icons.stop_rounded : Icons.mic_rounded,
                                  size: 32,
                                  color: svc.isListening ? PppdColors.safe : PppdColors.purple,
                                ),
                              ),
                            ),
                          ],
                        ),

                        // dB 프로그레스 바
                        if (svc.isListening) ...[
                          const SizedBox(height: 16),
                          Row(
                            children: [
                              const Icon(Icons.volume_up_rounded, size: 16, color: Colors.white70),
                              const SizedBox(width: 8),
                              Expanded(
                                child: ClipRRect(
                                  borderRadius: BorderRadius.circular(4),
                                  child: LinearProgressIndicator(
                                    value: (svc.currentDb / 100).clamp(0.0, 1.0),
                                    backgroundColor: Colors.white24,
                                    valueColor: AlwaysStoppedAnimation<Color>(
                                      svc.currentDb >= svc.dbThreshold ? Colors.white : Colors.white54,
                                    ),
                                    minHeight: 8,
                                  ),
                                ),
                              ),
                              const SizedBox(width: 8),
                              Text(
                                '${svc.dbThreshold.toInt()} dB',
                                style: pppdText(size: 11, color: Colors.white60),
                              ),
                            ],
                          ),
                        ],

                        // ── Auto-STT 토글 ──────────────────────────────
                        const SizedBox(height: 14),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                          decoration: BoxDecoration(
                            color: Colors.white.withOpacity(0.15),
                            borderRadius: BorderRadius.circular(14),
                          ),
                          child: Row(
                            children: [
                              const Icon(Icons.record_voice_over_rounded,
                                  size: 16, color: Colors.white),
                              const SizedBox(width: 8),
                              Expanded(
                                child: Text(
                                  '자동 STT',
                                  style: pppdText(size: 13, color: Colors.white,
                                      weight: FontWeight.w700),
                                ),
                              ),
                              Text(
                                svc.autoSttEnabled ? '켜짐' : '꺼짐',
                                style: pppdText(size: 11, color: Colors.white70),
                              ),
                              const SizedBox(width: 6),
                              Transform.scale(
                                scale: 0.8,
                                child: Switch(
                                  value: svc.autoSttEnabled,
                                  onChanged: svc.serverConnected
                                      ? (v) => svc.setAutoStt(v)
                                      : null,
                                  activeColor: Colors.white,
                                  activeTrackColor: Colors.white38,
                                  inactiveThumbColor: Colors.white54,
                                  inactiveTrackColor: Colors.white24,
                                  materialTapTargetSize: MaterialTapTargetSize.shrinkWrap,
                                ),
                              ),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 16),

                  // ── Auto-STT 결과 카드 ─────────────────────────────
                  if (svc.lastAutoSttText != null) ...[
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(18),
                      decoration: BoxDecoration(
                        color: Colors.white,
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: const Color(0xFF7B61FF).withOpacity(0.35), width: 1.5),
                        boxShadow: const [BoxShadow(color: Color(0x147B61FF), blurRadius: 16, offset: Offset(0, 8))],
                      ),
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Container(
                            width: 40, height: 40,
                            decoration: BoxDecoration(
                              color: PppdColors.softPurple,
                              borderRadius: BorderRadius.circular(14),
                            ),
                            child: const Icon(Icons.record_voice_over_rounded,
                                color: PppdColors.purple, size: 20),
                          ),
                          const SizedBox(width: 12),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text('자동 STT',
                                    style: pppdText(size: 11, color: PppdColors.purple,
                                        weight: FontWeight.w700)),
                                const SizedBox(height: 4),
                                SelectableText(
                                  svc.lastAutoSttText!,
                                  style: pppdText(size: 16, weight: FontWeight.w600, height: 1.45),
                                ),
                              ],
                            ),
                          ),
                          GestureDetector(
                            onTap: () => svc.clearAutoSttText(),
                            child: const Icon(Icons.close_rounded, size: 18, color: PppdColors.muted),
                          ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],

                  // ── 최신 감지 결과 ─────────────────────────────────
                  if (latest != null) ...[
                    Container(
                      width: double.infinity,
                      padding: const EdgeInsets.all(18),
                      decoration: BoxDecoration(
                        color: _alertBgColor(latest.priority),
                        borderRadius: BorderRadius.circular(20),
                        border: Border.all(color: _alertBorderColor(latest.priority), width: 1.5),
                      ),
                      child: Row(
                        children: [
                          Text(latest.emoji, style: const TextStyle(fontSize: 36)),
                          const SizedBox(width: 14),
                          Expanded(
                            child: Column(
                              crossAxisAlignment: CrossAxisAlignment.start,
                              children: [
                                Text(
                                  latest.label,
                                  style: pppdText(size: 16, weight: FontWeight.w800, color: PppdColors.text),
                                  maxLines: 1, overflow: TextOverflow.ellipsis,
                                ),
                                const SizedBox(height: 3),
                                Text(
                                  '신뢰도 ${(latest.confidence * 100).toStringAsFixed(0)}%  •  P(Alert) ${(latest.pAlert * 100).toStringAsFixed(0)}%',
                                  style: pppdText(size: 12, color: PppdColors.muted),
                                ),
                              ],
                            ),
                          ),
                          if (latest.priority == AlertPriority.urgent)
                            Container(
                              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                              decoration: BoxDecoration(
                                color: PppdColors.danger,
                                borderRadius: BorderRadius.circular(8),
                              ),
                              child: Text('긴급', style: pppdText(size: 11, color: Colors.white, weight: FontWeight.w700)),
                            ),
                        ],
                      ),
                    ),
                    const SizedBox(height: 16),
                  ],

                  // ── 빠른 실행 ─────────────────────────────────────
                  Text('빠른 실행', style: pppdText(size: 20, weight: FontWeight.w900)),
                  const SizedBox(height: 14),
                  PppdActionCard(
                    title: '지도 보기',
                    subtitle: '내 위치와 위험 장소를 한눈에 확인해요.',
                    icon: Icons.explore_rounded,
                    badge: 'LIVE',
                    onTap: () => context.pushNamed(MapWidget.routeName),
                  ),
                  const SizedBox(height: 14),
                  PppdActionCard(
                    title: '맞춤 설정',
                    subtitle: '자주 가는 장소와 필요한 소리 정보를 등록해요.',
                    icon: Icons.tune_rounded,
                    onTap: () => context.pushNamed(CustomizingWidget.routeName),
                  ),
                  const SizedBox(height: 14),
                  PppdActionCard(
                    title: '알림 확인',
                    subtitle: '위험 신호와 소리 감지 결과를 확인해요.',
                    icon: Icons.notifications_rounded,
                    badge: svc.alerts.isNotEmpty ? '${svc.alerts.length}' : null,
                    onTap: () => context.pushNamed(AlertWidget.routeName),
                  ),
                  const SizedBox(height: 14),
                  PppdActionCard(
                    title: '사용 방법',
                    subtitle: 'PromptEar의 기본 사용 흐름을 빠르게 익혀요.',
                    icon: Icons.school_rounded,
                    onTap: () => context.pushNamed(Tutorial1Widget.routeName),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Color _alertBgColor(AlertPriority p) {
    switch (p) {
      case AlertPriority.urgent: return PppdColors.danger.withOpacity(0.08);
      case AlertPriority.normal: return PppdColors.safe.withOpacity(0.08);
      case AlertPriority.weak:   return PppdColors.softPurple;
    }
  }

  Color _alertBorderColor(AlertPriority p) {
    switch (p) {
      case AlertPriority.urgent: return PppdColors.danger.withOpacity(0.3);
      case AlertPriority.normal: return PppdColors.safe.withOpacity(0.3);
      case AlertPriority.weak:   return PppdColors.purple.withOpacity(0.2);
    }
  }
}
