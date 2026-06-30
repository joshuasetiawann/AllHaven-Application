import 'dart:convert';
import 'dart:io';

import 'package:allhaven_mobile/main.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  test('AllHaven asset server can be constructed', () {
    expect(AllHavenAssetServer(), isA<AllHavenAssetServer>());
  });

  test('settings route serves HTML for normal page loads', () {
    final server = AllHavenAssetServer(
      assetKeysForTesting: {
        'assets/allhaven/index.html',
        'assets/allhaven/dashboard/settings/index.html',
        'assets/allhaven/dashboard/settings/index.txt',
      },
    );

    expect(
      server.resolveAssetPath(Uri.parse('/dashboard/settings')),
      'assets/allhaven/dashboard/settings/index.html',
    );
  });

  test('settings route serves RSC payload for client navigation', () {
    final server = AllHavenAssetServer(
      assetKeysForTesting: {
        'assets/allhaven/index.html',
        'assets/allhaven/dashboard/settings/index.html',
        'assets/allhaven/dashboard/settings/index.txt',
      },
    );

    expect(
      server.resolveAssetPath(Uri.parse('/dashboard/settings?_rsc=abc123')),
      'assets/allhaven/dashboard/settings/index.txt',
    );
    expect(
      server.resolveAssetPath(Uri.parse('/dashboard/settings.rsc')),
      'assets/allhaven/dashboard/settings/index.txt',
    );
    expect(
      server.resolveAssetPath(Uri.parse('/dashboard/settings.txt')),
      'assets/allhaven/dashboard/settings/index.txt',
    );
    expect(
      server.resolveAssetPath(Uri.parse('/dashboard/settings/index.txt')),
      'assets/allhaven/dashboard/settings/index.txt',
    );
  });

  test('settings system subroute serves its RSC payload', () {
    final server = AllHavenAssetServer(
      assetKeysForTesting: {
        'assets/allhaven/index.html',
        'assets/allhaven/dashboard/settings/system/index.html',
        'assets/allhaven/dashboard/settings/system/index.txt',
      },
    );

    expect(
      server.resolveAssetPath(
        Uri.parse('/dashboard/settings/system?_rsc=abc123'),
      ),
      'assets/allhaven/dashboard/settings/system/index.txt',
    );
  });

  test(
    'asset server falls back when preferred port is already occupied',
    () async {
      final guard = await ServerSocket.bind(InternetAddress.loopbackIPv4, 0);
      addTearDown(() async {
        await guard.close();
      });

      final server = AllHavenAssetServer(preferredPort: guard.port);
      final uri = await server.start();
      addTearDown(server.stop);

      expect(uri.port, isNot(guard.port));
    },
  );

  test('asset server responds to exported settings RSC payloads', () async {
    final server = AllHavenAssetServer(preferredPort: 0);
    final uri = await server.start();
    addTearDown(server.stop);

    final socket = await Socket.connect(uri.host, uri.port);
    socket.write(
      'GET /dashboard/settings?_rsc=test HTTP/1.1\r\n'
      'Host: ${uri.host}:${uri.port}\r\n'
      'Connection: close\r\n'
      '\r\n',
    );
    await socket.flush();
    final response = utf8.decode(
      await socket.fold<List<int>>(
        <int>[],
        (buffer, chunk) => buffer..addAll(chunk),
      ),
    );

    expect(response, startsWith('HTTP/1.1 ${HttpStatus.ok}'));
    expect(response.toLowerCase(), contains('content-type: text/x-component'));
  });
}
