
import '/flutter_flow/flutter_flow_util.dart';
import '/index.dart';
import '/shared/pppd_design.dart';
import 'package:flutter/material.dart';
import 'tutorial1_model.dart';
export 'tutorial1_model.dart';

class Tutorial1Widget extends StatefulWidget {
  const Tutorial1Widget({super.key});
  static String routeName = 'tutorial_1';
  static String routePath = '/tutorial1';
  @override
  State<Tutorial1Widget> createState() => _Tutorial1WidgetState();
}

class _Tutorial1WidgetState extends State<Tutorial1Widget> {
  late Tutorial1Model _model;
  final scaffoldKey = GlobalKey<ScaffoldState>();
  @override
  void initState() { super.initState(); _model = createModel(context, () => Tutorial1Model()); WidgetsBinding.instance.addPostFrameCallback((_) => safeSetState(() {})); }
  @override
  void dispose() { _model.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () { FocusScope.of(context).unfocus(); FocusManager.instance.primaryFocus?.unfocus(); },
      child: PppdScaffold(
        title: '사용 방법 1/4',
        subtitle: 'PPPD를 빠르게 시작해요.',
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
          child: Column(
            children: [
              Expanded(
                child: PppdSectionCard(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Container(width: 96, height: 96, decoration: BoxDecoration(color: PppdColors.softPurple, borderRadius: BorderRadius.circular(32)), child: Icon(Icons.map_rounded, color: PppdColors.purple, size: 48)),
                      const SizedBox(height: 26),
                      Text('지도에서 확인하기', style: pppdText(size: 25, weight: FontWeight.w900), textAlign: TextAlign.center),
                      const SizedBox(height: 12),
                      Text('내 위치와 위험 장소를 지도 위에서 한눈에 확인해요.', style: pppdText(size: 15, color: PppdColors.muted, height: 1.45), textAlign: TextAlign.center),
                      const SizedBox(height: 20),
                      Container(width: double.infinity, padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: PppdColors.lavender, borderRadius: BorderRadius.circular(20)), child: Text('위험 장소는 나비 마커로 표시되고, 내 위치는 기본 마커로 표시됩니다.', style: pppdText(size: 14, height: 1.5), textAlign: TextAlign.center)),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
              PppdPrimaryButton(text: '다음', icon: Icons.arrow_forward_rounded, onTap: () => context.pushNamed(Tutorial2Widget.routeName)),
            ],
          ),
        ),
      ),
    );
  }
}
