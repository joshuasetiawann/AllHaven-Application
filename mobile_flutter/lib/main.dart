import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';
import 'package:http/http.dart' as http;
import 'package:intl/intl.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

const _supabaseUrl = String.fromEnvironment('SUPABASE_URL');
const _supabaseAnonKey = String.fromEnvironment('SUPABASE_ANON_KEY');
const _uuid = Uuid();

void main() {
  runApp(AllHavenMobile(api: SupabaseDirect(_supabaseUrl, _supabaseAnonKey)));
}

class AllHavenMobile extends StatefulWidget {
  const AllHavenMobile({super.key, required this.api});

  final SupabaseDirect api;

  @override
  State<AllHavenMobile> createState() => _AllHavenMobileState();
}

class _AllHavenMobileState extends State<AllHavenMobile> {
  final _store = const FlutterSecureStorage();
  late final AppSession session;

  @override
  void initState() {
    super.initState();
    session = AppSession(widget.api, _store)..bootstrap();
  }

  @override
  Widget build(BuildContext context) {
    return AnimatedBuilder(
      animation: session,
      builder: (context, _) {
        return MaterialApp(
          title: 'AllHaven Mobile',
          debugShowCheckedModeBanner: false,
          theme: _theme,
          home: _buildHome(),
        );
      },
    );
  }

  Widget _buildHome() {
    if (!widget.api.isConfigured) {
      return const SetupProblemPage(
        title: 'Supabase belum masuk build',
        message:
            'APK Flutter ini perlu SUPABASE_URL dan SUPABASE_ANON_KEY dari GitHub Actions. Isi repo variable/secret lalu rebuild.',
      );
    }
    if (session.isBooting) {
      return const LoadingPage(label: 'Membuka AllHaven...');
    }
    if (session.user == null) {
      return LoginPage(session: session);
    }
    return HomeShell(session: session);
  }
}

final _theme = ThemeData(
  brightness: Brightness.dark,
  useMaterial3: true,
  colorScheme: ColorScheme.fromSeed(
    seedColor: const Color(0xFF20D6C9),
    brightness: Brightness.dark,
    surface: const Color(0xFF0D1118),
  ),
  scaffoldBackgroundColor: const Color(0xFF090D13),
  cardTheme: CardThemeData(
    color: const Color(0xFF111820),
    elevation: 0,
    shape: RoundedRectangleBorder(
      borderRadius: BorderRadius.circular(8),
      side: const BorderSide(color: Color(0xFF223040)),
    ),
  ),
  inputDecorationTheme: InputDecorationTheme(
    filled: true,
    fillColor: const Color(0xFF0B1018),
    border: OutlineInputBorder(borderRadius: BorderRadius.circular(8)),
  ),
);

class ApiError implements Exception {
  ApiError(this.message, {this.statusCode = 0, this.code});

  final String message;
  final int statusCode;
  final String? code;

  @override
  String toString() => message;
}

class AppSession extends ChangeNotifier {
  AppSession(this.api, this.store);

  final SupabaseDirect api;
  final FlutterSecureStorage store;

  bool isBooting = true;
  bool isBusy = false;
  AppUser? user;
  Workspace? workspace;
  String? lastError;

  String? get workspaceId => workspace?.id;
  String? get appUserId => user?.id;

  Future<void> bootstrap() async {
    isBooting = true;
    notifyListeners();
    try {
      await api.restoreSession(store);
      if (api.hasSession) {
        await _loadMe();
      }
    } catch (err) {
      lastError = _message(err);
      await api.clearSession(store);
      user = null;
      workspace = null;
    } finally {
      isBooting = false;
      notifyListeners();
    }
  }

  Future<void> login(String email, String password) async {
    await _busy(() async {
      await api.signIn(email, password, store);
      try {
        await _loadMe();
      } catch (_) {
        await api.provision(fullName: null);
        await _loadMe();
      }
    });
  }

  Future<void> register(String email, String password, String fullName) async {
    await _busy(() async {
      await api.signUp(email, password, fullName);
      await api.signIn(email, password, store);
      await api.provision(fullName: fullName.trim().isEmpty ? null : fullName.trim());
      await _loadMe();
    });
  }

  Future<void> logout() async {
    await api.signOut(store);
    user = null;
    workspace = null;
    notifyListeners();
  }

  Future<void> refreshProfile() async {
    await _busy(_loadMe);
  }

  Future<void> _loadMe() async {
    final loaded = await api.loadMe();
    user = loaded.$1;
    workspace = loaded.$2;
    api.appUserId = user!.id;
    api.workspaceId = workspace!.id;
  }

  Future<void> _busy(Future<void> Function() run) async {
    isBusy = true;
    lastError = null;
    notifyListeners();
    try {
      await run();
    } catch (err) {
      lastError = _message(err);
      rethrow;
    } finally {
      isBusy = false;
      notifyListeners();
    }
  }
}

String _message(Object err) {
  if (err is ApiError) return err.message;
  return err.toString().replaceFirst('Exception: ', '');
}

class SupabaseDirect {
  SupabaseDirect(String url, String anonKey)
      : url = _trimSlash(url),
        anonKey = anonKey.trim();

  final String url;
  final String anonKey;

  String? accessToken;
  String? refreshToken;
  String? appUserId;
  String? workspaceId;

  bool get isConfigured => url.startsWith('https://') && anonKey.isNotEmpty;
  bool get hasSession => accessToken != null && accessToken!.isNotEmpty;
  String get restUrl => '$url/rest/v1';
  String get authUrl => '$url/auth/v1';

  Future<void> restoreSession(FlutterSecureStorage store) async {
    accessToken = await store.read(key: 'supabase_access_token');
    refreshToken = await store.read(key: 'supabase_refresh_token');
  }

  Future<void> clearSession(FlutterSecureStorage store) async {
    accessToken = null;
    refreshToken = null;
    appUserId = null;
    workspaceId = null;
    await store.delete(key: 'supabase_access_token');
    await store.delete(key: 'supabase_refresh_token');
  }

  Future<void> signIn(String email, String password, FlutterSecureStorage store) async {
    final body = await _request(
      'POST',
      Uri.parse('$authUrl/token').replace(queryParameters: {'grant_type': 'password'}),
      authenticated: false,
      body: {'email': email.trim(), 'password': password},
      timeout: const Duration(seconds: 18),
    ) as Map<String, dynamic>;
    accessToken = body['access_token']?.toString();
    refreshToken = body['refresh_token']?.toString();
    if (accessToken == null || accessToken!.isEmpty) {
      throw ApiError('Login gagal: Supabase tidak mengirim session.', statusCode: 401);
    }
    await store.write(key: 'supabase_access_token', value: accessToken);
    if (refreshToken != null) {
      await store.write(key: 'supabase_refresh_token', value: refreshToken);
    }
  }

  Future<void> signUp(String email, String password, String fullName) async {
    try {
      await _request(
        'POST',
        Uri.parse('$authUrl/signup'),
        authenticated: false,
        body: {
          'email': email.trim(),
          'password': password,
          if (fullName.trim().isNotEmpty) 'data': {'full_name': fullName.trim()},
        },
        timeout: const Duration(seconds: 18),
      );
    } on ApiError catch (err) {
      if (!err.message.toLowerCase().contains('already')) rethrow;
    }
  }

  Future<void> signOut(FlutterSecureStorage store) async {
    try {
      await _request('POST', Uri.parse('$authUrl/logout'), body: {});
    } catch (_) {
      // Session may already be expired; local cleanup still matters.
    }
    await clearSession(store);
  }

  Future<void> provision({String? fullName}) async {
    await rpc('provision_me', {'p_full_name': fullName});
  }

  Future<(AppUser, Workspace)> loadMe() async {
    final profileRows = await select(
      'profiles',
      query: {'select': '*', 'limit': '1'},
      timeout: const Duration(seconds: 8),
    );
    if (profileRows.isEmpty) {
      throw ApiError('Profil belum siap. Coba login ulang agar provision_me berjalan.', statusCode: 409);
    }
    final wsRows = await select(
      'workspaces',
      query: {'select': '*', 'order': 'created_at.asc', 'limit': '1'},
      timeout: const Duration(seconds: 8),
    );
    if (wsRows.isEmpty) {
      throw ApiError('Workspace belum siap. Coba login ulang.', statusCode: 409);
    }
    return (AppUser.fromJson(profileRows.first), Workspace.fromJson(wsRows.first));
  }

  Future<List<Map<String, dynamic>>> select(
    String table, {
    Map<String, String>? query,
    Duration timeout = const Duration(seconds: 10),
  }) async {
    final uri = Uri.parse('$restUrl/$table').replace(queryParameters: query ?? {'select': '*'});
    final body = await _request('GET', uri, timeout: timeout);
    return _rows(body);
  }

  Future<Map<String, dynamic>> insert(
    String table,
    Map<String, dynamic> payload, {
    bool scoped = true,
    Duration timeout = const Duration(seconds: 10),
  }) async {
    final row = scoped ? {...payload, ...newScopedRow()} : payload;
    final body = await _insertTolerant(table, row, timeout: timeout);
    final rows = _rows(body);
    if (rows.isEmpty) throw ApiError('Insert berhasil tapi Supabase tidak mengembalikan data.');
    return rows.first;
  }

  Future<List<Map<String, dynamic>>> insertMany(
    String table,
    List<Map<String, dynamic>> payloads, {
    bool scoped = true,
    Duration timeout = const Duration(seconds: 12),
  }) async {
    final rows = payloads.map((p) => scoped ? {...p, ...newScopedRow()} : p).toList();
    final body = await _insertTolerant(table, rows, timeout: timeout);
    return _rows(body);
  }

  Future<Map<String, dynamic>> update(
    String table,
    String id,
    Map<String, dynamic> payload, {
    Duration timeout = const Duration(seconds: 10),
  }) async {
    final uri = Uri.parse('$restUrl/$table').replace(queryParameters: {
      'id': 'eq.$id',
      'select': '*',
    });
    final body = await _request('PATCH', uri, body: payload, timeout: timeout);
    final rows = _rows(body);
    if (rows.isEmpty) throw ApiError('Data tidak ditemukan atau tidak boleh diubah.', statusCode: 404);
    return rows.first;
  }

  Future<void> softDelete(String table, String id) async {
    await update(table, id, {'is_deleted': true, 'deleted_at': DateTime.now().toUtc().toIso8601String()});
  }

  Future<dynamic> rpc(String name, Map<String, dynamic> payload) {
    return _request('POST', Uri.parse('$restUrl/rpc/$name'), body: payload, timeout: const Duration(seconds: 12));
  }

  Map<String, dynamic> newScopedRow() {
    if (workspaceId == null || appUserId == null) {
      throw ApiError('Session belum lengkap. Logout lalu login lagi.', statusCode: 401);
    }
    return {'id': _uuid.v4(), 'workspace_id': workspaceId, 'created_by': appUserId};
  }

  Future<dynamic> _insertTolerant(
    String table,
    dynamic payload, {
    required Duration timeout,
  }) async {
    dynamic nextPayload = payload;
    final stripped = <String>{};
    while (true) {
      try {
        return await _request(
          'POST',
          Uri.parse('$restUrl/$table').replace(queryParameters: {'select': '*'}),
          body: nextPayload,
          timeout: timeout,
        );
      } on ApiError catch (err) {
        final missing = RegExp("Could not find the '([^']+)' column").firstMatch(err.message)?.group(1);
        if (missing == null || stripped.contains(missing) || !_payloadHas(nextPayload, missing)) rethrow;
        stripped.add(missing);
        nextPayload = _stripPayload(nextPayload, missing);
      }
    }
  }

  Future<dynamic> _request(
    String method,
    Uri uri, {
    Object? body,
    bool authenticated = true,
    Duration timeout = const Duration(seconds: 10),
  }) async {
    final headers = <String, String>{
      'apikey': anonKey,
      'Content-Type': 'application/json',
      if (method != 'GET') 'Prefer': 'return=representation',
      if (authenticated) 'Authorization': 'Bearer ${accessToken ?? anonKey}',
    };
    late http.Response res;
    try {
      final encoded = body == null ? null : jsonEncode(body);
      switch (method) {
        case 'GET':
          res = await http.get(uri, headers: headers).timeout(timeout);
          break;
        case 'POST':
          res = await http.post(uri, headers: headers, body: encoded).timeout(timeout);
          break;
        case 'PATCH':
          res = await http.patch(uri, headers: headers, body: encoded).timeout(timeout);
          break;
        case 'DELETE':
          res = await http.delete(uri, headers: headers, body: encoded).timeout(timeout);
          break;
        default:
          throw ApiError('HTTP method tidak dikenal: $method');
      }
    } on TimeoutException {
      throw ApiError('Koneksi ke Supabase terlalu lama. Cek internet lalu coba lagi.', code: 'TIMEOUT');
    } on http.ClientException catch (err) {
      throw ApiError('Tidak bisa menghubungi Supabase: ${err.message}');
    }
    final decoded = _decode(res.body);
    if (res.statusCode < 200 || res.statusCode >= 300) {
      final msg = decoded is Map
          ? (decoded['message'] ?? decoded['error_description'] ?? decoded['error'] ?? res.body).toString()
          : (res.body.isEmpty ? 'Request gagal (${res.statusCode})' : res.body);
      throw ApiError(msg, statusCode: res.statusCode, code: decoded is Map ? decoded['code']?.toString() : null);
    }
    return decoded;
  }
}

String _trimSlash(String value) => value.trim().replaceAll(RegExp(r'/+$'), '');

dynamic _decode(String body) {
  if (body.trim().isEmpty) return null;
  return jsonDecode(body);
}

List<Map<String, dynamic>> _rows(dynamic body) {
  if (body is List) {
    return body.whereType<Map>().map((e) => Map<String, dynamic>.from(e)).toList();
  }
  if (body is Map) return [Map<String, dynamic>.from(body)];
  return [];
}

bool _payloadHas(dynamic payload, String key) {
  if (payload is Map) return payload.containsKey(key);
  if (payload is List) return payload.any((row) => row is Map && row.containsKey(key));
  return false;
}

dynamic _stripPayload(dynamic payload, String key) {
  if (payload is Map) {
    final next = Map<String, dynamic>.from(payload)..remove(key);
    return next;
  }
  if (payload is List) {
    return payload.map((row) {
      if (row is! Map) return row;
      return Map<String, dynamic>.from(row)..remove(key);
    }).toList();
  }
  return payload;
}

class AppUser {
  AppUser({required this.id, required this.email, this.fullName});

  final String id;
  final String email;
  final String? fullName;

  factory AppUser.fromJson(Map<String, dynamic> json) {
    return AppUser(
      id: json['id'].toString(),
      email: (json['email'] ?? '').toString(),
      fullName: json['full_name']?.toString(),
    );
  }
}

class Workspace {
  Workspace({required this.id, required this.name});

  final String id;
  final String name;

  factory Workspace.fromJson(Map<String, dynamic> json) {
    return Workspace(id: json['id'].toString(), name: (json['name'] ?? 'AllHaven').toString());
  }
}

class LoadingPage extends StatelessWidget {
  const LoadingPage({super.key, required this.label});

  final String label;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const CircularProgressIndicator(),
            const SizedBox(height: 18),
            Text(label),
          ],
        ),
      ),
    );
  }
}

class SetupProblemPage extends StatelessWidget {
  const SetupProblemPage({super.key, required this.title, required this.message});

  final String title;
  final String message;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Center(
            child: Card(
              child: Padding(
                padding: const EdgeInsets.all(20),
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(title, style: Theme.of(context).textTheme.headlineSmall),
                    const SizedBox(height: 12),
                    Text(message),
                  ],
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}

class LoginPage extends StatefulWidget {
  const LoginPage({super.key, required this.session});

  final AppSession session;

  @override
  State<LoginPage> createState() => _LoginPageState();
}

class _LoginPageState extends State<LoginPage> {
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _fullName = TextEditingController();
  bool _register = false;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _fullName.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            const SizedBox(height: 40),
            Text('AllHaven Mobile', style: Theme.of(context).textTheme.displaySmall?.copyWith(fontWeight: FontWeight.w800)),
            const SizedBox(height: 8),
            const Text('Masuk langsung ke Supabase. Tidak perlu backend bridge untuk data utama.'),
            const SizedBox(height: 28),
            if (_register)
              TextField(
                controller: _fullName,
                decoration: const InputDecoration(labelText: 'Nama'),
                textInputAction: TextInputAction.next,
              ),
            if (_register) const SizedBox(height: 12),
            TextField(
              controller: _email,
              decoration: const InputDecoration(labelText: 'Email'),
              keyboardType: TextInputType.emailAddress,
              textInputAction: TextInputAction.next,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: _password,
              decoration: const InputDecoration(labelText: 'Password'),
              obscureText: true,
              onSubmitted: (_) => _submit(),
            ),
            const SizedBox(height: 18),
            FilledButton(
              onPressed: widget.session.isBusy ? null : _submit,
              child: widget.session.isBusy
                  ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                  : Text(_register ? 'Daftar & Masuk' : 'Masuk'),
            ),
            TextButton(
              onPressed: widget.session.isBusy ? null : () => setState(() => _register = !_register),
              child: Text(_register ? 'Saya sudah punya akun' : 'Buat akun baru'),
            ),
            if (widget.session.lastError != null) ErrorBox(message: widget.session.lastError!),
          ],
        ),
      ),
    );
  }

  Future<void> _submit() async {
    FocusScope.of(context).unfocus();
    try {
      if (_register) {
        await widget.session.register(_email.text, _password.text, _fullName.text);
      } else {
        await widget.session.login(_email.text, _password.text);
      }
    } catch (err) {
      if (mounted) showSnack(context, _message(err));
    }
  }
}

class HomeShell extends StatefulWidget {
  const HomeShell({super.key, required this.session});

  final AppSession session;

  @override
  State<HomeShell> createState() => _HomeShellState();
}

class _HomeShellState extends State<HomeShell> {
  late final pages = <_PageEntry>[
    _PageEntry('Home', Icons.dashboard_outlined, DashboardPage(session: widget.session)),
    _PageEntry('AI', Icons.auto_awesome_outlined, AiChatPage(session: widget.session)),
    _PageEntry('Tasks', Icons.check_circle_outline, GenericTablePage.tasks(session: widget.session)),
    _PageEntry('Notes', Icons.notes_outlined, GenericTablePage.notes(session: widget.session)),
    _PageEntry('Finance', Icons.account_balance_wallet_outlined, FinancePage(session: widget.session)),
    _PageEntry('Routines', Icons.calendar_month_outlined, GenericTablePage.routines(session: widget.session)),
    _PageEntry('Approvals', Icons.verified_user_outlined, ApprovalsPage(session: widget.session)),
    _PageEntry('Memory', Icons.psychology_alt_outlined, GenericTablePage.memories(session: widget.session)),
    _PageEntry('Automation', Icons.hub_outlined, GenericTablePage.automations(session: widget.session)),
    _PageEntry('Settings', Icons.settings_outlined, SettingsPage(session: widget.session)),
  ];

  @override
  Widget build(BuildContext context) {
    return DefaultTabController(
      length: pages.length,
      child: Scaffold(
        appBar: AppBar(
          title: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              const Text('AllHaven'),
              Text(
                widget.session.workspace?.name ?? 'Mobile',
                style: Theme.of(context).textTheme.bodySmall?.copyWith(color: Colors.white60),
              ),
            ],
          ),
          actions: [
            IconButton(
              tooltip: 'Refresh',
              onPressed: () => setState(() {}),
              icon: const Icon(Icons.refresh),
            ),
            IconButton(
              tooltip: 'Logout',
              onPressed: widget.session.logout,
              icon: const Icon(Icons.logout),
            ),
          ],
          bottom: TabBar(
            isScrollable: true,
            tabs: [for (final p in pages) Tab(icon: Icon(p.icon), text: p.label)],
          ),
        ),
        body: TabBarView(children: [for (final p in pages) p.page]),
      ),
    );
  }
}

class _PageEntry {
  _PageEntry(this.label, this.icon, this.page);
  final String label;
  final IconData icon;
  final Widget page;
}

class ErrorBox extends StatelessWidget {
  const ErrorBox({super.key, required this.message});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Container(
      margin: const EdgeInsets.only(top: 12),
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF35240B),
        border: Border.all(color: const Color(0xFF7D5B13)),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Row(
        children: [
          const Icon(Icons.warning_amber, color: Color(0xFFFFC44D)),
          const SizedBox(width: 10),
          Expanded(child: Text(message, style: const TextStyle(color: Color(0xFFFFD166)))),
        ],
      ),
    );
  }
}

class DashboardPage extends StatefulWidget {
  const DashboardPage({super.key, required this.session});

  final AppSession session;

  @override
  State<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends State<DashboardPage> {
  late Future<_DashboardData> _future = _load();

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => setState(() => _future = _load()),
      child: FutureBuilder<_DashboardData>(
        future: _future,
        builder: (context, snap) {
          if (snap.connectionState != ConnectionState.done) return const Center(child: CircularProgressIndicator());
          if (snap.hasError) return ListView(padding: const EdgeInsets.all(16), children: [ErrorBox(message: _message(snap.error!))]);
          final data = snap.data!;
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  StatCard(label: 'Income', value: money(data.income), icon: Icons.south_west, color: const Color(0xFF38E0A1)),
                  StatCard(label: 'Expense', value: money(data.expense), icon: Icons.north_east, color: const Color(0xFFFF7373)),
                  StatCard(label: 'Balance', value: money(data.income - data.expense), icon: Icons.account_balance_wallet_outlined),
                ],
              ),
              const SizedBox(height: 16),
              SectionHeader(title: 'Today', action: IconButton(onPressed: () => setState(() => _future = _load()), icon: const Icon(Icons.refresh))),
              CardList(
                children: [
                  InfoRow(icon: Icons.check_circle_outline, title: '${data.openTasks} open tasks', subtitle: 'Tasks sync directly from Supabase'),
                  InfoRow(icon: Icons.notes_outlined, title: '${data.notes} notes', subtitle: 'Available without backend bridge'),
                  InfoRow(icon: Icons.verified_user_outlined, title: '${data.proposals} pending approvals', subtitle: 'Can approve supported actions on mobile'),
                  InfoRow(icon: Icons.psychology_alt_outlined, title: '${data.memories} active memories', subtitle: 'Saved in Supabase'),
                ],
              ),
              const SizedBox(height: 16),
              SectionHeader(title: 'Recent Transactions'),
              CardList(
                children: data.recentTransactions.isEmpty
                    ? [const EmptyLine('No transactions yet')]
                    : data.recentTransactions
                        .map((row) => InfoRow(
                              icon: row['type'] == 'INCOME' ? Icons.south_west : Icons.north_east,
                              title: row['description']?.toString().isNotEmpty == true ? row['description'].toString() : row['type'].toString(),
                              subtitle: row['transaction_date']?.toString() ?? '',
                              trailing: money(num.tryParse(row['amount'].toString()) ?? 0),
                              danger: row['type'] != 'INCOME',
                            ))
                        .toList(),
              ),
            ],
          );
        },
      ),
    );
  }

  Future<_DashboardData> _load() async {
    final api = widget.session.api;
    final tx = await api.select('transactions', query: {
      'select': '*',
      'is_deleted': 'eq.false',
      'order': 'transaction_date.desc,created_at.desc',
      'limit': '25',
    });
    final tasks = await api.select('tasks', query: {'select': 'id,status', 'is_deleted': 'eq.false'});
    final notes = await api.select('notes', query: {'select': 'id', 'is_deleted': 'eq.false'});
    final props = await api.select('ai_tool_proposals', query: {
      'select': 'id',
      'workspace_id': 'eq.${widget.session.workspaceId}',
      'status': 'in.(PENDING,NEEDS_EDIT,FAILED)',
    });
    final memories = await api.select('ai_memories', query: {
      'select': 'id',
      'workspace_id': 'eq.${widget.session.workspaceId}',
      'status': 'eq.active',
      'is_deleted': 'eq.false',
    }).catchError((_) => <Map<String, dynamic>>[]);
    num income = 0;
    num expense = 0;
    for (final row in tx) {
      final amount = num.tryParse(row['amount'].toString()) ?? 0;
      if (row['type'] == 'INCOME') {
        income += amount;
      } else {
        expense += amount;
      }
    }
    return _DashboardData(
      income: income,
      expense: expense,
      openTasks: tasks.where((t) => t['status'] != 'DONE').length,
      notes: notes.length,
      proposals: props.length,
      memories: memories.length,
      recentTransactions: tx.take(8).toList(),
    );
  }
}

class _DashboardData {
  _DashboardData({
    required this.income,
    required this.expense,
    required this.openTasks,
    required this.notes,
    required this.proposals,
    required this.memories,
    required this.recentTransactions,
  });

  final num income;
  final num expense;
  final int openTasks;
  final int notes;
  final int proposals;
  final int memories;
  final List<Map<String, dynamic>> recentTransactions;
}

class StatCard extends StatelessWidget {
  const StatCard({super.key, required this.label, required this.value, required this.icon, this.color});

  final String label;
  final String value;
  final IconData icon;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      width: MediaQuery.sizeOf(context).width > 560 ? 220 : (MediaQuery.sizeOf(context).width - 44) / 2,
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                children: [
                  Icon(icon, color: color ?? Theme.of(context).colorScheme.primary),
                  const Spacer(),
                  Text(label.toUpperCase(), style: const TextStyle(color: Colors.white54, letterSpacing: 1.5, fontSize: 11)),
                ],
              ),
              const SizedBox(height: 18),
              FittedBox(
                fit: BoxFit.scaleDown,
                alignment: Alignment.centerLeft,
                child: Text(value, style: TextStyle(fontSize: 24, fontWeight: FontWeight.w800, color: color)),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class GenericTablePage extends StatefulWidget {
  GenericTablePage({super.key, required this.session, required this.spec});

  factory GenericTablePage.tasks({required AppSession session}) {
    return GenericTablePage(
      session: session,
      spec: TableSpec(
        table: 'tasks',
        title: 'Tasks',
        order: 'created_at.desc',
        fields: [
          FieldSpec('title', 'Title'),
          FieldSpec('description', 'Description', kind: FieldKind.longText, optional: true),
          FieldSpec('status', 'Status', kind: FieldKind.select, options: const ['TODO', 'IN_PROGRESS', 'DONE'], defaultValue: 'TODO'),
          FieldSpec('priority', 'Priority', kind: FieldKind.select, options: const ['LOW', 'NORMAL', 'HIGH', 'URGENT'], defaultValue: 'NORMAL'),
          FieldSpec('due_at', 'Due at', kind: FieldKind.dateTime, optional: true),
        ],
        defaults: const {'status': 'TODO', 'priority': 'NORMAL', 'is_deleted': false},
        titleOf: (r) => r['title']?.toString() ?? 'Task',
        subtitleOf: (r) => '${r['status'] ?? 'TODO'} · ${r['priority'] ?? 'NORMAL'}',
      ),
    );
  }

  factory GenericTablePage.notes({required AppSession session}) {
    return GenericTablePage(
      session: session,
      spec: TableSpec(
        table: 'notes',
        title: 'Notes',
        order: 'updated_at.desc',
        fields: [
          FieldSpec('title', 'Title'),
          FieldSpec('content', 'Content', kind: FieldKind.longText, optional: true),
          FieldSpec('tags', 'Tags, comma separated', optional: true),
          FieldSpec('is_pinned', 'Pinned', kind: FieldKind.boolean, defaultValue: false),
        ],
        defaults: const {'tags': <String>[], 'is_pinned': false, 'is_deleted': false},
        transform: (v) => {...v, 'tags': _tagList(v['tags'])},
        titleOf: (r) => r['title']?.toString() ?? 'Note',
        subtitleOf: (r) => (r['content'] ?? '').toString(),
      ),
    );
  }

  factory GenericTablePage.routines({required AppSession session}) {
    return GenericTablePage(
      session: session,
      spec: TableSpec(
        table: 'calendar_events',
        title: 'Routines',
        order: 'start_at.asc',
        fields: [
          FieldSpec('title', 'Title'),
          FieldSpec('description', 'Description', kind: FieldKind.longText, optional: true),
          FieldSpec('start_at', 'Start at', kind: FieldKind.dateTime),
          FieldSpec('end_at', 'End at', kind: FieldKind.dateTime, optional: true),
          FieldSpec('repeat_rule', 'Repeat', kind: FieldKind.select, options: const ['once', 'daily', 'weekly'], defaultValue: 'once'),
        ],
        defaults: const {'all_day': false, 'repeat_rule': 'once', 'is_deleted': false},
        titleOf: (r) => r['title']?.toString() ?? 'Routine',
        subtitleOf: (r) => '${_prettyDateTime(r['start_at'])} · ${r['repeat_rule'] ?? 'once'}',
      ),
    );
  }

  factory GenericTablePage.memories({required AppSession session}) {
    return GenericTablePage(
      session: session,
      spec: TableSpec(
        table: 'ai_memories',
        title: 'Memory',
        order: 'updated_at.desc',
        fields: [
          FieldSpec('category', 'Category', defaultValue: 'Profile'),
          FieldSpec('title', 'Title'),
          FieldSpec('content', 'Content', kind: FieldKind.longText),
          FieldSpec('sensitivity', 'Sensitivity', kind: FieldKind.select, options: const ['LOW', 'MEDIUM', 'HIGH'], defaultValue: 'LOW'),
        ],
        defaults: const {
          'category': 'Profile',
          'source': 'manual',
          'status': 'active',
          'sensitivity': 'LOW',
          'enabled': true,
          'confidence': 1.0,
          'relevance_score': 0.5,
          'is_deleted': false,
        },
        titleOf: (r) => r['title']?.toString() ?? 'Memory',
        subtitleOf: (r) => '${r['category'] ?? 'Profile'} · ${r['content'] ?? ''}',
      ),
    );
  }

  factory GenericTablePage.automations({required AppSession session}) {
    return GenericTablePage(
      session: session,
      spec: TableSpec(
        table: 'automations',
        title: 'Automations',
        order: 'created_at.desc',
        fields: [
          FieldSpec('name', 'Name'),
          FieldSpec('description', 'Description', kind: FieldKind.longText, optional: true),
          FieldSpec('trigger_type', 'Trigger type', defaultValue: 'manual'),
          FieldSpec('action_type', 'Action type', defaultValue: 'noop'),
          FieldSpec('enabled', 'Enabled', kind: FieldKind.boolean, defaultValue: false),
        ],
        defaults: const {'trigger_type': 'manual', 'action_type': 'noop', 'config': {}, 'enabled': false, 'is_deleted': false},
        titleOf: (r) => r['name']?.toString() ?? 'Automation',
        subtitleOf: (r) => '${r['trigger_type'] ?? 'manual'} → ${r['action_type'] ?? 'noop'}',
      ),
    );
  }

  final AppSession session;
  final TableSpec spec;

  @override
  State<GenericTablePage> createState() => _GenericTablePageState();
}

class _GenericTablePageState extends State<GenericTablePage> {
  late Future<List<Map<String, dynamic>>> _future = _load();

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => _reload(),
      child: FutureBuilder<List<Map<String, dynamic>>>(
        future: _future,
        builder: (context, snap) {
          final rows = snap.data ?? [];
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              SectionHeader(
                title: widget.spec.title,
                action: FilledButton.icon(
                  onPressed: _create,
                  icon: const Icon(Icons.add),
                  label: const Text('Add'),
                ),
              ),
              if (snap.connectionState != ConnectionState.done) const LinearProgressIndicator(),
              if (snap.hasError) ErrorBox(message: _message(snap.error!)),
              if (rows.isEmpty && snap.connectionState == ConnectionState.done && !snap.hasError) const EmptyState(),
              for (final row in rows)
                Card(
                  child: ListTile(
                    title: Text(widget.spec.titleOf(row), maxLines: 1, overflow: TextOverflow.ellipsis),
                    subtitle: Text(widget.spec.subtitleOf(row), maxLines: 2, overflow: TextOverflow.ellipsis),
                    trailing: Wrap(
                      spacing: 4,
                      children: [
                        IconButton(icon: const Icon(Icons.edit_outlined), onPressed: () => _edit(row)),
                        IconButton(icon: const Icon(Icons.delete_outline), onPressed: () => _delete(row['id'].toString())),
                      ],
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  Future<List<Map<String, dynamic>>> _load() {
    final q = <String, String>{'select': '*', 'order': widget.spec.order};
    if (widget.spec.hasSoftDelete) q['is_deleted'] = 'eq.false';
    if (widget.spec.table == 'ai_memories') {
      q['workspace_id'] = 'eq.${widget.session.workspaceId}';
      q['status'] = 'eq.active';
    }
    return widget.session.api.select(widget.spec.table, query: q).catchError((err) {
      if (widget.spec.table == 'ai_memories' && _message(err).contains('is_deleted')) {
        final retry = Map<String, String>.from(q)..remove('is_deleted');
        return widget.session.api.select(widget.spec.table, query: retry);
      }
      throw err;
    });
  }

  void _reload() => setState(() => _future = _load());

  Future<void> _create() async {
    final values = await showEditor(context, widget.spec, null);
    if (values == null) return;
    try {
      final payload = widget.spec.transform({...widget.spec.defaults, ...values});
      await widget.session.api.insert(widget.spec.table, payload);
      _reload();
    } catch (err) {
      showSnack(context, _message(err));
    }
  }

  Future<void> _edit(Map<String, dynamic> row) async {
    final values = await showEditor(context, widget.spec, row);
    if (values == null) return;
    try {
      await widget.session.api.update(widget.spec.table, row['id'].toString(), widget.spec.transform(values));
      _reload();
    } catch (err) {
      showSnack(context, _message(err));
    }
  }

  Future<void> _delete(String id) async {
    final ok = await confirm(context, 'Delete ${widget.spec.title}?');
    if (!ok) return;
    try {
      await widget.session.api.softDelete(widget.spec.table, id);
      _reload();
    } catch (err) {
      showSnack(context, _message(err));
    }
  }
}

enum FieldKind { text, longText, number, date, dateTime, select, boolean }

class FieldSpec {
  FieldSpec(
    this.key,
    this.label, {
    this.kind = FieldKind.text,
    this.options = const [],
    this.defaultValue,
    this.optional = false,
  });

  final String key;
  final String label;
  final FieldKind kind;
  final List<String> options;
  final Object? defaultValue;
  final bool optional;
}

class TableSpec {
  TableSpec({
    required this.table,
    required this.title,
    required this.fields,
    required this.titleOf,
    required this.subtitleOf,
    this.order = 'created_at.desc',
    this.defaults = const {},
    this.hasSoftDelete = true,
    Map<String, dynamic> Function(Map<String, dynamic>)? transform,
  }) : transform = transform ?? ((v) => v);

  final String table;
  final String title;
  final List<FieldSpec> fields;
  final String order;
  final Map<String, dynamic> defaults;
  final bool hasSoftDelete;
  final Map<String, dynamic> Function(Map<String, dynamic>) transform;
  final String Function(Map<String, dynamic>) titleOf;
  final String Function(Map<String, dynamic>) subtitleOf;
}

Future<Map<String, dynamic>?> showEditor(BuildContext context, TableSpec spec, Map<String, dynamic>? row) {
  final controllers = <String, TextEditingController>{};
  final values = <String, dynamic>{};
  for (final field in spec.fields) {
    final current = row?[field.key] ?? field.defaultValue ?? '';
    if (field.kind == FieldKind.boolean) {
      values[field.key] = current == true || current.toString() == 'true';
    } else {
      controllers[field.key] = TextEditingController(text: _initialText(field, current));
    }
  }
  return showDialog<Map<String, dynamic>>(
    context: context,
    builder: (context) {
      return StatefulBuilder(
        builder: (context, setState) {
          return AlertDialog(
            title: Text(row == null ? 'Add ${spec.title}' : 'Edit ${spec.title}'),
            content: SizedBox(
              width: 520,
              child: SingleChildScrollView(
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    for (final field in spec.fields) ...[
                      if (field.kind == FieldKind.select)
                        DropdownButtonFormField<String>(
                          value: _selectValue(field.options, controllers[field.key]!.text),
                          decoration: InputDecoration(labelText: field.label),
                          items: field.options.map((o) => DropdownMenuItem(value: o, child: Text(o))).toList(),
                          onChanged: (v) => controllers[field.key]!.text = v ?? '',
                        )
                      else if (field.kind == FieldKind.boolean)
                        SwitchListTile(
                          value: values[field.key] == true,
                          title: Text(field.label),
                          onChanged: (v) => setState(() => values[field.key] = v),
                        )
                      else
                        TextField(
                          controller: controllers[field.key],
                          decoration: InputDecoration(labelText: field.label),
                          minLines: field.kind == FieldKind.longText ? 3 : 1,
                          maxLines: field.kind == FieldKind.longText ? 6 : 1,
                          keyboardType: field.kind == FieldKind.number ? TextInputType.number : TextInputType.text,
                        ),
                      const SizedBox(height: 10),
                    ],
                  ],
                ),
              ),
            ),
            actions: [
              TextButton(onPressed: () => Navigator.pop(context), child: const Text('Cancel')),
              FilledButton(
                onPressed: () {
                  final out = <String, dynamic>{};
                  for (final field in spec.fields) {
                    if (field.kind == FieldKind.boolean) {
                      out[field.key] = values[field.key] == true;
                      continue;
                    }
                    final raw = controllers[field.key]!.text.trim();
                    if (raw.isEmpty && field.optional) {
                      out[field.key] = null;
                    } else if (field.kind == FieldKind.number) {
                      out[field.key] = num.tryParse(raw.replaceAll(',', '.')) ?? 0;
                    } else if (field.kind == FieldKind.dateTime) {
                      out[field.key] = _dateInput(raw, withTime: true);
                    } else if (field.kind == FieldKind.date) {
                      out[field.key] = _dateInput(raw, withTime: false);
                    } else {
                      out[field.key] = raw;
                    }
                  }
                  Navigator.pop(context, out);
                },
                child: const Text('Save'),
              ),
            ],
          );
        },
      );
    },
  );
}

String _initialText(FieldSpec field, Object? value) {
  if (value == null) return '';
  if (field.key == 'tags' && value is List) return value.join(', ');
  return value.toString();
}

List<String> _tagList(Object? value) {
  if (value is List) return value.map((e) => e.toString()).where((e) => e.trim().isNotEmpty).toList();
  return value.toString().split(',').map((e) => e.trim()).where((e) => e.isNotEmpty).toList();
}

String? _selectValue(List<String> options, String current) {
  if (options.isEmpty) return null;
  if (current.isNotEmpty && options.contains(current)) return current;
  return options.first;
}

T? _firstOrNull<T>(Iterable<T> values) {
  final iterator = values.iterator;
  if (iterator.moveNext()) return iterator.current;
  return null;
}

String? _dateInput(String raw, {required bool withTime}) {
  if (raw.isEmpty) return null;
  final parsed = DateTime.tryParse(raw);
  if (parsed != null) return withTime ? parsed.toIso8601String() : DateFormat('yyyy-MM-dd').format(parsed);
  return raw;
}

class FinancePage extends StatefulWidget {
  const FinancePage({super.key, required this.session});

  final AppSession session;

  @override
  State<FinancePage> createState() => _FinancePageState();
}

class _FinancePageState extends State<FinancePage> {
  late Future<List<Map<String, dynamic>>> _future = _load();

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => _reload(),
      child: FutureBuilder<List<Map<String, dynamic>>>(
        future: _future,
        builder: (context, snap) {
          final rows = snap.data ?? [];
          num income = 0;
          num expense = 0;
          for (final row in rows) {
            final amount = num.tryParse(row['amount'].toString()) ?? 0;
            if (row['type'] == 'INCOME') {
              income += amount;
            } else {
              expense += amount;
            }
          }
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              SectionHeader(
                title: 'Finance',
                action: FilledButton.icon(onPressed: _addTransaction, icon: const Icon(Icons.add), label: const Text('Add')),
              ),
              Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  StatCard(label: 'Income', value: money(income), icon: Icons.south_west, color: const Color(0xFF38E0A1)),
                  StatCard(label: 'Expense', value: money(expense), icon: Icons.north_east, color: const Color(0xFFFF7373)),
                  StatCard(label: 'Balance', value: money(income - expense), icon: Icons.account_balance_wallet_outlined),
                ],
              ),
              const SizedBox(height: 12),
              if (snap.connectionState != ConnectionState.done) const LinearProgressIndicator(),
              if (snap.hasError) ErrorBox(message: _message(snap.error!)),
              if (rows.isEmpty && snap.connectionState == ConnectionState.done && !snap.hasError) const EmptyState(),
              for (final row in rows)
                Card(
                  child: ListTile(
                    leading: Icon(row['type'] == 'INCOME' ? Icons.south_west : Icons.north_east),
                    title: Text(row['description']?.toString().isNotEmpty == true ? row['description'].toString() : row['type'].toString()),
                    subtitle: Text('${row['transaction_date'] ?? ''} · ${row['category_name_snapshot'] ?? '-'}'),
                    trailing: Wrap(
                      spacing: 4,
                      crossAxisAlignment: WrapCrossAlignment.center,
                      children: [
                        Text(
                          '${row['type'] == 'INCOME' ? '+' : '-'}${money(num.tryParse(row['amount'].toString()) ?? 0)}',
                          style: TextStyle(color: row['type'] == 'INCOME' ? const Color(0xFF38E0A1) : const Color(0xFFFF7373)),
                        ),
                        IconButton(icon: const Icon(Icons.delete_outline), onPressed: () => _delete(row['id'].toString())),
                      ],
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  Future<List<Map<String, dynamic>>> _load() {
    return widget.session.api.select('transactions', query: {
      'select': '*',
      'is_deleted': 'eq.false',
      'order': 'transaction_date.desc,created_at.desc',
      'limit': '250',
    });
  }

  void _reload() => setState(() => _future = _load());

  Future<void> _addTransaction() async {
    final spec = TableSpec(
      table: 'transactions',
      title: 'Transaction',
      fields: [
        FieldSpec('type', 'Type', kind: FieldKind.select, options: const ['EXPENSE', 'INCOME'], defaultValue: 'EXPENSE'),
        FieldSpec('amount', 'Amount', kind: FieldKind.number),
        FieldSpec('category_name_snapshot', 'Category', optional: true),
        FieldSpec('transaction_date', 'Date', kind: FieldKind.date, defaultValue: DateFormat('yyyy-MM-dd').format(DateTime.now())),
        FieldSpec('description', 'Description', kind: FieldKind.longText, optional: true),
      ],
      titleOf: (r) => 'Transaction',
      subtitleOf: (r) => '',
    );
    final values = await showEditor(context, spec, null);
    if (values == null) return;
    try {
      final payload = await _financePayload(values);
      await widget.session.api.insert('transactions', payload);
      _reload();
    } catch (err) {
      showSnack(context, _message(err));
    }
  }

  Future<Map<String, dynamic>> _financePayload(Map<String, dynamic> values) async {
    final type = values['type'] == 'INCOME' ? 'INCOME' : 'EXPENSE';
    final categoryName = values['category_name_snapshot']?.toString().trim() ?? '';
    String? categoryId;
    if (categoryName.isNotEmpty) {
      final cats = await widget.session.api.select('finance_categories', query: {
        'select': '*',
        'is_deleted': 'eq.false',
        'type': 'eq.$type',
      });
      final existing = _firstOrNull(
        cats.where((c) => c['name'].toString().toLowerCase() == categoryName.toLowerCase()),
      );
      if (existing != null) {
        categoryId = existing['id'].toString();
      } else {
        final cat = await widget.session.api.insert('finance_categories', {
          'name': categoryName,
          'type': type,
          'is_deleted': false,
        });
        categoryId = cat['id'].toString();
      }
    }
    return {
      'type': type,
      'amount': values['amount'] ?? 0,
      'currency': 'IDR',
      'transaction_date': values['transaction_date'] ?? DateFormat('yyyy-MM-dd').format(DateTime.now()),
      'description': values['description'],
      'category_id': categoryId,
      'category_name_snapshot': categoryName.isEmpty ? null : categoryName,
      'is_deleted': false,
    };
  }

  Future<void> _delete(String id) async {
    final ok = await confirm(context, 'Delete transaction?');
    if (!ok) return;
    try {
      await widget.session.api.softDelete('transactions', id);
      _reload();
    } catch (err) {
      showSnack(context, _message(err));
    }
  }
}

class ApprovalsPage extends StatefulWidget {
  const ApprovalsPage({super.key, required this.session});

  final AppSession session;

  @override
  State<ApprovalsPage> createState() => _ApprovalsPageState();
}

class _ApprovalsPageState extends State<ApprovalsPage> {
  late Future<List<Map<String, dynamic>>> _future = _load();

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: () async => _reload(),
      child: FutureBuilder<List<Map<String, dynamic>>>(
        future: _future,
        builder: (context, snap) {
          final rows = snap.data ?? [];
          return ListView(
            padding: const EdgeInsets.all(16),
            children: [
              SectionHeader(title: 'AI Approvals', action: IconButton(onPressed: _reload, icon: const Icon(Icons.refresh))),
              if (snap.connectionState != ConnectionState.done) const LinearProgressIndicator(),
              if (snap.hasError) ErrorBox(message: _message(snap.error!)),
              if (rows.isEmpty && snap.connectionState == ConnectionState.done && !snap.hasError) const EmptyState(),
              for (final row in rows)
                Card(
                  child: Padding(
                    padding: const EdgeInsets.all(14),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          children: [
                            Expanded(child: Text(row['tool_name']?.toString().replaceAll('_', ' ') ?? 'Tool', style: Theme.of(context).textTheme.titleMedium)),
                            Chip(label: Text(row['risk_level']?.toString() ?? 'LOW')),
                          ],
                        ),
                        const SizedBox(height: 8),
                        JsonBlock(row['tool_payload']),
                        if (row['error_message'] != null) ErrorBox(message: row['error_message'].toString()),
                        const SizedBox(height: 10),
                        Row(
                          children: [
                            Expanded(
                              child: FilledButton.icon(
                                onPressed: () => _approve(row),
                                icon: const Icon(Icons.check_circle_outline),
                                label: const Text('Approve'),
                              ),
                            ),
                            const SizedBox(width: 10),
                            IconButton.filledTonal(
                              onPressed: () => _reject(row),
                              icon: const Icon(Icons.close),
                            ),
                          ],
                        ),
                      ],
                    ),
                  ),
                ),
            ],
          );
        },
      ),
    );
  }

  Future<List<Map<String, dynamic>>> _load() {
    return widget.session.api.select('ai_tool_proposals', query: {
      'select': 'id,tool_name,tool_payload,status,risk_level,requires_confirmation,error_message,executed_at,created_at,updated_at',
      'workspace_id': 'eq.${widget.session.workspaceId}',
      'status': 'in.(PENDING,NEEDS_EDIT,FAILED)',
      'order': 'created_at.desc',
    });
  }

  void _reload() => setState(() => _future = _load());

  Future<void> _approve(Map<String, dynamic> proposal) async {
    try {
      final tool = proposal['tool_name'].toString();
      final payload = Map<String, dynamic>.from(proposal['tool_payload'] as Map? ?? {});
      final id = proposal['id'].toString();
      final result = await _executeProposal(tool, payload, id);
      await widget.session.api.update('ai_tool_proposals', id, {
        'status': 'EXECUTED',
        'error_message': null,
        'executed_at': DateTime.now().toUtc().toIso8601String(),
        if (result != null) 'target_entity_id': result,
      });
      _reload();
    } catch (err) {
      showSnack(context, _message(err));
    }
  }

  Future<String?> _executeProposal(String tool, Map<String, dynamic> payload, String proposalId) async {
    if (tool.startsWith('create_transaction')) {
      final row = await widget.session.api.insert('transactions', {
        'type': payload['type']?.toString().toUpperCase() == 'INCOME' ? 'INCOME' : 'EXPENSE',
        'amount': payload['amount'] ?? 0,
        'currency': _currency(payload['currency']),
        'transaction_date': payload['transaction_date'] ?? payload['date'] ?? DateFormat('yyyy-MM-dd').format(DateTime.now()),
        'description': payload['description'],
        'category_name_snapshot': payload['category_id']?.toString(),
        'dedup_key': '$proposalId:0',
        'is_deleted': false,
      });
      return row['id']?.toString();
    }
    if (tool.startsWith('create_task')) {
      final row = await widget.session.api.insert('tasks', {
        'title': payload['title'] ?? 'Task',
        'description': payload['description'],
        'status': payload['status'] ?? 'TODO',
        'priority': payload['priority'] ?? 'NORMAL',
        'due_at': payload['due_at'],
        'is_deleted': false,
      });
      return row['id']?.toString();
    }
    if (tool.startsWith('create_note')) {
      final row = await widget.session.api.insert('notes', {
        'title': payload['title'] ?? 'Note',
        'content': payload['content'],
        'tags': payload['tags'] is List ? payload['tags'] : <String>[],
        'is_pinned': false,
        'is_deleted': false,
      });
      return row['id']?.toString();
    }
    if (tool == 'create_event' || tool == 'create_routine') {
      final row = await widget.session.api.insert('calendar_events', {
        'title': payload['title'] ?? 'Routine',
        'description': payload['description'],
        'start_at': payload['start_at'] ?? DateTime.now().toIso8601String(),
        'end_at': payload['end_at'],
        'all_day': false,
        'repeat_rule': payload['repeat_rule'] ?? 'once',
        'dedup_key': '$proposalId:0',
        'is_deleted': false,
      });
      return row['id']?.toString();
    }
    if (tool == 'create_automation') {
      final row = await widget.session.api.insert('automations', {
        'name': payload['name'] ?? 'Automation',
        'description': payload['description'],
        'trigger_type': payload['trigger_type'] ?? 'manual',
        'action_type': payload['action_type'] ?? 'noop',
        'config': payload['config'] is Map ? payload['config'] : <String, dynamic>{},
        'enabled': false,
        'is_deleted': false,
      });
      return row['id']?.toString();
    }
    throw ApiError('Aksi "$tool" masih butuh desktop bridge.');
  }

  Future<void> _reject(Map<String, dynamic> proposal) async {
    try {
      await widget.session.api.update('ai_tool_proposals', proposal['id'].toString(), {'status': 'REJECTED'});
      _reload();
    } catch (err) {
      showSnack(context, _message(err));
    }
  }
}

class AiChatPage extends StatefulWidget {
  const AiChatPage({super.key, required this.session});

  final AppSession session;

  @override
  State<AiChatPage> createState() => _AiChatPageState();
}

class _AiChatPageState extends State<AiChatPage> {
  final _input = TextEditingController();
  final _messages = <({String role, String text})>[];
  bool _busy = false;

  @override
  void dispose() {
    _input.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Expanded(
          child: ListView(
            padding: const EdgeInsets.all(16),
            children: [
              if (_messages.isEmpty)
                const Card(
                  child: Padding(
                    padding: EdgeInsets.all(16),
                    child: Text('AI chat di Flutter memakai provider cloud langsung dari APK. Simpan API key di Settings. Ollama tetap lewat URL Tailscale/bridge.'),
                  ),
                ),
              for (final msg in _messages)
                Align(
                  alignment: msg.role == 'user' ? Alignment.centerRight : Alignment.centerLeft,
                  child: Container(
                    margin: const EdgeInsets.only(bottom: 10),
                    padding: const EdgeInsets.all(12),
                    constraints: const BoxConstraints(maxWidth: 620),
                    decoration: BoxDecoration(
                      color: msg.role == 'user' ? const Color(0xFF123D3B) : const Color(0xFF111820),
                      borderRadius: BorderRadius.circular(8),
                      border: Border.all(color: const Color(0xFF223040)),
                    ),
                    child: Text(msg.text),
                  ),
                ),
            ],
          ),
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _input,
                    minLines: 1,
                    maxLines: 4,
                    decoration: const InputDecoration(hintText: 'Tanya AllHaven...'),
                    onSubmitted: (_) => _send(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  onPressed: _busy ? null : _send,
                  icon: _busy
                      ? const SizedBox(width: 20, height: 20, child: CircularProgressIndicator(strokeWidth: 2))
                      : const Icon(Icons.send),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _send() async {
    final text = _input.text.trim();
    if (text.isEmpty) return;
    _input.clear();
    setState(() {
      _messages.add((role: 'user', text: text));
      _busy = true;
    });
    try {
      final answer = await DirectAiSettings(widget.session.store).chat(text, _messages);
      setState(() => _messages.add((role: 'assistant', text: answer)));
    } catch (err) {
      setState(() => _messages.add((role: 'assistant', text: _message(err))));
    } finally {
      setState(() => _busy = false);
    }
  }
}

class DirectAiSettings {
  DirectAiSettings(this.store);

  final FlutterSecureStorage store;

  Future<String> chat(String prompt, List<({String role, String text})> history) async {
    final provider = await store.read(key: 'ai_provider') ?? 'openai';
    final key = await store.read(key: '${provider}_api_key');
    final model = await store.read(key: '${provider}_model') ?? (provider == 'openrouter' ? 'openai/gpt-4o-mini' : 'gpt-4o-mini');
    if (key == null || key.trim().isEmpty) {
      throw ApiError('API key belum diisi. Buka Settings → AI Provider.');
    }
    final endpoint = provider == 'openrouter'
        ? 'https://openrouter.ai/api/v1/chat/completions'
        : 'https://api.openai.com/v1/chat/completions';
    final messages = history.take(12).map((m) => {'role': m.role, 'content': m.text}).toList();
    if (messages.isEmpty || messages.last['content'] != prompt) {
      messages.add({'role': 'user', 'content': prompt});
    }
    final res = await http
        .post(
          Uri.parse(endpoint),
          headers: {
            'Content-Type': 'application/json',
            'Authorization': 'Bearer $key',
            if (provider == 'openrouter') 'HTTP-Referer': 'https://allhaven.local',
            if (provider == 'openrouter') 'X-Title': 'AllHaven Mobile',
          },
          body: jsonEncode({'model': model, 'messages': messages}),
        )
        .timeout(const Duration(seconds: 45));
    final body = _decode(res.body);
    if (res.statusCode < 200 || res.statusCode >= 300) {
      throw ApiError(_aiErrorMessage(body, res.body));
    }
    if (body is Map && body['choices'] is List && (body['choices'] as List).isNotEmpty) {
      return ((body['choices'] as List).first['message']?['content'] ?? '').toString().trim();
    }
    throw ApiError('Provider tidak mengirim jawaban.');
  }
}

class SettingsPage extends StatefulWidget {
  const SettingsPage({super.key, required this.session});

  final AppSession session;

  @override
  State<SettingsPage> createState() => _SettingsPageState();
}

class _SettingsPageState extends State<SettingsPage> {
  final _openAiKey = TextEditingController();
  final _openAiModel = TextEditingController(text: 'gpt-4o-mini');
  final _openRouterKey = TextEditingController();
  final _openRouterModel = TextEditingController(text: 'openai/gpt-4o-mini');
  final _bridgeUrl = TextEditingController();
  final _ollamaUrl = TextEditingController();
  final _n8nUrl = TextEditingController();
  String _provider = 'openai';
  String? _bridgeStatus;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  void dispose() {
    _openAiKey.dispose();
    _openAiModel.dispose();
    _openRouterKey.dispose();
    _openRouterModel.dispose();
    _bridgeUrl.dispose();
    _ollamaUrl.dispose();
    _n8nUrl.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        SectionHeader(title: 'Settings'),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Supabase direct', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                InfoRow(icon: Icons.cloud_done_outlined, title: widget.session.workspace?.name ?? 'Workspace', subtitle: 'Auth, tasks, notes, finance, routines, approvals, memory'),
              ],
            ),
          ),
        ),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('AI Provider', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 12),
                SegmentedButton<String>(
                  segments: const [
                    ButtonSegment(value: 'openai', label: Text('OpenAI')),
                    ButtonSegment(value: 'openrouter', label: Text('OpenRouter')),
                  ],
                  selected: {_provider},
                  onSelectionChanged: (s) => setState(() => _provider = s.first),
                ),
                const SizedBox(height: 12),
                TextField(controller: _openAiKey, obscureText: true, decoration: const InputDecoration(labelText: 'OpenAI API key')),
                const SizedBox(height: 10),
                TextField(controller: _openAiModel, decoration: const InputDecoration(labelText: 'OpenAI model')),
                const SizedBox(height: 10),
                TextField(controller: _openRouterKey, obscureText: true, decoration: const InputDecoration(labelText: 'OpenRouter API key')),
                const SizedBox(height: 10),
                TextField(controller: _openRouterModel, decoration: const InputDecoration(labelText: 'OpenRouter model')),
                const SizedBox(height: 12),
                FilledButton.icon(onPressed: _saveAi, icon: const Icon(Icons.save_outlined), label: const Text('Save AI')),
              ],
            ),
          ),
        ),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Bridge only for local services', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                const Text('Ollama dan n8n boleh memakai Tailscale/LAN. Data Supabase tidak memakai bridge ini.'),
                const SizedBox(height: 12),
                TextField(controller: _bridgeUrl, decoration: const InputDecoration(labelText: 'AllHaven bridge URL')),
                const SizedBox(height: 10),
                TextField(controller: _ollamaUrl, decoration: const InputDecoration(labelText: 'Ollama URL')),
                const SizedBox(height: 10),
                TextField(controller: _n8nUrl, decoration: const InputDecoration(labelText: 'n8n URL')),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(child: OutlinedButton.icon(onPressed: _testBridge, icon: const Icon(Icons.network_check), label: const Text('Test bridge'))),
                    const SizedBox(width: 10),
                    Expanded(child: FilledButton.icon(onPressed: _saveBridge, icon: const Icon(Icons.save_outlined), label: const Text('Save bridge'))),
                  ],
                ),
                if (_bridgeStatus != null) ErrorBox(message: _bridgeStatus!),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _load() async {
    final prefs = await SharedPreferences.getInstance();
    _provider = await widget.session.store.read(key: 'ai_provider') ?? 'openai';
    _openAiKey.text = await widget.session.store.read(key: 'openai_api_key') ?? '';
    _openAiModel.text = await widget.session.store.read(key: 'openai_model') ?? 'gpt-4o-mini';
    _openRouterKey.text = await widget.session.store.read(key: 'openrouter_api_key') ?? '';
    _openRouterModel.text = await widget.session.store.read(key: 'openrouter_model') ?? 'openai/gpt-4o-mini';
    _bridgeUrl.text = prefs.getString('bridge_url') ?? '';
    _ollamaUrl.text = prefs.getString('ollama_url') ?? '';
    _n8nUrl.text = prefs.getString('n8n_url') ?? '';
    if (mounted) setState(() {});
  }

  Future<void> _saveAi() async {
    await widget.session.store.write(key: 'ai_provider', value: _provider);
    await widget.session.store.write(key: 'openai_api_key', value: _openAiKey.text.trim());
    await widget.session.store.write(key: 'openai_model', value: _openAiModel.text.trim());
    await widget.session.store.write(key: 'openrouter_api_key', value: _openRouterKey.text.trim());
    await widget.session.store.write(key: 'openrouter_model', value: _openRouterModel.text.trim());
    showSnack(context, 'AI provider saved');
  }

  Future<void> _saveBridge() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('bridge_url', normalizeBridge(_bridgeUrl.text));
    await prefs.setString('ollama_url', _ollamaUrl.text.trim());
    await prefs.setString('n8n_url', _n8nUrl.text.trim());
    showSnack(context, 'Bridge settings saved');
  }

  Future<void> _testBridge() async {
    setState(() => _bridgeStatus = 'Testing...');
    try {
      final base = normalizeBridge(_bridgeUrl.text);
      final res = await http.get(Uri.parse('$base/health')).timeout(const Duration(seconds: 8));
      setState(() => _bridgeStatus = res.statusCode == 200 ? 'Bridge online: ${res.body}' : 'Bridge error ${res.statusCode}: ${res.body}');
    } catch (err) {
      setState(() => _bridgeStatus = 'Bridge unreachable: ${_message(err)}');
    }
  }
}

String normalizeBridge(String value) {
  var v = value.trim().replaceAll(RegExp(r'/+$'), '');
  if (v.endsWith('/health')) v = v.substring(0, v.length - '/health'.length);
  if (!v.endsWith('/api/v1')) v = '$v/api/v1';
  return v;
}

String _currency(Object? value) {
  final raw = (value ?? 'IDR').toString().trim().toUpperCase();
  if (raw.length >= 3) return raw.substring(0, 3);
  return raw.padRight(3, 'X');
}

String _aiErrorMessage(dynamic body, String fallback) {
  if (body is Map) {
    final error = body['error'];
    if (error is Map && error['message'] != null) return error['message'].toString();
    if (body['message'] != null) return body['message'].toString();
  }
  return fallback;
}

class SectionHeader extends StatelessWidget {
  const SectionHeader({super.key, required this.title, this.action});

  final String title;
  final Widget? action;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Row(
        children: [
          Expanded(child: Text(title, style: Theme.of(context).textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.w800))),
          if (action != null) action!,
        ],
      ),
    );
  }
}

class CardList extends StatelessWidget {
  const CardList({super.key, required this.children});

  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Column(
        children: [
          for (var i = 0; i < children.length; i++) ...[
            children[i],
            if (i < children.length - 1) const Divider(height: 1),
          ],
        ],
      ),
    );
  }
}

class InfoRow extends StatelessWidget {
  const InfoRow({
    super.key,
    required this.icon,
    required this.title,
    required this.subtitle,
    this.trailing,
    this.danger = false,
  });

  final IconData icon;
  final String title;
  final String subtitle;
  final String? trailing;
  final bool danger;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, color: danger ? const Color(0xFFFF7373) : Theme.of(context).colorScheme.primary),
      title: Text(title, maxLines: 1, overflow: TextOverflow.ellipsis),
      subtitle: Text(subtitle, maxLines: 2, overflow: TextOverflow.ellipsis),
      trailing: trailing == null ? null : Text(trailing!, style: TextStyle(color: danger ? const Color(0xFFFF7373) : const Color(0xFF38E0A1))),
    );
  }
}

class EmptyLine extends StatelessWidget {
  const EmptyLine(this.text, {super.key});
  final String text;
  @override
  Widget build(BuildContext context) => ListTile(title: Text(text, style: const TextStyle(color: Colors.white54)));
}

class EmptyState extends StatelessWidget {
  const EmptyState({super.key});

  @override
  Widget build(BuildContext context) {
    return const Card(
      child: Padding(
        padding: EdgeInsets.all(20),
        child: Center(child: Text('No data yet')),
      ),
    );
  }
}

class JsonBlock extends StatelessWidget {
  const JsonBlock(this.value, {super.key});

  final Object? value;

  @override
  Widget build(BuildContext context) {
    const encoder = JsonEncoder.withIndent('  ');
    final text = value == null ? '{}' : encoder.convert(value);
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: const Color(0xFF0B1018),
        borderRadius: BorderRadius.circular(8),
        border: Border.all(color: const Color(0xFF223040)),
      ),
      child: Text(text, style: const TextStyle(fontFamily: 'monospace', fontSize: 12)),
    );
  }
}

String money(num value) {
  return NumberFormat.currency(locale: 'id_ID', symbol: 'Rp ', decimalDigits: 0).format(value);
}

String _prettyDateTime(Object? value) {
  final dt = DateTime.tryParse(value?.toString() ?? '');
  if (dt == null) return value?.toString() ?? '';
  return DateFormat('MMM d, HH:mm').format(dt);
}

Future<bool> confirm(BuildContext context, String title) async {
  return await showDialog<bool>(
        context: context,
        builder: (context) => AlertDialog(
          title: Text(title),
          actions: [
            TextButton(onPressed: () => Navigator.pop(context, false), child: const Text('Cancel')),
            FilledButton(onPressed: () => Navigator.pop(context, true), child: const Text('OK')),
          ],
        ),
      ) ??
      false;
}

void showSnack(BuildContext context, String message) {
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(message)));
}
