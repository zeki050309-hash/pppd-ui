import '/flutter_flow/flutter_flow_util.dart';
import '/flutter_flow/form_field_controller.dart';
import 'locationn_sound_register_widget.dart' show LocationnSoundRegisterWidget;
import 'package:flutter/material.dart';

class LocationnSoundRegisterModel extends FlutterFlowModel<LocationnSoundRegisterWidget> {
  String? mainCategoryValue;
  FormFieldController<String>? mainCategoryValueController;
  String? detailCategoryValue;
  FormFieldController<String>? detailCategoryValueController;
  String? soundDetailValue;
  FormFieldController<String>? soundDetailValueController;
  FocusNode? textFieldFocusNode;
  TextEditingController? textController;
  String? Function(BuildContext, String?)? textControllerValidator;
  @override
  void initState(BuildContext context) {}
  @override
  void dispose() { textFieldFocusNode?.dispose(); textController?.dispose(); }
}
