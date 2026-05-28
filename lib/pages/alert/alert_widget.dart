
import '/flutter_flow/flutter_flow_util.dart';
import '/shared/pppd_design.dart';
import 'package:flutter/material.dart';
import 'alert_model.dart';
export 'alert_model.dart';

class AlertWidget extends StatefulWidget {
  const AlertWidget({super.key});
  static String routeName = 'alert';
  static String routePath = '/alert';
  @override
  State<AlertWidget> createState() => _AlertWidgetState();
}

class _AlertWidgetState extends State<AlertWidget> {
  late AlertModel _model;
  final scaffoldKey = GlobalKey<ScaffoldState>();
  @override
  void initState() { super.initState(); _model = createModel(context, () => AlertModel()); WidgetsBinding.instance.addPostFrameCallback((_) => safeSetState(() {})); }
  @override
  void dispose() { _model.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () { FocusScope.of(context).unfocus(); FocusManager.instance.primaryFocus?.unfocus(); },
      child: PppdScaffold(
        title: '알림',
        subtitle: '위험 신호와 감지된 소리를 확인해요.',
        child: Padding(
          padding: const EdgeInsets.fromLTRB(20, 34, 20, 28),
          child: PppdSectionCard(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 84,
                  height: 84,
                  decoration: BoxDecoration(color: PppdColors.softPurple, borderRadius: BorderRadius.circular(28)),
                  child: const Icon(Icons.notifications_none_rounded, size: 42, color: PppdColors.purple),
                ),
                const SizedBox(height: 18),
                Text('아직 새로운 알림이 없어요', style: pppdText(size: 21, weight: FontWeight.w900), textAlign: TextAlign.center),
                const SizedBox(height: 8),
                Text('위험 장소나 중요한 소리가 감지되면 여기에 알림이 표시될 예정이에요.', style: pppdText(size: 14, color: PppdColors.muted, height: 1.45), textAlign: TextAlign.center),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
