import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:webview_flutter/webview_flutter.dart';

Future<void> main() async {
  WidgetsFlutterBinding.ensureInitialized();
  SystemChrome.setSystemUIOverlayStyle(
    const SystemUiOverlayStyle(
      statusBarColor: Colors.black,
      statusBarIconBrightness: Brightness.light,
      systemNavigationBarColor: Colors.black,
      systemNavigationBarIconBrightness: Brightness.light,
    ),
  );

  final server = AllHavenAssetServer();
  final baseUri = await server.start();
  runApp(AllHavenApp(baseUri: baseUri, server: server));
}

class AllHavenApp extends StatelessWidget {
  const AllHavenApp({super.key, required this.baseUri, required this.server});

  final Uri baseUri;
  final AllHavenAssetServer server;

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'AllHaven',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        brightness: Brightness.dark,
        scaffoldBackgroundColor: const Color(0xFF070B10),
      ),
      home: AllHavenWebShell(baseUri: baseUri, server: server),
    );
  }
}

class AllHavenWebShell extends StatefulWidget {
  const AllHavenWebShell({
    super.key,
    required this.baseUri,
    required this.server,
  });

  final Uri baseUri;
  final AllHavenAssetServer server;

  @override
  State<AllHavenWebShell> createState() => _AllHavenWebShellState();
}

class _AllHavenWebShellState extends State<AllHavenWebShell> {
  static const _blockingLoadTimeout = Duration(seconds: 5);

  late final WebViewController _controller;
  Timer? _loadingCoverTimer;
  var _progress = 0;
  var _pageLoading = true;
  var _blockingLoader = true;
  var _firstPageReleased = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    _armBlockingLoaderTimeout();
    _controller = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFF070B10))
      ..setNavigationDelegate(
        NavigationDelegate(
          onProgress: (progress) {
            if (!mounted) {
              return;
            }
            if (progress >= 100) {
              _finishPageLoad();
              return;
            }
            setState(() {
              _progress = progress;
              _pageLoading = true;
            });
          },
          onPageStarted: (_) => _beginPageLoad(),
          onPageFinished: (_) => _finishPageLoad(),
          onWebResourceError: (error) {
            if (error.isForMainFrame == false) {
              return;
            }
            _finishPageLoad();
            if (mounted) {
              setState(() => _error = error.description);
            }
          },
        ),
      )
      ..loadRequest(widget.baseUri);
  }

  @override
  void dispose() {
    _loadingCoverTimer?.cancel();
    unawaited(widget.server.stop());
    super.dispose();
  }

  void _beginPageLoad() {
    final shouldBlock = !_firstPageReleased;
    if (shouldBlock) {
      _armBlockingLoaderTimeout();
    }
    if (!mounted) {
      return;
    }
    setState(() {
      _progress = 0;
      _pageLoading = true;
      _blockingLoader = shouldBlock;
      _error = null;
    });
  }

  void _finishPageLoad() {
    _releaseBlockingLoader(markLoaded: true);
  }

  void _armBlockingLoaderTimeout() {
    _loadingCoverTimer?.cancel();
    _loadingCoverTimer = Timer(
      _blockingLoadTimeout,
      () => _releaseBlockingLoader(markLoaded: false),
    );
  }

  void _releaseBlockingLoader({required bool markLoaded}) {
    _loadingCoverTimer?.cancel();
    _loadingCoverTimer = null;
    _firstPageReleased = true;
    if (!mounted) {
      return;
    }
    setState(() {
      if (markLoaded) {
        _progress = 100;
        _pageLoading = false;
      }
      _blockingLoader = false;
    });
  }

  Future<void> _handleBack() async {
    if (await _controller.canGoBack()) {
      await _controller.goBack();
      return;
    }
    await SystemNavigator.pop();
  }

  @override
  Widget build(BuildContext context) {
    return PopScope(
      canPop: false,
      onPopInvokedWithResult: (didPop, _) {
        if (!didPop) {
          unawaited(_handleBack());
        }
      },
      child: Scaffold(
        body: SafeArea(
          child: Stack(
            children: [
              WebViewWidget(controller: _controller),
              if (_pageLoading && !_blockingLoader && _progress < 100)
                Positioned(
                  left: 0,
                  right: 0,
                  top: 0,
                  child: LinearProgressIndicator(
                    minHeight: 2,
                    value: _progress <= 0 ? null : _progress / 100,
                    backgroundColor: Colors.transparent,
                    color: const Color(0xFF25D8D0),
                  ),
                ),
              if (_blockingLoader)
                const Positioned.fill(child: _AllHavenLoadingCover()),
              if (_error != null)
                Positioned.fill(
                  child: _AllHavenErrorCover(
                    message: _error!,
                    onRetry: () => _controller.reload(),
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}

class _AllHavenLoadingCover extends StatelessWidget {
  const _AllHavenLoadingCover();

  @override
  Widget build(BuildContext context) {
    return const ColoredBox(
      color: Color(0xFF070B10),
      child: Center(
        child: SizedBox(
          width: 28,
          height: 28,
          child: CircularProgressIndicator(
            strokeWidth: 2,
            color: Color(0xFF25D8D0),
          ),
        ),
      ),
    );
  }
}

class _AllHavenErrorCover extends StatelessWidget {
  const _AllHavenErrorCover({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    return ColoredBox(
      color: const Color(0xFF070B10),
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              const Text(
                'AllHaven gagal dimuat',
                textAlign: TextAlign.center,
                style: TextStyle(
                  color: Colors.white,
                  fontSize: 20,
                  fontWeight: FontWeight.w700,
                ),
              ),
              const SizedBox(height: 12),
              Text(
                message,
                textAlign: TextAlign.center,
                style: const TextStyle(color: Color(0xFF9AA5B1)),
              ),
              const SizedBox(height: 20),
              FilledButton(
                style: FilledButton.styleFrom(
                  backgroundColor: const Color(0xFF25D8D0),
                  foregroundColor: const Color(0xFF071012),
                ),
                onPressed: onRetry,
                child: const Text('Muat ulang'),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class AllHavenAssetServer {
  AllHavenAssetServer({Set<String>? assetKeysForTesting})
    : _assetKeys = assetKeysForTesting;

  static const _assetRoot = 'assets/allhaven';
  static const _indexPath = '/index.html';

  HttpServer? _server;
  Set<String>? _assetKeys;

  Future<Uri> start() async {
    _assetKeys ??= await _loadAssetKeys();
    _server = await HttpServer.bind(InternetAddress.loopbackIPv4, 0);
    unawaited(_serveRequests(_server!));
    return Uri.parse('http://${_server!.address.host}:${_server!.port}/');
  }

  Future<void> stop() async {
    await _server?.close(force: true);
    _server = null;
  }

  Future<void> _serveRequests(HttpServer server) async {
    await for (final request in server) {
      unawaited(_handleRequest(request));
    }
  }

  Future<void> _handleRequest(HttpRequest request) async {
    final response = request.response;
    response.headers
      ..set(HttpHeaders.accessControlAllowOriginHeader, '*')
      ..set(HttpHeaders.cacheControlHeader, 'public, max-age=31536000');

    if (request.method == 'OPTIONS') {
      response.statusCode = HttpStatus.noContent;
      await response.close();
      return;
    }

    final assetPath = _resolveAssetPath(request.uri);
    try {
      final data = await rootBundle.load(assetPath);
      response.headers.contentType = _contentType(assetPath);
      response.contentLength = data.lengthInBytes;
      response.add(data.buffer.asUint8List());
    } on FlutterError {
      response.statusCode = HttpStatus.notFound;
      response.headers.contentType = ContentType.text;
      response.write('Not found');
    } finally {
      await response.close();
    }
  }

  @visibleForTesting
  String resolveAssetPath(Uri uri) => _resolveAssetPath(uri);

  String _resolveAssetPath(Uri uri) {
    final safePath = _normalizePath(_stripRscSuffix(uri.path));
    final routePath = _stripRoutePayloadSuffix(safePath);
    final wantsRsc = _isRscRequest(uri) || _isRoutePayloadRequest(safePath);
    final candidates = <String>[
      if (wantsRsc) ..._routeIndexCandidates(routePath, 'txt'),
      safePath,
      ..._routeIndexCandidates(routePath, 'html'),
      _indexPath,
    ];

    for (final candidate in candidates) {
      final assetPath = '$_assetRoot$candidate';
      if (_assetKeys?.contains(assetPath) ?? false) {
        return assetPath;
      }
    }
    return '$_assetRoot$_indexPath';
  }

  bool _isRscRequest(Uri uri) {
    return uri.queryParameters.containsKey('_rsc') || uri.path.endsWith('.rsc');
  }

  String _stripRscSuffix(String path) {
    return path.endsWith('.rsc') ? path.substring(0, path.length - 4) : path;
  }

  bool _isRoutePayloadRequest(String path) {
    return path.endsWith('.txt') && !path.endsWith('/index.txt');
  }

  String _stripRoutePayloadSuffix(String path) {
    return _isRoutePayloadRequest(path)
        ? path.substring(0, path.length - 4)
        : path;
  }

  List<String> _routeIndexCandidates(String safePath, String extension) {
    if (safePath == '/' || safePath == _indexPath) {
      return ['/index.$extension'];
    }
    if (safePath.endsWith('/index.html') || safePath.endsWith('/index.txt')) {
      return [
        '${safePath.substring(0, safePath.lastIndexOf('.') + 1)}$extension',
      ];
    }
    return [
      safePath.endsWith('/')
          ? '${safePath}index.$extension'
          : '$safePath/index.$extension',
    ];
  }

  String _normalizePath(String rawPath) {
    var path = Uri.decodeComponent(rawPath);
    if (path.isEmpty || path == '/') {
      return _indexPath;
    }
    if (!path.startsWith('/')) {
      path = '/$path';
    }
    if (path.contains('..')) {
      return _indexPath;
    }
    return path;
  }

  Future<Set<String>> _loadAssetKeys() async {
    final manifest = await rootBundle.loadString('AssetManifest.json');
    final decoded = jsonDecode(manifest);
    if (decoded is Map<String, dynamic>) {
      return decoded.keys.toSet();
    }
    return const <String>{};
  }

  ContentType _contentType(String assetPath) {
    final lower = assetPath.toLowerCase();
    if (lower.endsWith('.html')) {
      return ContentType.html;
    }
    if (lower.endsWith('.js') || lower.endsWith('.mjs')) {
      return ContentType('application', 'javascript', charset: 'utf-8');
    }
    if (lower.endsWith('.css')) {
      return ContentType('text', 'css', charset: 'utf-8');
    }
    if (lower.endsWith('.json') || lower.endsWith('.map')) {
      return ContentType.json;
    }
    if (lower.endsWith('.txt')) {
      return ContentType('text', 'x-component', charset: 'utf-8');
    }
    if (lower.endsWith('.svg')) {
      return ContentType('image', 'svg+xml');
    }
    if (lower.endsWith('.png')) {
      return ContentType('image', 'png');
    }
    if (lower.endsWith('.jpg') || lower.endsWith('.jpeg')) {
      return ContentType('image', 'jpeg');
    }
    if (lower.endsWith('.webp')) {
      return ContentType('image', 'webp');
    }
    if (lower.endsWith('.ico')) {
      return ContentType('image', 'x-icon');
    }
    if (lower.endsWith('.woff2')) {
      return ContentType('font', 'woff2');
    }
    if (lower.endsWith('.wasm')) {
      return ContentType('application', 'wasm');
    }
    return ContentType.binary;
  }
}
