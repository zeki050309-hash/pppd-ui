
import '/flutter_flow/flutter_flow_util.dart';
import '/index.dart';
import '/shared/pppd_design.dart';
import 'package:flutter/material.dart';
import 'customizing_model.dart';
export 'customizing_model.dart';

class CustomizingWidget extends StatefulWidget {
  const CustomizingWidget({super.key});
  static String routeName = 'customizing';
  static String routePath = '/customizing';
  @override
  State<CustomizingWidget> createState() => _CustomizingWidgetState();
}

class _CustomizingWidgetState extends State<CustomizingWidget> {
  late CustomizingModel _model;
  final scaffoldKey = GlobalKey<ScaffoldState>();
  @override
  void initState() {
    super.initState();
    _model = createModel(context, () => CustomizingModel());
    WidgetsBinding.instance.addPostFrameCallback((_) => safeSetState(() {}));
  }
  @override
  void dispose() { _model.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () { FocusScope.of(context).unfocus(); FocusManager.instance.primaryFocus?.unfocus(); },
      child: PppdScaffold(
        title: '맞춤 설정',
        subtitle: '내 생활 환경에 맞는 장소와 소리를 등록해요.',
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 10, 20, 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              PppdSectionCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('무엇을 등록할까요?', style: pppdText(size: 22, weight: FontWeight.w900)),
                    const SizedBox(height: 8),
                    Text('소리만 따로 등록하거나, 장소를 먼저 고른 뒤 그 장소에서 자주 들리는 소리를 연결할 수 있어요.', style: pppdText(size: 14, color: PppdColors.muted, height: 1.45)),
                  ],
                ),
              ),
              const SizedBox(height: 18),
              PppdActionCard(title: '소리 등록', subtitle: '사람, 동물, 근무 환경에서 필요한 소리를 선택해요.', icon: Icons.graphic_eq_rounded, badge: 'Sound', onTap: () => context.pushNamed(AboutSoundWidget.routeName)),
              const SizedBox(height: 14),
              PppdActionCard(title: '장소 등록', subtitle: '자주 방문하는 장소를 등록하고 관련 소리를 이어서 설정해요.', icon: Icons.place_rounded, badge: 'Place', onTap: () => context.pushNamed(AboutLocationWidget.routeName)),
            ],
          ),
        ),
      ),
    );
  }
}
