
import '/flutter_flow/flutter_flow_drop_down.dart';
import '/flutter_flow/flutter_flow_util.dart';
import '/flutter_flow/form_field_controller.dart';
import '/shared/pppd_design.dart';
import 'package:flutter/material.dart';
import 'locationn_sound_register_model.dart';
export 'locationn_sound_register_model.dart';

class LocationnSoundRegisterWidget extends StatefulWidget {
  const LocationnSoundRegisterWidget({super.key});
  static String routeName = 'LocationnSoundRegister';
  static String routePath = '/locationnSoundRegister';
  @override
  State<LocationnSoundRegisterWidget> createState() => _LocationnSoundRegisterWidgetState();
}

class _LocationnSoundRegisterWidgetState extends State<LocationnSoundRegisterWidget> {
  late LocationnSoundRegisterModel _model;
  final scaffoldKey = GlobalKey<ScaffoldState>();

  final Map<String, List<String>> detailOptionsByMainCategory = {
    '사람': ['생후 0~6개월 영아','생후 6~12개월 영아','생후 12~18개월 영아','언어를 구사하는 사람'],
    '동물': ['강아지','고라니','고양이','닭','도마뱀','(멧)돼지','말','소','앵무새','양','염소','코끼리','토끼'],
    '근무': ['공장','연구실','병원/의료기관','사무실','건설 현장','물류창고','주방 / 식품 제조 현장','콜센터/고객지원실','학교/교육기관','항공/교통 관련 근무지'],
    '기타': [],
  };

  final Map<String, List<String>> soundOptionsByWorkplace = {
    '공장': ['경고음','기기 가동 시작음','비상 정지 알림음','컨베이어벨트 작동음','지게차 후진 경고음','압축공기 분사음','금속 충돌음','절단기/프레스 작동음','모터 과부하음','누출음','화재 경보음','작업자 호출 방송'],
    '연구실': ['장비 알람음','원심분리기 종료음','냉장고/초저온고 경고음','가스 누출 경보음','화학 후드 경고음','타이머 알림음','유리기구 깨지는 소리','액체 끓는 소리','펌프 작동음','멸균기 완료음','비상 샤워/세안기 작동음'],
    '병원/의료기관': ['환자 모니터 알람음','호출벨 소리','응급 방송','의료기기 완료음','주사펌프 알람음','산소 공급 장치 소리','휠체어/카트 이동음'],
    '사무실': ['전화벨','메신저 알림음','회의 시작 알림음','보안문 개폐음','화재 경보음','복사기 오류음'],
    '건설 현장': ['크레인 이동 경고음','굴착기 작동음','망치질/드릴 소리','자재 낙하음','안전관리자 호루라기','차량 후진음','비상 경보음'],
    '물류창고': ['바코드 스캔음','지게차 경고음','컨베이어 작동음','포장기계 작동음','재고 알림음','출입문 개폐음','박스 낙하음'],
    '주방 / 식품 제조 현장': ['오븐 타이머음','튀김기 알림음','냉장고 경고음','칼질/도마 소리','식기 깨지는 소리','환풍기 작동음'],
    '콜센터/고객지원실': ['인입 전화 알림음','대기콜 알림음','상담 녹취 시작음','메신저 알림음','시스템 오류음','긴급 공지 알림음'],
    '학교/교육기관': ['수업 시작 종','수업 종료 종','방송 알림음','비상벨','실험실 장비음','학생 호출 방송'],
    '항공/교통 관련 근무지': ['탑승 안내 방송','보안검색대 알림음','차량/열차 출발음','무전기 호출음','엔진 가동음','경고 사이렌'],
  };

  List<String> get detailOptions => _model.mainCategoryValue == null ? [] : detailOptionsByMainCategory[_model.mainCategoryValue] ?? [];
  List<String> get soundDetailOptions => _model.detailCategoryValue == null ? [] : soundOptionsByWorkplace[_model.detailCategoryValue] ?? [];
  bool get showDetailDropdown => _model.mainCategoryValue != null && _model.mainCategoryValue != '기타' && detailOptions.isNotEmpty;
  bool get showSoundDetailDropdown => _model.mainCategoryValue == '근무' && _model.detailCategoryValue != null && soundDetailOptions.isNotEmpty;
  bool get showTextField => _model.mainCategoryValue == '기타';
  String get selectedSoundSummary {
    if (_model.mainCategoryValue == '기타') return _model.textController.text.trim();
    if (_model.mainCategoryValue == '근무') return [_model.mainCategoryValue, _model.detailCategoryValue, _model.soundDetailValue].where((e) => e != null && e!.isNotEmpty).join(' > ');
    return [_model.mainCategoryValue, _model.detailCategoryValue].where((e) => e != null && e!.isNotEmpty).join(' > ');
  }
  bool get canRegister {
    if (_model.mainCategoryValue == null) return false;
    if (_model.mainCategoryValue == '기타') return _model.textController.text.trim().isNotEmpty;
    if (_model.mainCategoryValue == '근무') return _model.detailCategoryValue != null && _model.soundDetailValue != null;
    return _model.detailCategoryValue != null;
  }

  @override
  void initState() { super.initState(); _model = createModel(context, () => LocationnSoundRegisterModel()); _model.textController ??= TextEditingController(); _model.textFieldFocusNode ??= FocusNode(); WidgetsBinding.instance.addPostFrameCallback((_) => safeSetState(() {})); }
  @override
  void dispose() { _model.dispose(); super.dispose(); }

  Widget _dropdown({required String hintText, required FormFieldController<String>? controller, required List<String> options, required void Function(String?) onChanged}) {
    return FlutterFlowDropDown<String>(
      controller: controller,
      options: options,
      optionLabels: options,
      onChanged: onChanged,
      width: double.infinity,
      height: 52,
      textStyle: pppdText(size: 15),
      hintText: hintText,
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
        hintText: '추가할 소리의 이름',
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
    if (!canRegister) {
      await showDialog(context: context, builder: (c) => AlertDialog(title: const Text('소리를 선택해 주세요'), content: const Text('등록할 소리 정보를 모두 선택하거나 입력해 주세요.'), actions: [TextButton(onPressed: () => Navigator.pop(c), child: const Text('Ok'))]));
      return;
    }
    await showDialog(context: context, builder: (c) => AlertDialog(title: const Text('등록 완료'), content: Text(selectedSoundSummary), actions: [TextButton(onPressed: () => Navigator.pop(c), child: const Text('Ok'))]));
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () { FocusScope.of(context).unfocus(); FocusManager.instance.primaryFocus?.unfocus(); },
      child: PppdScaffold(
        title: '장소별 소리 등록',
        subtitle: '이 장소에서 자주 들리는 소리를 선택해요.',
        child: SingleChildScrollView(
          padding: const EdgeInsets.fromLTRB(20, 10, 20, 28),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            PppdSectionCard(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('어떤 소리를 등록할까요?', style: pppdText(size: 21, weight: FontWeight.w900)),
              const SizedBox(height: 8),
              Text('큰 분류를 먼저 고르고, 근무를 선택한 경우 장소와 자주 들리는 소리를 이어서 선택해 주세요.', style: pppdText(size: 14, color: PppdColors.muted, height: 1.45)),
              const SizedBox(height: 18),
              _dropdown(hintText: '큰 분류 선택', controller: _model.mainCategoryValueController ??= FormFieldController<String>(_model.mainCategoryValue), options: const ['사람','동물','근무','기타'], onChanged: (val) => safeSetState(() { _model.mainCategoryValue = val; _model.detailCategoryValue = null; _model.detailCategoryValueController = null; _model.soundDetailValue = null; _model.soundDetailValueController = null; _model.textController?.clear(); })),
              if (showDetailDropdown) ...[const SizedBox(height: 14), _dropdown(hintText: _model.mainCategoryValue == '근무' ? '근무 장소 선택' : '세부 옵션 선택', controller: _model.detailCategoryValueController ??= FormFieldController<String>(_model.detailCategoryValue), options: detailOptions, onChanged: (val) => safeSetState(() { _model.detailCategoryValue = val; _model.soundDetailValue = null; _model.soundDetailValueController = null; }))],
              if (showSoundDetailDropdown) ...[const SizedBox(height: 14), Text('이 장소에서 특히 어떤 소리가 자주 들리나요?', style: pppdText(size: 14, weight: FontWeight.w800)), const SizedBox(height: 8), _dropdown(hintText: '자주 들리는 소리 선택', controller: _model.soundDetailValueController ??= FormFieldController<String>(_model.soundDetailValue), options: soundDetailOptions, onChanged: (val) => safeSetState(() { _model.soundDetailValue = val; }))],
              if (showTextField) ...[const SizedBox(height: 14), _textField()],
              if (selectedSoundSummary.isNotEmpty) ...[const SizedBox(height: 18), Container(width: double.infinity, padding: const EdgeInsets.all(14), decoration: BoxDecoration(color: PppdColors.lavender, borderRadius: BorderRadius.circular(18)), child: Text('선택한 소리: $selectedSoundSummary', style: pppdText(size: 14, weight: FontWeight.w800, color: PppdColors.deepPurple)))],
            ])),
            const SizedBox(height: 24),
            PppdPrimaryButton(text: '등록', icon: Icons.check_rounded, onTap: _handleRegister),
          ]),
        ),
      ),
    );
  }
}
