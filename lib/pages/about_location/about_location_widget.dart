
import '/flutter_flow/flutter_flow_drop_down.dart';
import '/flutter_flow/flutter_flow_util.dart';
import '/flutter_flow/form_field_controller.dart';
import '/index.dart';
import '/shared/pppd_design.dart';
import 'package:flutter/material.dart';
import 'about_location_model.dart';
export 'about_location_model.dart';

class AboutLocationWidget extends StatefulWidget {
  const AboutLocationWidget({super.key});
  static String routeName = 'AboutLocation';
  static String routePath = '/aboutLocation';
  @override
  State<AboutLocationWidget> createState() => _AboutLocationWidgetState();
}

class _AboutLocationWidgetState extends State<AboutLocationWidget> {
  late AboutLocationModel _model;
  final scaffoldKey = GlobalKey<ScaffoldState>();
  final List<String> locationOptions = const ['공공기관','공원/여가시설','길거리','대중교통','마트/편의점','병원/약국','직장','집','카페/식당','학교','기타'];
  bool get showEtcTextField => _model.locationValue == '기타';
  String get selectedLocationSummary {
    if (_model.locationValue == '기타') return _model.textController.text.trim().isEmpty ? '기타' : _model.textController.text.trim();
    return _model.locationValue ?? '';
  }
  @override
  void initState() { super.initState(); _model = createModel(context, () => AboutLocationModel()); _model.textController ??= TextEditingController(); _model.textFieldFocusNode ??= FocusNode(); WidgetsBinding.instance.addPostFrameCallback((_) => safeSetState(() {})); }
  @override
  void dispose() { _model.dispose(); super.dispose(); }

  Widget _dropdown() {
    return FlutterFlowDropDown<String>(
      controller: _model.locationValueController ??= FormFieldController<String>(_model.locationValue),
      options: locationOptions,
      optionLabels: locationOptions,
      onChanged: (val) => safeSetState(() { _model.locationValue = val; if (val != '기타') _model.textController?.clear(); }),
      width: double.infinity,
      height: 52,
      textStyle: pppdText(size: 15),
      hintText: '장소 선택',
      icon: const Icon(Icons.keyboard_arrow_down_rounded, color: PppdColors.muted, size: 24),
      fillColor: Colors.white,
      elevation: 0,
      borderColor: const Color(0xFFE8E0FF),
      borderWidth: 1,
      borderRadius: 18,
      margin: const EdgeInsetsDirectional.fromSTEB(14, 0, 14, 0),
      hidesUnderline: true,
      isOverButton: false,
      isSearchable: false,
      isMultiSelect: false,
    );
  }

  Widget _textField() {
    return TextFormField(
      controller: _model.textController,
      focusNode: _model.textFieldFocusNode,
      onChanged: (_) => safeSetState(() {}),
      decoration: InputDecoration(
        hintText: '추가할 장소의 이름',
        hintStyle: pppdText(size: 14, color: PppdColors.muted),
        filled: true,
        fillColor: Colors.white,
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
        border: OutlineInputBorder(borderRadius: BorderRadius.circular(18), borderSide: const BorderSide(color: Color(0xFFE8E0FF))),
        enabledBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(18), borderSide: const BorderSide(color: Color(0xFFE8E0FF))),
        focusedBorder: OutlineInputBorder(borderRadius: BorderRadius.circular(18), borderSide: const BorderSide(color: PppdColors.purple, width: 1.5)),
      ),
      style: pppdText(size: 15),
      cursorColor: PppdColors.purple,
    );
  }

  Future<void> _handleRegister() async {
    if (_model.locationValue == null || _model.locationValue!.isEmpty || (_model.locationValue == '기타' && _model.textController.text.trim().isEmpty)) {
      await showDialog(context: context, builder: (c) => AlertDialog(title: const Text('장소를 입력해 주세요'), content: const Text('장소를 선택하거나 직접 입력해 주세요.'), actions: [TextButton(onPressed: () => Navigator.pop(c), child: const Text('Ok'))]));
      return;
    }
    await showDialog(context: context, builder: (c) => AlertDialog(title: const Text('장소 등록 완료'), content: Text('등록한 장소: $selectedLocationSummary\n이 장소에서 자주 들리는 소리도 함께 등록해 주세요.'), actions: [TextButton(onPressed: () => Navigator.pop(c), child: const Text('Next'))]));
    context.pushNamed(LocationnSoundRegisterWidget.routeName);
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () { FocusScope.of(context).unfocus(); FocusManager.instance.primaryFocus?.unfocus(); },
      child: PppdScaffold(
        title: '장소 등록',
        subtitle: '자주 방문하는 공간을 선택해요.',
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 10, 20, 28),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            PppdSectionCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('어디에서 소리를 자주 듣나요?', style: pppdText(size: 21, weight: FontWeight.w900)),
              const SizedBox(height: 8),
              Text('장소를 먼저 고르면 다음 화면에서 해당 장소와 관련된 소리를 등록할 수 있어요.', style: pppdText(size: 14, color: PppdColors.muted, height: 1.45)),
              const SizedBox(height: 18),
              _dropdown(),
              if (showEtcTextField) ...[const SizedBox(height: 14), _textField()],
              if (selectedLocationSummary.isNotEmpty) ...[
                const SizedBox(height: 18),
                Container(width: double.infinity, padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: PppdColors.lavender, borderRadius: BorderRadius.circular(18)), child: Text('선택한 장소: $selectedLocationSummary', style: pppdText(size: 14, weight: FontWeight.w800, color: PppdColors.deepPurple))),
              ],
            ])),
            const SizedBox(height: 24),
            PppdPrimaryButton(text: '소리 등록으로 이동', icon: Icons.arrow_forward_rounded, onTap: _handleRegister),
          ]),
        ),
      ),
    );
  }
}
