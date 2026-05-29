import '/backend/backend.dart';
import '/flutter_flow/flutter_flow_theme.dart';
import '/flutter_flow/flutter_flow_util.dart';
import '/services/location_context_service.dart';
import '/shared/pppd_design.dart';
import 'dart:async';
import 'package:cloud_firestore/cloud_firestore.dart';
import 'package:flutter/material.dart';
import 'package:geolocator/geolocator.dart';
import 'package:google_fonts/google_fonts.dart';
import 'package:google_maps_flutter/google_maps_flutter.dart' as gm;
import 'package:provider/provider.dart';
import 'map_model.dart';
export 'map_model.dart';

class MapWidget extends StatefulWidget {
  const MapWidget({super.key});

  static String routeName = 'map';
  static String routePath = '/map';

  @override
  State<MapWidget> createState() => _MapWidgetState();
}

class _DangerPlace {
  const _DangerPlace({
    required this.id,
    required this.name,
    required this.position,
    required this.dangerLevel,
    required this.description,
  });

  final String id;
  final String name;
  final gm.LatLng position;
  final String dangerLevel;
  final String description;
}

class _MapWidgetState extends State<MapWidget> {
  late MapModel _model;

  final scaffoldKey = GlobalKey<ScaffoldState>();
  gm.GoogleMapController? _mapController;
  StreamSubscription<Position>? _positionSubscription;
  final TextEditingController _searchController = TextEditingController();
  final FocusNode _searchFocusNode = FocusNode();

  gm.LatLng? _currentUserLocation;
  gm.BitmapDescriptor? _butterflyIcon;
  List<UsersRecord> _users = [];
  List<_DangerPlace> _dangerPlaces = [];
  _DangerPlace? _selectedDangerPlace;
  String _locationStatus = '위치 추적 준비 중...';
  gm.LatLng? _searchResultLocation;
  String? _searchResultName;
  bool _isSearchingGooglePlace = false;
  bool _isLoadingPlaces = true;
  bool _showUserMarkers = true;
  bool _showDangerMarkers = true;
  String _searchQuery = '';

  static const gm.LatLng _fallbackLocation = gm.LatLng(36.014561, 129.320973);
  static const Color _primaryPurple = Color(0xFF6F3EE8);
  static const Color _darkPurple = Color(0xFF251344);
  static const Color _softPurple = Color(0xFFF4EFFF);
  static const String _googleMapsApiKey =
      'AIzaSyAtyMxOY64odIcwiBJu4WX9LKbvDw-J-dM';

  @override
  void initState() {
    super.initState();
    _model = createModel(context, () => MapModel());

    WidgetsBinding.instance.addPostFrameCallback((_) async {
      safeSetState(() {});
      await _loadButterflyIcon();
      await _loadMapData();
      await _startLiveLocationTracking();
    });
  }

  @override
  void dispose() {
    _positionSubscription?.cancel();
    _searchController.dispose();
    _searchFocusNode.dispose();
    _mapController?.dispose();
    _model.dispose();
    super.dispose();
  }

  Future<void> _loadButterflyIcon() async {
    try {
      final icon = await gm.BitmapDescriptor.fromAssetImage(
        const ImageConfiguration(size: Size(56.0, 56.0)),
        'assets/images/pppd_butterfly.png',
      );

      if (!mounted) return;
      setState(() {
        _butterflyIcon = icon;
      });
    } catch (e) {
      debugPrint('Failed to load butterfly marker image: $e');
    }
  }

  Future<void> _loadMapData() async {
    if (!mounted) return;

    setState(() {
      _isLoadingPlaces = true;
    });

    try {
      final results = await Future.wait([
        queryUsersRecordOnce(),
        FirebaseFirestore.instance.collection('danger_places').get(),
      ]);

      final users = results[0] as List<UsersRecord>;
      final dangerSnapshot = results[1] as QuerySnapshot<Map<String, dynamic>>;
      final dangerPlaces = dangerSnapshot.docs
          .map(_dangerPlaceFromDoc)
          .whereType<_DangerPlace>()
          .toList();

      if (!mounted) return;

      setState(() {
        _users = users;
        _dangerPlaces = dangerPlaces;
        if (_selectedDangerPlace != null &&
            !_dangerPlaces.any((e) => e.id == _selectedDangerPlace!.id)) {
          _selectedDangerPlace = null;
        }
        _isLoadingPlaces = false;
      });
    } catch (e) {
      debugPrint('Failed to load map data: $e');
      if (!mounted) return;
      setState(() {
        _isLoadingPlaces = false;
      });
    }
  }

  _DangerPlace? _dangerPlaceFromDoc(
    QueryDocumentSnapshot<Map<String, dynamic>> doc,
  ) {
    final data = doc.data();
    final position = _readLatLng(data);

    if (position == null) {
      debugPrint('danger_places/${doc.id} has no valid location.');
      return null;
    }

    return _DangerPlace(
      id: doc.id,
      name: _readString(
        data,
        const ['place_name', 'placeName', 'name', 'title'],
        '위험 장소',
      ),
      position: position,
      dangerLevel: _readString(
        data,
        const ['danger_level', 'dangerLevel', 'risk_level', 'riskLevel'],
        'Unknown',
      ),
      description: _readString(
        data,
        const ['description', 'desc', 'memo', 'note'],
        '상세 설명이 없습니다.',
      ),
    );
  }

  gm.LatLng? _readLatLng(Map<String, dynamic> data) {
    final location = data['location'];
    if (location is GeoPoint) {
      return gm.LatLng(location.latitude, location.longitude);
    }

    final latitude = data['latitude'] ?? data['lat'];
    final longitude = data['longitude'] ?? data['lng'] ?? data['lon'];

    if (latitude is num && longitude is num) {
      return gm.LatLng(latitude.toDouble(), longitude.toDouble());
    }

    return null;
  }

  String _readString(
    Map<String, dynamic> data,
    List<String> keys,
    String fallback,
  ) {
    for (final key in keys) {
      final value = data[key];
      if (value is String && value.trim().isNotEmpty) {
        return value.trim();
      }
    }
    return fallback;
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
          _locationStatus = '위치 권한이 영구적으로 거부되었습니다. 설정에서 권한을 허용해 주세요.';
        });
      }
      return false;
    }

    return true;
  }

  Future<void> _startLiveLocationTracking() async {
    final hasPermission = await _ensureLocationPermission();

    if (!hasPermission) {
      return;
    }

    if (mounted) {
      setState(() {
        _locationStatus = '현재 위치를 확인하는 중...';
      });
    }

    // 1) 브라우저/기기에서 마지막으로 알고 있던 위치를 먼저 사용한다.
    // Chrome 웹에서 getPositionStream이 불안정할 때도 지도에 우선 표시할 수 있다.
    try {
      final lastKnownPosition = await Geolocator.getLastKnownPosition();
      if (lastKnownPosition != null) {
        await _setCurrentLocation(lastKnownPosition, moveCamera: true);
      }
    } catch (e) {
      debugPrint('Last known position unavailable: $e');
    }

    // 2) 현재 위치 1회 조회. 실패하더라도 기존 위치가 있으면 지우지 않는다.
    try {
      final firstPosition = await Geolocator.getCurrentPosition(
        desiredAccuracy: LocationAccuracy.high,
        timeLimit: const Duration(seconds: 12),
      );
      await _setCurrentLocation(firstPosition, moveCamera: true);
    } catch (e) {
      debugPrint('Current position unavailable: $e');

      if (mounted && _currentUserLocation == null) {
        setState(() {
          _locationStatus =
              '현재 위치를 바로 가져오지 못했습니다. 위치 버튼을 다시 눌러주세요.';
        });
      }
    }

    // 3) 위치 스트림은 보조 업데이트용. 웹에서 unavailable이 나도 앱 상태를 깨지 않게 처리한다.
    const locationSettings = LocationSettings(
      accuracy: LocationAccuracy.high,
      distanceFilter: 2,
    );

    await _positionSubscription?.cancel();

    _positionSubscription = Geolocator.getPositionStream(
      locationSettings: locationSettings,
    ).listen(
      (position) async {
        await _setCurrentLocation(position, moveCamera: false);
      },
      onError: (error) {
        debugPrint('Position stream unavailable: $error');
        if (!mounted) return;

        if (_currentUserLocation == null) {
          setState(() {
            _locationStatus = '실시간 위치 업데이트를 사용할 수 없습니다.';
          });
        } else {
          setState(() {
            _locationStatus =
                '현재 위치 표시 중 · 실시간 업데이트는 일시적으로 불안정합니다.';
          });
        }
      },
    );
  }

  Future<void> _setCurrentLocation(
    Position position, {
    bool moveCamera = false,
  }) async {
    final location = gm.LatLng(position.latitude, position.longitude);

    if (!mounted) return;

    setState(() {
      _currentUserLocation = location;
      _locationStatus =
          '현재 위치: ${location.latitude.toStringAsFixed(6)}, ${location.longitude.toStringAsFixed(6)}';
    });

    if (moveCamera) {
      await _moveCameraTo(location, zoom: 17.0);
    }
  }

  Future<void> _moveCameraTo(gm.LatLng location, {double zoom = 16.0}) async {
    try {
      await _mapController?.animateCamera(
        gm.CameraUpdate.newLatLngZoom(location, zoom),
      );
    } catch (e) {
      debugPrint('Move camera failed: $e');
    }
  }


  Future<void> _searchDangerPlacesLocally() async {
    final query = _searchController.text.trim();
    if (query.isEmpty) {
      setState(() {
        _searchQuery = '';
        _searchResultLocation = null;
        _searchResultName = null;
        _selectedDangerPlace = null;
      });
      return;
    }

    setState(() {
      _isSearchingGooglePlace = false;
      _searchQuery = query;
      _searchResultLocation = null;
      _searchResultName = null;
    });
  }

  List<_DangerPlace> get _visibleDangerPlaces {
    final query = _searchQuery.trim().toLowerCase();
    if (query.isEmpty) {
      return _dangerPlaces;
    }

    return _dangerPlaces.where((place) {
      return place.name.toLowerCase().contains(query) ||
          place.description.toLowerCase().contains(query) ||
          place.dangerLevel.toLowerCase().contains(query);
    }).toList();
  }

  Future<void> _focusFirstSearchResult() async {
    await _searchDangerPlacesLocally();

    // Firestore danger_places 내부 검색 결과로 이동한다.
    if (_searchResultLocation != null) {
      return;
    }

    final results = _visibleDangerPlaces;
    if (results.isEmpty) {
      setState(() => _selectedDangerPlace = null);
      return;
    }

    final first = results.first;
    setState(() => _selectedDangerPlace = first);
    await _moveCameraTo(first.position, zoom: 17.0);
  }

  void _clearSearch() {
    _searchController.clear();
    setState(() {
      _searchQuery = '';
      _selectedDangerPlace = null;
      _searchResultLocation = null;
      _searchResultName = null;
    });
  }

  Set<gm.Marker> get _markers {
    final markers = <gm.Marker>{};

    if (_showUserMarkers) {
      if (_currentUserLocation != null) {
        markers.add(
          gm.Marker(
            markerId: const gm.MarkerId('current_user_location'),
            position: _currentUserLocation!,
            icon: gm.BitmapDescriptor.defaultMarkerWithHue(
              gm.BitmapDescriptor.hueAzure,
            ),
            infoWindow: const gm.InfoWindow(
              title: '내 현재 위치',
              snippet: '실시간 위치 추적 중',
            ),
          ),
        );
      }

      for (final user in _users) {
        final location = user.currentLocation;
        if (location == null) continue;

        markers.add(
          gm.Marker(
            markerId: gm.MarkerId('user_${user.reference.id}'),
            position: gm.LatLng(location.latitude, location.longitude),
            icon: gm.BitmapDescriptor.defaultMarkerWithHue(
              gm.BitmapDescriptor.hueViolet,
            ),
            infoWindow: const gm.InfoWindow(
              title: '사용자 위치',
              snippet: 'Firestore users.currentLocation',
            ),
          ),
        );
      }
    }

    if (_showDangerMarkers) {
      for (final place in _visibleDangerPlaces) {
        markers.add(
          gm.Marker(
            markerId: gm.MarkerId('danger_${place.id}'),
            position: place.position,
            icon: _butterflyIcon ??
                gm.BitmapDescriptor.defaultMarkerWithHue(
                  gm.BitmapDescriptor.hueRose,
                ),
            infoWindow: gm.InfoWindow(
              title: place.name,
              snippet: '위험도: ${place.dangerLevel}',
            ),
            onTap: () {
              setState(() {
                _selectedDangerPlace = place;
              });
            },
          ),
        );
      }
    }

    if (_searchResultLocation != null) {
      markers.add(
        gm.Marker(
          markerId: const gm.MarkerId('google_place_search_result'),
          position: _searchResultLocation!,
          icon: gm.BitmapDescriptor.defaultMarkerWithHue(
            gm.BitmapDescriptor.hueGreen,
          ),
          infoWindow: gm.InfoWindow(
            title: _searchResultName ?? '검색 결과',
            snippet: '검색 결과',
          ),
        ),
      );
    }

    return markers;
  }

  _DangerPlace? get _featuredDangerPlace {
    if (_selectedDangerPlace != null) {
      return _selectedDangerPlace;
    }
    final visiblePlaces = _visibleDangerPlaces;
    if (visiblePlaces.isNotEmpty) {
      return visiblePlaces.first;
    }
    return null;
  }

  Color _dangerColor(String level) {
    final normalized = level.toLowerCase();
    if (normalized.contains('critical') || normalized.contains('매우')) {
      return const Color(0xFFE53935);
    }
    if (normalized.contains('high') || normalized.contains('높')) {
      return const Color(0xFFFF5252);
    }
    if (normalized.contains('medium') || normalized.contains('보통')) {
      return const Color(0xFFFF9800);
    }
    if (normalized.contains('low') || normalized.contains('낮')) {
      return const Color(0xFFFFC107);
    }
    return _primaryPurple;
  }

  String _dangerLabel(String level) {
    final normalized = level.toLowerCase();
    if (normalized.contains('critical') || normalized.contains('매우')) {
      return '위험 매우 높음';
    }
    if (normalized.contains('high') || normalized.contains('높')) {
      return '위험 높음';
    }
    if (normalized.contains('medium') || normalized.contains('보통')) {
      return '위험 보통';
    }
    if (normalized.contains('low') || normalized.contains('낮')) {
      return '위험 낮음';
    }
    return level == 'Unknown' ? '위험도 미정' : level;
  }

  Widget _buildSearchBar() {
    return Container(
      padding: const EdgeInsetsDirectional.fromSTEB(14.0, 8.0, 10.0, 8.0),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.96),
        borderRadius: BorderRadius.circular(18.0),
        boxShadow: const [
          BoxShadow(
            blurRadius: 18.0,
            offset: Offset(0, 8),
            color: Color(0x22000000),
          ),
        ],
      ),
      child: Row(
        children: [
          const Icon(
            Icons.search_rounded,
            color: Color(0xFF7A7390),
            size: 22.0,
          ),
          const SizedBox(width: 10.0),
          Expanded(
            child: TextField(
              controller: _searchController,
              focusNode: _searchFocusNode,
              textInputAction: TextInputAction.search,
              onChanged: (value) {
                setState(() {
                  _searchQuery = value;
                  if (_selectedDangerPlace != null &&
                      !_visibleDangerPlaces
                          .any((place) => place.id == _selectedDangerPlace!.id)) {
                    _selectedDangerPlace = null;
                  }
                });
              },
              onSubmitted: (_) => _focusFirstSearchResult(),
              decoration: const InputDecoration(
                hintText: 'Google Maps 장소 검색',
                border: InputBorder.none,
                isDense: true,
                contentPadding: EdgeInsets.zero,
              ),
              style: FlutterFlowTheme.of(context).bodyMedium.override(
                    font: GoogleFonts.inter(),
                    color: _darkPurple,
                    letterSpacing: 0.0,
                  ),
            ),
          ),
          if (_searchQuery.isNotEmpty)
            InkWell(
              onTap: _clearSearch,
              borderRadius: BorderRadius.circular(14.0),
              child: Container(
                width: 34.0,
                height: 34.0,
                decoration: BoxDecoration(
                  color: const Color(0xFFF5F2FA),
                  borderRadius: BorderRadius.circular(14.0),
                ),
                child: const Icon(
                  Icons.close_rounded,
                  color: Color(0xFF7A7390),
                  size: 20.0,
                ),
              ),
            ),
          const SizedBox(width: 6.0),
          InkWell(
            onTap: () async {
              if (_searchQuery.trim().isNotEmpty) {
                await _focusFirstSearchResult();
              } else {
                await _loadMapData();
              }
            },
            borderRadius: BorderRadius.circular(14.0),
            child: Container(
              width: 38.0,
              height: 38.0,
              decoration: BoxDecoration(
                color: _softPurple,
                borderRadius: BorderRadius.circular(14.0),
              ),
              child: (_isLoadingPlaces || _isSearchingGooglePlace)
                  ? const Padding(
                      padding: EdgeInsets.all(10.0),
                      child: CircularProgressIndicator(strokeWidth: 2.0),
                    )
                  : Icon(
                      _searchQuery.trim().isNotEmpty
                          ? Icons.arrow_forward_rounded
                          : Icons.refresh_rounded,
                      color: _primaryPurple,
                      size: 21.0,
                    ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFilterPanel() {
    return Container(
      padding: const EdgeInsets.all(10.0),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.94),
        borderRadius: BorderRadius.circular(18.0),
        boxShadow: const [
          BoxShadow(
            blurRadius: 16.0,
            offset: Offset(0, 8),
            color: Color(0x1F000000),
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          _buildToggleChip(
            label: '사용자',
            icon: Icons.person_pin_circle_rounded,
            selected: _showUserMarkers,
            onTap: () => setState(() => _showUserMarkers = !_showUserMarkers),
          ),
          const SizedBox(width: 8.0),
          _buildToggleChip(
            label: '위험 장소',
            icon: Icons.flutter_dash_rounded,
            selected: _showDangerMarkers,
            onTap: () => setState(() => _showDangerMarkers = !_showDangerMarkers),
          ),
        ],
      ),
    );
  }

  Widget _buildToggleChip({
    required String label,
    required IconData icon,
    required bool selected,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(999.0),
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 180),
        padding: const EdgeInsetsDirectional.fromSTEB(10.0, 8.0, 12.0, 8.0),
        decoration: BoxDecoration(
          color: selected ? _primaryPurple : const Color(0xFFF5F2FA),
          borderRadius: BorderRadius.circular(999.0),
        ),
        child: Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              icon,
              size: 16.0,
              color: selected ? Colors.white : _primaryPurple,
            ),
            const SizedBox(width: 5.0),
            Text(
              label,
              style: FlutterFlowTheme.of(context).labelMedium.override(
                    font: GoogleFonts.inter(
                      fontWeight: FontWeight.w700,
                    ),
                    color: selected ? Colors.white : _darkPurple,
                    letterSpacing: 0.0,
                  ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildFloatingControls() {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        _buildMapControlButton(
          icon: Icons.my_location_rounded,
          onTap: () async {
            if (_currentUserLocation != null) {
              await _moveCameraTo(_currentUserLocation!, zoom: 17.0);
            } else {
              await _startLiveLocationTracking();
            }
          },
        ),
        const SizedBox(height: 10.0),
        _buildMapControlButton(
          icon: Icons.add_rounded,
          onTap: () async {
            await _mapController?.animateCamera(gm.CameraUpdate.zoomIn());
          },
        ),
        const SizedBox(height: 8.0),
        _buildMapControlButton(
          icon: Icons.remove_rounded,
          onTap: () async {
            await _mapController?.animateCamera(gm.CameraUpdate.zoomOut());
          },
        ),
      ],
    );
  }

  Widget _buildMapControlButton({
    required IconData icon,
    required VoidCallback onTap,
  }) {
    return InkWell(
      onTap: onTap,
      borderRadius: BorderRadius.circular(14.0),
      child: Container(
        width: 46.0,
        height: 46.0,
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.96),
          borderRadius: BorderRadius.circular(14.0),
          boxShadow: const [
            BoxShadow(
              blurRadius: 12.0,
              offset: Offset(0, 5),
              color: Color(0x22000000),
            ),
          ],
        ),
        child: Icon(
          icon,
          color: _darkPurple,
          size: 22.0,
        ),
      ),
    );
  }

  Widget _buildStatusPill() {
    return Container(
      padding: const EdgeInsetsDirectional.fromSTEB(12.0, 8.0, 12.0, 8.0),
      decoration: BoxDecoration(
        color: Colors.white.withOpacity(0.94),
        borderRadius: BorderRadius.circular(999.0),
        boxShadow: const [
          BoxShadow(
            blurRadius: 14.0,
            offset: Offset(0, 6),
            color: Color(0x1A000000),
          ),
        ],
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          Container(
            width: 8.0,
            height: 8.0,
            decoration: const BoxDecoration(
              color: Color(0xFF2F80ED),
              shape: BoxShape.circle,
            ),
          ),
          const SizedBox(width: 7.0),
          Flexible(
            child: Text(
              _locationStatus,
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: FlutterFlowTheme.of(context).labelMedium.override(
                    font: GoogleFonts.inter(
                      fontWeight: FontWeight.w600,
                    ),
                    color: _darkPurple,
                    letterSpacing: 0.0,
                  ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildBottomDangerCard() {
    final place = _featuredDangerPlace;

    if (place == null) {
      return Container(
        padding: const EdgeInsets.all(18.0),
        decoration: _bottomCardDecoration(),
        child: Row(
          children: [
            _buildButterflyBadge(),
            const SizedBox(width: 14.0),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                mainAxisSize: MainAxisSize.min,
                children: [
                  Text(
                    '표시할 위험 장소가 없습니다',
                    style: FlutterFlowTheme.of(context).titleSmall.override(
                          font: GoogleFonts.interTight(
                            fontWeight: FontWeight.w800,
                          ),
                          color: _darkPurple,
                          letterSpacing: 0.0,
                        ),
                  ),
                  const SizedBox(height: 4.0),
                  Text(
                    'Firestore의 danger_places 컬렉션에 데이터를 추가해 주세요.',
                    style: FlutterFlowTheme.of(context).bodySmall.override(
                          font: GoogleFonts.inter(),
                          color: const Color(0xFF7A7390),
                          letterSpacing: 0.0,
                        ),
                  ),
                ],
              ),
            ),
          ],
        ),
      );
    }

    final color = _dangerColor(place.dangerLevel);

    return Container(
      padding: const EdgeInsets.all(18.0),
      decoration: _bottomCardDecoration(),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              _buildButterflyBadge(color: color),
              const SizedBox(width: 14.0),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      place.name,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: FlutterFlowTheme.of(context).titleMedium.override(
                            font: GoogleFonts.interTight(
                              fontWeight: FontWeight.w800,
                            ),
                            color: _darkPurple,
                            letterSpacing: 0.0,
                          ),
                    ),
                    const SizedBox(height: 4.0),
                    Text(
                      place.description,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: FlutterFlowTheme.of(context).bodySmall.override(
                            font: GoogleFonts.inter(),
                            color: const Color(0xFF7A7390),
                            letterSpacing: 0.0,
                          ),
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 10.0),
              _buildDangerBadge(place.dangerLevel),
            ],
          ),
          const SizedBox(height: 14.0),
          Row(
            children: [
              Expanded(
                child: Text(
                  '위험 장소 ${_visibleDangerPlaces.length}개 · 사용자 위치 ${_users.where((e) => e.currentLocation != null).length + (_currentUserLocation != null ? 1 : 0)}개',
                  style: FlutterFlowTheme.of(context).labelMedium.override(
                        font: GoogleFonts.inter(
                          fontWeight: FontWeight.w600,
                        ),
                        color: const Color(0xFF7A7390),
                        letterSpacing: 0.0,
                      ),
                ),
              ),
              InkWell(
                onTap: () => _moveCameraTo(place.position, zoom: 17.0),
                borderRadius: BorderRadius.circular(999.0),
                child: Container(
                  padding:
                      const EdgeInsetsDirectional.fromSTEB(14.0, 9.0, 14.0, 9.0),
                  decoration: BoxDecoration(
                    color: _primaryPurple,
                    borderRadius: BorderRadius.circular(999.0),
                  ),
                  child: Text(
                    '위치 보기',
                    style: FlutterFlowTheme.of(context).labelMedium.override(
                          font: GoogleFonts.inter(
                            fontWeight: FontWeight.w800,
                          ),
                          color: Colors.white,
                          letterSpacing: 0.0,
                        ),
                  ),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }

  BoxDecoration _bottomCardDecoration() {
    return BoxDecoration(
      color: Colors.white.withOpacity(0.96),
      borderRadius: BorderRadius.circular(24.0),
      boxShadow: const [
        BoxShadow(
          blurRadius: 28.0,
          offset: Offset(0, 12),
          color: Color(0x33000000),
        ),
      ],
    );
  }

  Widget _buildButterflyBadge({Color? color}) {
    return Container(
      width: 54.0,
      height: 54.0,
      decoration: BoxDecoration(
        color: (color ?? _primaryPurple).withOpacity(0.12),
        borderRadius: BorderRadius.circular(18.0),
      ),
      child: Padding(
        padding: const EdgeInsets.all(8.0),
        child: Image.asset(
          'assets/images/pppd_butterfly.png',
          fit: BoxFit.contain,
        ),
      ),
    );
  }

  Widget _buildDangerBadge(String level) {
    final color = _dangerColor(level);

    return Container(
      padding: const EdgeInsetsDirectional.fromSTEB(9.0, 6.0, 9.0, 6.0),
      decoration: BoxDecoration(
        color: color.withOpacity(0.12),
        borderRadius: BorderRadius.circular(999.0),
      ),
      child: Text(
        _dangerLabel(level),
        style: FlutterFlowTheme.of(context).labelSmall.override(
              font: GoogleFonts.inter(
                fontWeight: FontWeight.w800,
              ),
              color: color,
              letterSpacing: 0.0,
            ),
      ),
    );
  }

  Widget _buildMap() {
    final initialLocation = _currentUserLocation ?? _fallbackLocation;

    return Stack(
      children: [
        gm.GoogleMap(
          initialCameraPosition: gm.CameraPosition(
            target: initialLocation,
            zoom: 15.0,
          ),
          onMapCreated: (controller) async {
            _mapController = controller;
            if (_currentUserLocation != null) {
              await _moveCameraTo(_currentUserLocation!, zoom: 17.0);
            }
          },
          onTap: (_) => setState(() => _selectedDangerPlace = null),
          markers: _markers,
          mapType: gm.MapType.hybrid,
          myLocationEnabled: true,
          myLocationButtonEnabled: false,
          zoomControlsEnabled: false,
          compassEnabled: false,
          mapToolbarEnabled: false,
          trafficEnabled: false,
        ),
        Positioned(
          top: 16.0,
          left: 16.0,
          right: 16.0,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              _buildSearchBar(),
              const SizedBox(height: 10.0),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: _buildFilterPanel(),
              ),
            ],
          ),
        ),
        Positioned(
          top: 142.0,
          left: 16.0,
          right: 82.0,
          child: _buildStatusPill(),
        ),
        Positioned(
          right: 16.0,
          top: 150.0,
          child: _buildFloatingControls(),
        ),
        Positioned(
          left: 16.0,
          right: 16.0,
          bottom: 18.0,
          child: _buildBottomDangerCard(),
        ),
      ],
    );
  }

  @override
  Widget build(BuildContext context) {
    final locSvc = context.watch<LocationContextService>();

    return GestureDetector(
      onTap: () {
        FocusScope.of(context).unfocus();
        FocusManager.instance.primaryFocus?.unfocus();
      },
      child: Scaffold(
        key: scaffoldKey,
        resizeToAvoidBottomInset: false,
        backgroundColor: FlutterFlowTheme.of(context).primaryBackground,
        // ── 현재 상황 선택 패널 (서버 추론 context 연동) ──
        bottomSheet: _ContextPanel(
          currentContext: locSvc.currentContext,
          onContextChanged: (ctx) => locSvc.setContext(ctx),
        ),
        body: SafeArea(
          top: false,
          child: _buildMap(),
        ),
      ),
    );
  }
}

// ── 상황 선택 패널 ─────────────────────────────────────────────────
class _ContextPanel extends StatelessWidget {
  const _ContextPanel({
    required this.currentContext,
    required this.onContextChanged,
  });
  final String currentContext;
  final void Function(String) onContextChanged;

  @override
  Widget build(BuildContext context) {
    final labels = LocationContextService.allContextLabels;
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 12, 16, 16),
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: const BorderRadius.vertical(top: Radius.circular(20)),
        boxShadow: [BoxShadow(color: Colors.black.withOpacity(0.08), blurRadius: 12, offset: const Offset(0, -4))],
      ),
      child: Column(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(Icons.place_rounded, size: 16, color: PppdColors.purple),
              const SizedBox(width: 6),
              Text('현재 상황', style: pppdText(size: 14, weight: FontWeight.w800)),
              const SizedBox(width: 6),
              Text('소리 추론 정확도에 사용됩니다', style: pppdText(size: 12, color: PppdColors.muted)),
            ],
          ),
          const SizedBox(height: 10),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: labels.entries.map((e) {
                final selected = e.key == currentContext;
                return Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: GestureDetector(
                    onTap: () => onContextChanged(e.key),
                    child: AnimatedContainer(
                      duration: const Duration(milliseconds: 200),
                      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
                      decoration: BoxDecoration(
                        color: selected ? PppdColors.purple : PppdColors.softPurple,
                        borderRadius: BorderRadius.circular(20),
                      ),
                      child: Text(
                        e.value,
                        style: pppdText(
                          size: 13,
                          color: selected ? Colors.white : PppdColors.deepPurple,
                          weight: selected ? FontWeight.w700 : FontWeight.w500,
                        ),
                      ),
                    ),
                  ),
                );
              }).toList(),
            ),
          ),
        ],
      ),
    );
  }
}
