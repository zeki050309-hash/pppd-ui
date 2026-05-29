import '/flutter_flow/flutter_flow_util.dart';
import '/index.dart';
import '/shared/pppd_design.dart';
import '/services/promptear_service.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
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
  late TextEditingController _serverUrlController;

  @override
  void initState() {
    super.initState();
    _model = createModel(context, () => CustomizingModel());
    WidgetsBinding.instance.addPostFrameCallback((_) {
      final svc = context.read<PromptEarService>();
      _serverUrlController = TextEditingController(text: svc.serverUrl);
      safeSetState(() {});
    });
    _serverUrlController = TextEditingController();
  }

  @override
  void dispose() {
    _model.dispose();
    _serverUrlController.dispose();
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
        title: '맞춤 설정',
        subtitle: '내 생활 환경에 맞는 장소와 소리를 등록해요.',
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 10, 20, 28),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              // ── 소리 감지 설정 ────────────────────────────────────
              PppdSectionCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('소리 감지 설정', style: pppdText(size: 18, weight: FontWeight.w900)),
                    const SizedBox(height: 16),

                    // dB 임계값 슬라이더
                    Row(
                      children: [
                        const Icon(Icons.graphic_eq_rounded, size: 18, color: PppdColors.purple),
                        const SizedBox(width: 8),
                        Text('최소 감지 음량', style: pppdText(size: 14, weight: FontWeight.w700)),
                        const Spacer(),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                          decoration: BoxDecoration(
                            color: PppdColors.purple.withOpacity(0.1),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            '${svc.dbThreshold.toInt()} dB',
                            style: pppdText(size: 14, weight: FontWeight.w800, color: PppdColors.purple),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 6),
                    SliderTheme(
                      data: SliderTheme.of(context).copyWith(
                        activeTrackColor:   PppdColors.purple,
                        inactiveTrackColor: PppdColors.softPurple,
                        thumbColor:         PppdColors.purple,
                        overlayColor:       PppdColors.purple.withOpacity(0.15),
                        trackHeight:        6,
                      ),
                      child: Slider(
                        value:   svc.dbThreshold,
                        min:     20,
                        max:     80,
                        divisions: 12,
                        onChanged: (v) {
                          svc.dbThreshold = v;
                        },
                        onChangeEnd: (_) => svc.savePrefs(),
                      ),
                    ),
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text('20 dB\n조용한 환경', style: pppdText(size: 11, color: PppdColors.muted), textAlign: TextAlign.left),
                        Text('50 dB\n평균 대화', style: pppdText(size: 11, color: PppdColors.muted), textAlign: TextAlign.center),
                        Text('80 dB\n시끄러운 곳', style: pppdText(size: 11, color: PppdColors.muted), textAlign: TextAlign.right),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(
                      '이 값 이상의 소리만 서버로 전송해요. 낮을수록 민감하게 반응하지만 진동이 잦아질 수 있어요.',
                      style: pppdText(size: 12, color: PppdColors.muted, height: 1.4),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 16),

              // ── 서버 연결 설정 ─────────────────────────────────────
              PppdSectionCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Text('서버 주소', style: pppdText(size: 18, weight: FontWeight.w900)),
                        const Spacer(),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
                          decoration: BoxDecoration(
                            color: svc.serverConnected
                                ? PppdColors.safe.withOpacity(0.12)
                                : PppdColors.danger.withOpacity(0.12),
                            borderRadius: BorderRadius.circular(10),
                          ),
                          child: Text(
                            svc.serverConnected ? '연결됨' : '연결 안됨',
                            style: pppdText(
                              size: 12,
                              color: svc.serverConnected ? PppdColors.safe : PppdColors.danger,
                              weight: FontWeight.w700,
                            ),
                          ),
                        ),
                      ],
                    ),
                    const SizedBox(height: 12),
                    TextField(
                      controller: _serverUrlController,
                      decoration: InputDecoration(
                        hintText: 'http://192.168.x.x:8000',
                        hintStyle: pppdText(size: 14, color: PppdColors.muted),
                        filled: true,
                        fillColor: PppdColors.lavender,
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(14),
                          borderSide: BorderSide.none,
                        ),
                        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                      ),
                      style: pppdText(size: 14),
                      keyboardType: TextInputType.url,
                    ),
                    const SizedBox(height: 10),
                    PppdPrimaryButton(
                      text: '저장 후 연결 확인',
                      onTap: () async {
                        svc.serverUrl = _serverUrlController.text.trim();
                        await svc.savePrefs();
                        await svc.checkServer();
                        if (context.mounted) {
                          ScaffoldMessenger.of(context).showSnackBar(
                            SnackBar(
                              content: Text(svc.serverConnected ? '서버에 연결됐어요!' : '서버에 연결할 수 없어요. 주소를 확인해 주세요.'),
                            ),
                          );
                        }
                      },
                    ),
                    const SizedBox(height: 6),
                    Text('PC와 같은 Wi-Fi에 연결된 상태에서 PC의 IP 주소를 입력하세요.', style: pppdText(size: 12, color: PppdColors.muted, height: 1.4)),
                  ],
                ),
              ),
              const SizedBox(height: 18),

              // ── 소리/장소 등록 ─────────────────────────────────────
              PppdSectionCard(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('무엇을 등록할까요?', style: pppdText(size: 18, weight: FontWeight.w900)),
                    const SizedBox(height: 8),
                    Text(
                      '소리만 따로 등록하거나, 장소를 먼저 고른 뒤 그 장소에서 자주 들리는 소리를 연결할 수 있어요.',
                      style: pppdText(size: 14, color: PppdColors.muted, height: 1.45),
                    ),
                  ],
                ),
              ),
              const SizedBox(height: 14),
              PppdActionCard(
                title: '소리 등록',
                subtitle: '사람, 동물, 근무 환경에서 필요한 소리를 선택해요.',
                icon: Icons.graphic_eq_rounded,
                badge: 'Sound',
                onTap: () => context.pushNamed(AboutSoundWidget.routeName),
              ),
              const SizedBox(height: 14),
              PppdActionCard(
                title: '장소 등록',
                subtitle: '자주 방문하는 장소를 등록하고 관련 소리를 이어서 설정해요.',
                icon: Icons.place_rounded,
                badge: 'Place',
                onTap: () => context.pushNamed(AboutLocationWidget.routeName),
              ),
            ],
          ),
        ),
      ),
    );
  }
}
