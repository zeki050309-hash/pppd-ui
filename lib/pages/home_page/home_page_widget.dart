
import '/flutter_flow/flutter_flow_util.dart';
import '/index.dart';
import '/shared/pppd_design.dart';
import 'package:flutter/material.dart';
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
    WidgetsBinding.instance.addPostFrameCallback((_) => safeSetState(() {}));
  }

  @override
  void dispose() {
    _model.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
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
                  Row(
                    children: [
                      Container(
                        width: 54,
                        height: 54,
                        decoration: BoxDecoration(
                          borderRadius: BorderRadius.circular(20),
                          gradient: const LinearGradient(colors: [Color(0xFF7B61FF), Color(0xFFB59CFF)]),
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
                            Text('PPPD', style: pppdText(size: 28, weight: FontWeight.w900)),
                            Text('소리와 위치를 더 직관적으로', style: pppdText(size: 13, color: PppdColors.muted)),
                          ],
                        ),
                      ),
                    ],
                  ),
                  const SizedBox(height: 26),
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(24),
                    decoration: BoxDecoration(
                      borderRadius: BorderRadius.circular(30),
                      gradient: const LinearGradient(
                        begin: Alignment.topLeft,
                        end: Alignment.bottomRight,
                        colors: [Color(0xFF6C4DFF), Color(0xFF9E7BFF)],
                      ),
                      boxShadow: const [BoxShadow(color: Color(0x337B61FF), blurRadius: 28, offset: Offset(0, 16))],
                    ),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text('오늘도 안전하게\n주변 소리를 확인해요', style: pppdText(size: 26, weight: FontWeight.w900, color: Colors.white, height: 1.15)),
                        const SizedBox(height: 12),
                        Text('위험 장소는 나비 마커로, 사용자 위치는 기본 마커로 지도에서 확인할 수 있어요.', style: pppdText(size: 14, color: const Color(0xFFEDE7FF), height: 1.45)),
                        const SizedBox(height: 22),
                        InkWell(
                          borderRadius: BorderRadius.circular(18),
                          onTap: () => context.pushNamed(MapWidget.routeName),
                          child: Container(
                            height: 52,
                            padding: const EdgeInsets.symmetric(horizontal: 18),
                            decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(18)),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                const Icon(Icons.map_rounded, color: PppdColors.purple),
                                const SizedBox(width: 8),
                                Text('지도 열기', style: pppdText(size: 15, weight: FontWeight.w900, color: PppdColors.purple)),
                              ],
                            ),
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(height: 24),
                  Text('빠른 실행', style: pppdText(size: 20, weight: FontWeight.w900)),
                  const SizedBox(height: 14),
                  PppdActionCard(title: '지도 보기', subtitle: '내 위치와 위험 장소를 한눈에 확인해요.', icon: Icons.explore_rounded, badge: 'LIVE', onTap: () => context.pushNamed(MapWidget.routeName)),
                  const SizedBox(height: 14),
                  PppdActionCard(title: '맞춤 설정', subtitle: '자주 가는 장소와 필요한 소리 정보를 등록해요.', icon: Icons.tune_rounded, onTap: () => context.pushNamed(CustomizingWidget.routeName)),
                  const SizedBox(height: 14),
                  PppdActionCard(title: '알림 확인', subtitle: '위험 신호와 소리 감지 결과를 확인해요.', icon: Icons.notifications_rounded, onTap: () => context.pushNamed(AlertWidget.routeName)),
                  const SizedBox(height: 14),
                  PppdActionCard(title: '사용 방법', subtitle: 'PPPD의 기본 사용 흐름을 빠르게 익혀요.', icon: Icons.school_rounded, onTap: () => context.pushNamed(Tutorial1Widget.routeName)),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
