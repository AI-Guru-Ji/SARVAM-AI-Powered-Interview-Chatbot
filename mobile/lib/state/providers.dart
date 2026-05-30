import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../services/api_client.dart';
import '../services/audio_service.dart';
import '../models/api_models.dart';

/// Riverpod glue. Holds the small handful of long-lived singletons +
/// the per-session state controller.
///
/// The state controller exposes a ``SessionState?`` — null before
/// /sessions has been called. Screens listen and rebuild on change.

// ── Shared services ───────────────────────────────────────────────────
final apiClientProvider = Provider<ApiClient>((ref) {
  final token = ref.watch(authTokenProvider);
  return ApiClient(token: token);
});

final audioServiceProvider = Provider<AudioService>((ref) {
  final svc = AudioService();
  ref.onDispose(svc.dispose);
  return svc;
});

final sharedPrefsProvider = FutureProvider<SharedPreferences>(
  (ref) => SharedPreferences.getInstance(),
);

// ── Auth ──────────────────────────────────────────────────────────────
final authTokenProvider = StateProvider<String?>((ref) => null);
final candidatePhoneProvider = StateProvider<String?>((ref) => null);

// ── Server-config (roles + languages) ────────────────────────────────
final configProvider = FutureProvider<ConfigResponse>((ref) async {
  final api = ref.watch(apiClientProvider);
  return api.config();
});

// ── Active interview session ─────────────────────────────────────────
class SessionController extends StateNotifier<SessionState?> {
  SessionController(this._api) : super(null);
  final ApiClient _api;

  static const _kSessionIdKey = 'shramsaathi_session_id';

  Future<void> startNewSession({
    required String role,
    required String language,
    required String candidateName,
    required String candidatePhone,
    required String recruiterEmail,
  }) async {
    state = await _api.createSession(
      role: role,
      language: language,
      candidateName: candidateName,
      candidatePhone: candidatePhone,
      recruiterEmail: recruiterEmail,
    );
    // Persist so we can resume after app kill / phone reboot.
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kSessionIdKey, state!.sessionId);
  }

  Future<void> refresh() async {
    if (state == null) return;
    state = await _api.getSession(state!.sessionId);
  }

  /// Try to restore a session from disk on app launch. Returns the
  /// restored stage name so the caller can navigate to the right
  /// screen, or null if nothing to resume.
  Future<String?> tryRestore() async {
    final prefs = await SharedPreferences.getInstance();
    final sid = prefs.getString(_kSessionIdKey);
    if (sid == null || sid.isEmpty) return null;
    try {
      state = await _api.getSession(sid);
      // Don't resume sessions that are already completed.
      if (state!.isCompleted) {
        await prefs.remove(_kSessionIdKey);
        state = null;
        return null;
      }
      return state!.stage;
    } catch (_) {
      // Backend doesn't have it anymore (DB cleared, server restarted
      // in demo) — silently drop the stale id.
      await prefs.remove(_kSessionIdKey);
      state = null;
      return null;
    }
  }

  Future<void> submitAnswer(dynamic audioFile) async {
    if (state == null) return;
    state = await _api.submitAnswer(
      sessionId: state!.sessionId,
      audio: audioFile,
    );
  }

  Future<void> finalize() async {
    if (state == null) return;
    state = await _api.finalize(state!.sessionId);
  }

  Future<void> advancePastReview() async {
    if (state == null) return;
    state = await _api.advancePastReview(state!.sessionId);
  }

  Future<void> abort() async {
    if (state == null) return;
    try {
      await _api.abortSession(state!.sessionId);
    } catch (_) {}
    state = null;
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kSessionIdKey);
  }
}

final sessionProvider =
    StateNotifierProvider<SessionController, SessionState?>((ref) {
  return SessionController(ref.watch(apiClientProvider));
});
