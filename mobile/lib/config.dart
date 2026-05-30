/// Compile-time configuration for the ShramSaathi AI Android client.
///
/// All environment-specific values live here. To point the app at a
/// different backend (Render staging, ngrok during a demo, production
/// Cloud Run, ...) override at build time:
///
///   flutter build apk --dart-define=BACKEND_URL=https://api.example.com
///
class AppConfig {
  /// Base URL of the FastAPI backend. Default targets a local dev server
  /// reached from the Android emulator via the 10.0.2.2 loopback alias.
  /// On a physical device replace with your laptop's LAN IP, your ngrok
  /// URL, or the deployed Render URL.
  static const String backendUrl = String.fromEnvironment(
    'BACKEND_URL',
    defaultValue: 'http://10.0.2.2:8000',
  );

  /// Static API key for the backend's `Authorization: Bearer …` gate.
  /// Empty by default — the backend treats empty as "auth disabled"
  /// which is what we want for local demo. Set at build time for prod.
  static const String backendApiKey = String.fromEnvironment(
    'BACKEND_API_KEY',
    defaultValue: '',
  );

  /// Sentry DSN for crash reporting. Empty → Sentry is a no-op (used
  /// during local dev). Set at release build time:
  ///   flutter build apk --dart-define=SENTRY_DSN=https://...@sentry.io/...
  static const String sentryDsn = String.fromEnvironment(
    'SENTRY_DSN',
    defaultValue: '',
  );

  /// Brand colour palette — matches the Streamlit dashboard.
  static const int primaryColorValue = 0xFF6366F1;
  static const int accentColorValue  = 0xFF06B6D4;
  static const int successColorValue = 0xFF10B981;
  static const int dangerColorValue  = 0xFFEF4444;
}
