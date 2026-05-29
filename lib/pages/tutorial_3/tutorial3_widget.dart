
import '/flutter_flow/flutter_flow_util.dart';
import '/index.dart';
import '/shared/pppd_design.dart';
import 'package:flutter/material.dart';
import 'tutorial3_model.dart';
export 'tutorial3_model.dart';

class Tutorial3Widget extends StatefulWidget {
  const Tutorial3Widget({super.key});
  static String routeName = 'tutorial_3';
  static String routePath = '/tutorial3';
  @override
  State<Tutorial3Widget> createState() => _Tutorial3WidgetState();
}

class _Tutorial3WidgetState extends State<Tutorial3Widget> {
  late Tutorial3Model _model;
  final scaffoldKey = GlobalKey<ScaffoldState>();
  @override
  void initState() { super.initState(); _model = createModel(context, () => Tutorial3Model()); WidgetsBinding.instance.addPostFrameCallback((_) => safeSetState(() {})); }
  @override
  void dispose() { _model.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () { FocusScope.of(context).unfocus(); FocusManager.instance.primaryFocus?.unfocus(); },
      child: PppdScaffold(
        title: '사용 방법 3/4',
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
                      Container(width: 96, height: 96, decoration: BoxDecoration(color: PppdColors.softPurple, borderRadius: BorderRadius.circular(32)), child: Icon(Icons.graphic_eq_rounded, color: PppdColors.purple, size: 48)),
                      const SizedBox(height: 26),
                      Text('소리 등록하기', style: pppdText(size: 25, weight: FontWeight.w900), textAlign: TextAlign.center),
                      const SizedBox(height: 12),
                      Text('사람, 동물, 근무 환경의 소리를 단계별로 선택해요.', style: pppdText(size: 15, color: PppdColors.muted, height: 1.45), textAlign: TextAlign.center),
                      const SizedBox(height: 20),
                      Container(width: double.infinity, padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: PppdColors.lavender, borderRadius: BorderRadius.circular(20)), child: Text('근무 환경은 장소를 선택한 뒤 그 장소에서 자주 들리는 소리까지 고를 수 있습니다.', style: pppdText(size: 14, height: 1.5), textAlign: TextAlign.center)),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
              PppdPrimaryButton(text: '다음', icon: Icons.arrow_forward_rounded, onTap: () => context.pushNamed(Tutorial4Widget.routeName)),
            ],
          ),
        ),
      ),
    );
  }
}
