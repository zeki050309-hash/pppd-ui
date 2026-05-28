
import '/flutter_flow/flutter_flow_util.dart';
import '/flutter_flow/form_field_controller.dart';
import '/index.dart';
import 'about_location_widget.dart' show AboutLocationWidget;
import 'package:flutter/material.dart';

class AboutLocationModel extends FlutterFlowModel<AboutLocationWidget> {
  String? locationValue;
  FormFieldController<String>? locationValueController;
  FocusNode? textFieldFocusNode;
  TextEditingController? textController;
  String? Function(BuildContext, String?)? textControllerValidator;
  @override
  void initState(BuildContext context) {}
  @override
  void dispose() { textFieldFocusNode?.dispose(); textController?.dispose(); }
}
