
import '/flutter_flow/flutter_flow_util.dart';
import '/index.dart';
import '/shared/pppd_design.dart';
import 'package:flutter/material.dart';
import 'tutorial4_model.dart';
export 'tutorial4_model.dart';

class Tutorial4Widget extends StatefulWidget {
  const Tutorial4Widget({super.key});
  static String routeName = 'tutorial_4';
  static String routePath = '/tutorial4';
  @override
  State<Tutorial4Widget> createState() => _Tutorial4WidgetState();
}

class _Tutorial4WidgetState extends State<Tutorial4Widget> {
  late Tutorial4Model _model;
  final scaffoldKey = GlobalKey<ScaffoldState>();
  @override
  void initState() { super.initState(); _model = createModel(context, () => Tutorial4Model()); WidgetsBinding.instance.addPostFrameCallback((_) => safeSetState(() {})); }
  @override
  void dispose() { _model.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () { FocusScope.of(context).unfocus(); FocusManager.instance.primaryFocus?.unfocus(); },
      child: PppdScaffold(
        title: '사용 방법 4/4',
        subtitle: 'PromptEar를 빠르게 시작해요.',
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 20, 20, 28),
          child: Column(
            children: [
              Expanded(
                child: PppdSectionCard(
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Container(width: 96, height: 96, decoration: BoxDecoration(color: PppdColors.softPurple, borderRadius: BorderRadius.circular(32)), child: Icon(Icons.notifications_active_rounded, color: PppdColors.purple, size: 48)),
                      const SizedBox(height: 26),
                      Text('알림 받기', style: pppdText(size: 25, weight: FontWeight.w900), textAlign: TextAlign.center),
                      const SizedBox(height: 12),
                      Text('중요한 소리가 감지되면 이해하기 쉬운 방식으로 알려줘요.', style: pppdText(size: 15, color: PppdColors.muted, height: 1.45), textAlign: TextAlign.center),
                      const SizedBox(height: 20),
                      Container(width: double.infinity, padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: PppdColors.lavender, borderRadius: BorderRadius.circular(20)), child: Text('이제 홈으로 이동해서 지도와 맞춤 설정을 사용해 보세요.', style: pppdText(size: 14, height: 1.5), textAlign: TextAlign.center)),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
              PppdPrimaryButton(text: '시작하기', icon: Icons.arrow_forward_rounded, onTap: () => context.pushNamed(HomePageWidget.routeName)),
            ],
          ),
        ),
      ),
    );
  }
}
