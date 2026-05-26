import '/backend/backend.dart';
import '/flutter_flow/flutter_flow_google_map.dart';
import '/flutter_flow/flutter_flow_theme.dart';
import '/flutter_flow/flutter_flow_util.dart';
import 'dart:async';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart' as gm;
import 'map_model.dart';
export 'map_model.dart';

class MapWidget extends StatefulWidget {
  const MapWidget({super.key});

  static String routeName = 'map';
  static String routePath = '/map';

  @override
  State<MapWidget> createState() => _MapWidgetState();
}

class _MapWidgetState extends State<MapWidget> {
  late MapModel _model;

  final scaffoldKey = GlobalKey<ScaffoldState>();

  LatLng? _currentUserLocation;
  StreamSubscription<Position>? _positionSubscription;
  String _locationStatus = '위치 추적 준비 중...';

  @override
  void initState() {
    super.initState();
    _model = createModel(context, () => MapModel());

    WidgetsBinding.instance.addPostFrameCallback((_) {
      safeSetState(() {});
      _startLiveLocationTracking();
    });
  }

  @override
  void dispose() {
    _positionSubscription?.cancel();
    _model.dispose();

    super.dispose();
  }

  Future<bool> _ensureLocationPermission() async {
    final serviceEnabled = await Geolocator.isLocationServiceEnabled();

    if (!serviceEnabled) {
      if (mounted) {
        setState(() {
          _locationStatus = '기기 위치 서비스가 꺼져 있습니다.';
        });
      }
      return false;
    }

    var permission = await Geolocator.checkPermission();

    if (permission == LocationPermission.denied) {
      permission = await Geolocator.requestPermission();
    }

    if (permission == LocationPermission.denied) {
      if (mounted) {
        setState(() {
          _locationStatus = '위치 권한이 거부되었습니다.';
        });
      }
      return false;
    }

    if (permission == LocationPermission.deniedForever) {
      if (mounted) {
        setState(() {
          _locationStatus = '위치 권한이 영구적으로 거부되었습니다. 설정에서 권한을 허용해야 합니다.';
        });
      }
      return false;
    }

    return true;
  }

  Future<void> _moveCameraTo(LatLng location) async {
    try {
      final controller = await _model.googleMapsController.future;

      await controller.animateCamera(
        gm.CameraUpdate.newLatLngZoom(
          gm.LatLng(location.latitude, location.longitude),
          17.0,
        ),
      );
    } catch (e) {
      debugPrint('Move camera failed: $e');
    }
  }

  Future<void> _setCurrentLocation(
    Position position, {
    bool moveCamera = false,
  }) async {
    final location = LatLng(position.latitude, position.longitude);

    if (!mounted) return;

    setState(() {
      _currentUserLocation = location;
      _model.googleMapsCenter = location;
      _locationStatus =
          '현재 위치: ${location.latitude.toStringAsFixed(6)}, ${location.longitude.toStringAsFixed(6)}';
    });

    if (moveCamera) {
      await _moveCameraTo(location);
    }
  }

  Future<void> _startLiveLocationTracking() async {
    final hasPermission = await _ensureLocationPermission();

    if (!hasPermission) {
      return;
    }

    try {
      if (mounted) {
        setState(() {
          _locationStatus = '현재 위치를 가져오는 중...';
        });
      }

      final firstPosition = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
      );

      await _setCurrentLocation(firstPosition, moveCamera: true);

      const locationSettings = LocationSettings(
        accuracy: LocationAccuracy.high,
        distanceFilter: 2,
      );

      await _positionSubscription?.cancel();

      _positionSubscription = Geolocator.getPositionStream(
        locationSettings: locationSettings,
      ).listen(
        (position) async {
          await _setCurrentLocation(position, moveCamera: true);
        },
        onError: (error) {
          if (!mounted) return;

          setState(() {
            _locationStatus = '위치 스트림 오류: $error';
          });
        },
      );
    } catch (e) {
      if (!mounted) return;

      setState(() {
        _locationStatus = '현재 위치를 가져오지 못했습니다: $e';
      });
    }
  }

  List<FlutterFlowMarker> _buildMarkers(List<UsersRecord> users) {
    final firestoreMarkers = users
        .map((e) => e.currentLocation)
        .withoutNulls
        .toList()
        .map(
          (marker) => FlutterFlowMarker(
            marker.serialize(),
            marker,
          ),
        )
        .toList();

    final currentUserMarker = _currentUserLocation == null
        ? <FlutterFlowMarker>[]
        : [
            FlutterFlowMarker(
              'current_user_location',
              _currentUserLocation!,
            ),
          ];

    return [
      ...firestoreMarkers,
      ...currentUserMarker,
    ];
  }

  Widget _buildMap(List<UsersRecord> users) {
    return Stack(
      children: [
        FlutterFlowGoogleMap(
          controller: _model.googleMapsController,
          onCameraIdle: (latLng) => _model.googleMapsCenter = latLng,
          initialLocation: _currentUserLocation ??
              _model.googleMapsCenter ??
              LatLng(36.014561, 129.320973),
          markers: _buildMarkers(users),
          markerColor: GoogleMarkerColor.violet,
          mapType: MapType.hybrid,
          style: GoogleMapStyle.standard,
          initialZoom: 15.0,
          allowInteraction: true,
          allowZoom: true,
          showZoomControls: true,
          showLocation: true,
          showCompass: false,
          showMapToolbar: false,
          showTraffic: false,
          centerMapOnMarkerTap: true,
          mapTakesGesturePreference: false,
        ),
        Positioned(
          top: 12.0,
          left: 12.0,
          right: 12.0,
          child: Container(
            padding: const EdgeInsets.all(12.0),
            decoration: BoxDecoration(
              color: Colors.white.withOpacity(0.92),
              borderRadius: BorderRadius.circular(8.0),
              boxShadow: const [
                BoxShadow(
                  blurRadius: 8.0,
                  offset: Offset(0, 2),
                  color: Color(0x33000000),
                ),
              ],
            ),
            child: Text(
              _locationStatus,
              style: const TextStyle(
                color: Colors.black,
                fontSize: 13.0,
                fontWeight: FontWeight.w500,
              ),
            ),
          ),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: () {
        FocusScope.of(context).unfocus();
        FocusManager.instance.primaryFocus?.unfocus();
      },
      child: Scaffold(
        key: scaffoldKey,
        resizeToAvoidBottomInset: false,
        backgroundColor: FlutterFlowTheme.of(context).primaryBackground,
        appBar: AppBar(
          backgroundColor: FlutterFlowTheme.of(context).primary,
          automaticallyImplyLeading: false,
          title: Text(
            'Map',
            style: FlutterFlowTheme.of(context).headlineMedium.override(
                  font: GoogleFonts.interTight(
                    fontWeight:
                        FlutterFlowTheme.of(context).headlineMedium.fontWeight,
                    fontStyle:
                        FlutterFlowTheme.of(context).headlineMedium.fontStyle,
                  ),
                  color: Colors.white,
                  fontSize: 22.0,
                  letterSpacing: 0.0,
                  fontWeight:
                      FlutterFlowTheme.of(context).headlineMedium.fontWeight,
                  fontStyle:
                      FlutterFlowTheme.of(context).headlineMedium.fontStyle,
                ),
          ),
          actions: [],
          centerTitle: false,
          elevation: 2.0,
        ),
        body: SafeArea(
          top: true,
          child: FutureBuilder<List<UsersRecord>>(
            future: queryUsersRecordOnce(),
            builder: (context, snapshot) {
              if (snapshot.hasError) {
                debugPrint('Users query failed: ${snapshot.error}');
                return _buildMap(const <UsersRecord>[]);
              }

              if (!snapshot.hasData) {
                return _buildMap(const <UsersRecord>[]);
              }

              return _buildMap(snapshot.data!);
            },
          ),
        ),
      ),
    );
  }
}
