import 'dart:convert';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:intl/intl.dart';
import 'package:timeago/timeago.dart' as timeago;
import 'lat_lng.dart';
import 'place.dart';
import 'uploaded_file.dart';
import '/backend/backend.dart';
import 'package:cloud_firestore/cloud_firestore.dart';

LatLng? getUsersLocation(LatLng userslocation) {
  if (userslocation == null ||
      (userslocation.latitude == 0 && userslocation.longitude == 0)) {
    return LatLng(36.014561, 129.320973);
  }

  return userslocation;
}
