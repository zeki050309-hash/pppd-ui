import '/flutter_flow/flutter_flow_util.dart';
import '/shared/pppd_design.dart';
import '/services/promptear_service.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
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

  @override
  void initState() {
    super.initState();
    _model = createModel(context, () => AlertModel());
    WidgetsBinding.instance.addPostFrameCallback((_) => safeSetState(() {}));
  }

  @override
  void dispose() {
    _model.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final svc = context.watch<PromptEarService>();

    return GestureDetector(
      onTap: () {
        FocusScope.of(context).unfocus();
        FocusManager.instance.primaryFocus?.unfocus();
      },
      child: PppdScaffold(
        title: '알림 기록',
        subtitle: '감지된 소리와 알림 이력을 확인해요.',
        trailing: svc.alerts.isNotEmpty
            ? IconButton(
                icon: const Icon(Icons.delete_sweep_rounded, color: PppdColors.muted),
                onPressed: () async {
                  final ok = await showDialog<bool>(
                    context: context,
                    builder: (c) => AlertDialog(
                      title: const Text('모두 삭제'),
                      content: const Text('알림 기록을 모두 지울까요?'),
                      actions: [
                        TextButton(onPressed: () => Navigator.pop(c, false), child: const Text('취소')),
                        TextButton(
                          onPressed: () => Navigator.pop(c, true),
                          child: const Text('삭제', style: TextStyle(color: PppdColors.danger)),
                        ),
                      ],
                    ),
                  );
                  if (ok == true) svc.clearAlerts();
                },
              )
            : null,
        child: svc.alerts.isEmpty
            ? _emptyState()
            : ListView.separated(
                padding: const EdgeInsets.fromLTRB(20, 10, 20, 28),
                itemCount: svc.alerts.length,
                separatorBuilder: (_, __) => const SizedBox(height: 10),
                itemBuilder: (_, i) => _AlertTile(alert: svc.alerts[i]),
              ),
      ),
    );
  }

  Widget _emptyState() {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: PppdSectionCard(
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Container(
                width: 84, height: 84,
                decoration: BoxDecoration(color: PppdColors.softPurple, borderRadius: BorderRadius.circular(28)),
                child: const Icon(Icons.notifications_none_rounded, size: 42, color: PppdColors.purple),
              ),
              const SizedBox(height: 18),
              Text('아직 감지된 소리가 없어요', style: pppdText(size: 21, weight: FontWeight.w900), textAlign: TextAlign.center),
              const SizedBox(height: 8),
              Text('홈 화면에서 소리 감지를 시작하면 위험 신호와 감지 이력이 여기에 표시돼요.', style: pppdText(size: 14, color: PppdColors.muted, height: 1.45), textAlign: TextAlign.center),
            ],
          ),
        ),
      ),
    );
  }
}

// ── 알림 타일 ─────────────────────────────────────────────────────
class _AlertTile extends StatelessWidget {
  const _AlertTile({required this.alert});
  final SoundAlert alert;

  @override
  Widget build(BuildContext context) {
    final timeStr = '${alert.timestamp.hour.toString().padLeft(2, '0')}:'
        '${alert.timestamp.minute.toString().padLeft(2, '0')}';

    return Container(
      padding: const EdgeInsets.all(16),
      decoration: BoxDecoration(
        color: _bgColor,
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: _borderColor, width: 1.5),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(alert.emoji, style: const TextStyle(fontSize: 32)),
          const SizedBox(width: 12),
          Expanded(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Text(
                        alert.label,
                        style: pppdText(size: 15, weight: FontWeight.w800, color: PppdColors.text),
                        maxLines: 2, overflow: TextOverflow.ellipsis,
                      ),
                    ),
                    if (alert.priority == AlertPriority.urgent)
                      Container(
                        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
                        decoration: BoxDecoration(color: PppdColors.danger, borderRadius: BorderRadius.circular(7)),
                        child: Text('긴급', style: pppdText(size: 10, color: Colors.white, weight: FontWeight.w700)),
                      ),
                  ],
                ),
                const SizedBox(height: 6),
                Wrap(
                  spacing: 6, runSpacing: 4,
                  children: [
                    _chip(alert.source == 'clap' ? 'CLAP' : 'YAMNet', PppdColors.purple),
                    _chip(alert.category, PppdColors.deepPurple.withOpacity(0.6)),
                    _chip('신뢰도 ${(alert.confidence * 100).toStringAsFixed(0)}%', PppdColors.muted),
                  ],
                ),
                const SizedBox(height: 6),
                Row(
                  children: [
                    Icon(
                      Icons.notifications_active_rounded,
                      size: 13,
                      color: alert.pAlert >= 0.37 ? PppdColors.safe : PppdColors.muted,
                    ),
                    const SizedBox(width: 4),
                    Text(
                      'P(Alert) ${(alert.pAlert * 100).toStringAsFixed(0)}%',
                      style: pppdText(size: 12, color: alert.pAlert >= 0.37 ? PppdColors.safe : PppdColors.muted),
                    ),
                    const Spacer(),
                    Text(timeStr, style: pppdText(size: 12, color: PppdColors.muted)),
                  ],
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget _chip(String label, Color color) => Container(
        padding: const EdgeInsets.symmetric(horizontal: 7, vertical: 3),
        decoration: BoxDecoration(color: color.withOpacity(0.1), borderRadius: BorderRadius.circular(6)),
        child: Text(label, style: pppdText(size: 11, color: color, weight: FontWeight.w600)),
      );

  Color get _bgColor {
    switch (alert.priority) {
      case AlertPriority.urgent: return PppdColors.danger.withOpacity(0.06);
      case AlertPriority.normal: return PppdColors.safe.withOpacity(0.06);
      case AlertPriority.weak:   return Colors.white;
    }
  }

  Color get _borderColor {
    switch (alert.priority) {
      case AlertPriority.urgent: return PppdColors.danger.withOpacity(0.25);
      case AlertPriority.normal: return PppdColors.safe.withOpacity(0.25);
      case AlertPriority.weak:   return const Color(0xFFEAE4FF);
    }
  }
}
