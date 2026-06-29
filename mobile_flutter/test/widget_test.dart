import 'package:allhaven_mobile/main.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
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
}
