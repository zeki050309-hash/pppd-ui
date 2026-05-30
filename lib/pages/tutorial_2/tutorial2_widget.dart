
import '/flutter_flow/flutter_flow_util.dart';
import '/index.dart';
import '/shared/pppd_design.dart';
import 'package:flutter/material.dart';
import 'tutorial2_model.dart';
export 'tutorial2_model.dart';

class Tutorial2Widget extends StatefulWidget {
  const Tutorial2Widget({super.key});
  static String routeName = 'tutorial_2';
  static String routePath = '/tutorial2';
  @override
  State<Tutorial2Widget> createState() => _Tutorial2WidgetState();
}

class _Tutorial2WidgetState extends State<Tutorial2Widget> {
  late Tutorial2Model _model;
  final scaffoldKey = GlobalKey<ScaffoldState>();
  @override
  void initState() { super.initState(); _model = createModel(context, () => Tutorial2Model()); WidgetsBinding.instance.addPostFrameCallback((_) => safeSetState(() {})); }
  @override
  void dispose() { _model.dispose(); super.dispose(); }
  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () { FocusScope.of(context).unfocus(); FocusManager.instance.primaryFocus?.unfocus(); },
      child: PppdScaffold(
        title: '사용 방법 2/4',
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
                      Container(width: 96, height: 96, decoration: BoxDecoration(color: PppdColors.softPurple, borderRadius: BorderRadius.circular(32)), child: Icon(Icons.record_voice_over_rounded, color: PppdColors.purple, size: 48)),
                      const SizedBox(height: 26),
                      Text('음성을 글자로', style: pppdText(size: 25, weight: FontWeight.w900), textAlign: TextAlign.center),
                      const SizedBox(height: 12),
                      Text('Speech 탭에서 녹음하면 상대방의 말을 글자로 바꿔서 보여줘요.', style: pppdText(size: 15, color: PppdColors.muted, height: 1.45), textAlign: TextAlign.center),
                      const SizedBox(height: 20),
                      Container(width: double.infinity, padding: const EdgeInsets.all(16), decoration: BoxDecoration(color: PppdColors.lavender, borderRadius: BorderRadius.circular(20)), child: Text('대화를 글로 확인할 수 있어요. 녹음 중에는 홈 탭의 소리 감지가 잠시 멈춰요.', style: pppdText(size: 14, height: 1.5), textAlign: TextAlign.center)),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
              PppdPrimaryButton(text: '다음', icon: Icons.arrow_forward_rounded, onTap: () => context.pushNamed(Tutorial3Widget.routeName)),
            ],
          ),
        ),
      ),
    );
  }
}
