import '/shared/pppd_design.dart';
import '/services/promptear_service.dart';
import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

/// Speech(음성 → 텍스트) 탭.
/// 홈 탭의 소리 감지와는 완전히 분리된 기능이다.
/// 이 탭에서 녹음을 시작하면 홈 탭의 소리 감지 녹음은 자동으로 멈춘다.
class SpeechWidget extends StatefulWidget {
  const SpeechWidget({super.key});

  static String routeName = 'Speech';
  static String routePath = '/speech';

  @override
  State<SpeechWidget> createState() => _SpeechWidgetState();
}

class _SpeechWidgetState extends State<SpeechWidget> {
  bool _busy = false;            // STT 변환 대기 중
  String? _resultText;           // 마지막 인식 결과
  String? _error;
  final List<String> _history = [];

  Future<void> _toggleRecord() async {
    final svc = context.read<PromptEarService>();

    if (svc.isSpeechRecording) {
      // ── 녹음 종료 → 서버로 전송하여 텍스트 변환 ──
      setState(() { _busy = true; _error = null; });
      try {
        final text = await svc.stopSpeechRecordingAndTranscribe();
        if (!mounted) return;
        setState(() {
          _busy = false;
          if (text != null && text.isNotEmpty) {
            _resultText = text;
            _history.insert(0, text);
            if (_history.length > 20) _history.removeLast();
          } else {
            _resultText = null;
            _error = '인식된 음성이 없어요. 다시 시도해 주세요.';
          }
        });
      } catch (e) {
        if (!mounted) return;
        setState(() { _busy = false; _error = '$e'; });
      }
    } else {
      // ── 녹음 시작 ──
      if (!svc.serverConnected) {
        setState(() => _error = '서버에 연결되어 있지 않아요. 맞춤 설정에서 서버 주소를 확인해 주세요.');
        return;
      }
      setState(() { _error = null; _resultText = null; });
      final ok = await svc.startSpeechRecording();
      if (!ok && mounted) {
        setState(() => _error = '마이크 권한이 필요해요.');
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    final svc = context.watch<PromptEarService>();
    final recording = svc.isSpeechRecording;

    return Scaffold(
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
                // ── 헤더 ───────────────────────────────────────────
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
                      child: const Icon(Icons.record_voice_over_rounded,
                          color: Colors.white, size: 28),
                    ),
                    const SizedBox(width: 14),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text('음성 → 텍스트',
                              style: pppdText(size: 24, weight: FontWeight.w900)),
                          Text('말한 내용을 글자로 바꿔드려요.',
                              style: pppdText(size: 13, color: PppdColors.muted)),
                        ],
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 22),

                // ── 녹음 카드 ───────────────────────────────────────
                Container(
                  width: double.infinity,
                  padding: const EdgeInsets.symmetric(vertical: 36, horizontal: 24),
                  decoration: BoxDecoration(
                    borderRadius: BorderRadius.circular(30),
                    gradient: LinearGradient(
                      begin: Alignment.topLeft,
                      end: Alignment.bottomRight,
                      colors: recording
                          ? [const Color(0xFFFF7BA0), const Color(0xFFFF5B7F)]
                          : [const Color(0xFF6C4DFF), const Color(0xFF9E7BFF)],
                    ),
                    boxShadow: [
                      BoxShadow(
                        color: (recording ? PppdColors.danger : const Color(0xFF7B61FF))
                            .withOpacity(0.35),
                        blurRadius: 28, offset: const Offset(0, 16),
                      ),
                    ],
                  ),
                  child: Column(
                    children: [
                      Text(
                        _busy
                            ? '인식 중…'
                            : (recording ? '녹음 중…' : '버튼을 눌러 녹음하세요'),
                        style: pppdText(
                            size: 20, weight: FontWeight.w900, color: Colors.white),
                      ),
                      const SizedBox(height: 6),
                      Text(
                        recording
                            ? '다시 누르면 녹음을 멈추고 글자로 변환해요.'
                            : '홈 탭의 소리 감지는 녹음 중 자동으로 멈춰요.',
                        textAlign: TextAlign.center,
                        style: pppdText(size: 12, color: Colors.white70, height: 1.4),
                      ),
                      const SizedBox(height: 22),
                      GestureDetector(
                        onTap: _busy ? null : _toggleRecord,
                        child: Container(
                          width: 88, height: 88,
                          decoration: BoxDecoration(
                            color: Colors.white,
                            shape: BoxShape.circle,
                            boxShadow: [
                              BoxShadow(
                                color: Colors.black.withOpacity(0.12),
                                blurRadius: 10,
                              ),
                            ],
                          ),
                          child: _busy
                              ? const Padding(
                                  padding: EdgeInsets.all(26),
                                  child: CircularProgressIndicator(
                                      strokeWidth: 3, color: PppdColors.purple),
                                )
                              : Icon(
                                  recording ? Icons.stop_rounded : Icons.mic_rounded,
                                  size: 44,
                                  color: recording ? PppdColors.danger : PppdColors.purple,
                                ),
                        ),
                      ),
                    ],
                  ),
                ),
                const SizedBox(height: 18),

                // ── 오류 표시 ───────────────────────────────────────
                if (_error != null) ...[
                  Container(
                    width: double.infinity,
                    padding: const EdgeInsets.all(14),
                    decoration: BoxDecoration(
                      color: PppdColors.danger.withOpacity(0.08),
                      borderRadius: BorderRadius.circular(16),
                      border: Border.all(color: PppdColors.danger.withOpacity(0.3)),
                    ),
                    child: Text(_error!,
                        style: pppdText(size: 13, color: PppdColors.danger)),
                  ),
                  const SizedBox(height: 16),
                ],

                // ── 최근 인식 결과 ──────────────────────────────────
                if (_resultText != null) ...[
                  Text('인식 결과', style: pppdText(size: 16, weight: FontWeight.w900)),
                  const SizedBox(height: 10),
                  PppdSectionCard(
                    child: SelectableText(
                      _resultText!,
                      style: pppdText(size: 18, weight: FontWeight.w600, height: 1.5),
                    ),
                  ),
                  const SizedBox(height: 20),
                ],

                // ── 기록 ────────────────────────────────────────────
                if (_history.length > 1) ...[
                  Text('이전 기록', style: pppdText(size: 16, weight: FontWeight.w900)),
                  const SizedBox(height: 10),
                  ..._history.skip(1).map((t) => Container(
                        width: double.infinity,
                        margin: const EdgeInsets.only(bottom: 10),
                        padding: const EdgeInsets.all(14),
                        decoration: BoxDecoration(
                          color: Colors.white,
                          borderRadius: BorderRadius.circular(16),
                          border: Border.all(color: const Color(0xFFEAE4FF)),
                        ),
                        child: Text(t,
                            style: pppdText(size: 14, color: PppdColors.text, height: 1.4)),
                      )),
                ],
              ],
            ),
          ),
        ),
      ),
    );
  }
}
