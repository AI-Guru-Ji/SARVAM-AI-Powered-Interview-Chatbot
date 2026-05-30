import 'dart:io';

import 'package:dio/dio.dart';

import '../config.dart';
import '../models/api_models.dart';


/// Network exception surfaced to the UI when even the retries
/// exhaust. UI layers should catch this and show an "offline" banner
/// instead of the raw DioException.
class OfflineException implements Exception {
  OfflineException(this.message);
  final String message;
  @override
  String toString() => message;
}


/// Retry interceptor — transparent retries on transient network
/// failures (connection timeouts, DNS failures, "no route to host"
/// etc.) with a short exponential backoff.
class _RetryInterceptor extends Interceptor {
  _RetryInterceptor(this._dio, {this.maxRetries = 2});
  final Dio _dio;
  final int maxRetries;

  bool _isRetryable(DioException err) {
    if (err.type == DioExceptionType.connectionTimeout ||
        err.type == DioExceptionType.sendTimeout ||
        err.type == DioExceptionType.receiveTimeout ||
        err.type == DioExceptionType.connectionError) {
      return true;
    }
    final status = err.response?.statusCode ?? 0;
    return status >= 500 && status < 600;   // server hiccups
  }

  @override
  Future<void> onError(
    DioException err, ErrorInterceptorHandler handler,
  ) async {
    final attempt = (err.requestOptions.extra['_retry_count'] ?? 0) as int;
    if (attempt >= maxRetries || !_isRetryable(err)) {
      // Map exhausted retries to a friendlier exception for the UI.
      if (_isRetryable(err)) {
        return handler.reject(
          DioException(
            requestOptions: err.requestOptions,
            error: OfflineException(
              'Could not reach the server. Check your internet and try again.',
            ),
            type: err.type,
            response: err.response,
          ),
        );
      }
      return handler.next(err);
    }
    final backoff = Duration(milliseconds: 400 * (1 << attempt));
    await Future.delayed(backoff);
    final opts = err.requestOptions.copyWith();
    opts.extra['_retry_count'] = attempt + 1;
    try {
      final response = await _dio.fetch<dynamic>(opts);
      return handler.resolve(response);
    } on DioException catch (e) {
      return handler.reject(e);
    }
  }
}

/// Single HTTP client to talk to the FastAPI backend.
///
/// All endpoints live in this one class so a future refactor can swap
/// the underlying transport (e.g. WebSocket for progress streaming)
/// without touching the UI layer.
class ApiClient {
  final Dio _dio;

  ApiClient({String? token})
      : _dio = Dio(BaseOptions(
          baseUrl: AppConfig.backendUrl,
          connectTimeout: const Duration(seconds: 10),
          // Generous default; /finalize overrides this to 4 min because
          // Sarvam can take 60-180s for a Hindi/Indic interview (Devanagari
          // tokens are ~3× the budget of English).
          receiveTimeout: const Duration(seconds: 90),
          sendTimeout: const Duration(seconds: 60),
          headers: {
            if (AppConfig.backendApiKey.isNotEmpty || (token?.isNotEmpty ?? false))
              'Authorization': 'Bearer ${token?.isNotEmpty == true ? token : AppConfig.backendApiKey}',
          },
        )) {
    // Retry transient network errors twice before giving up. Saves a
    // demo from a single dropped Wi-Fi packet.
    _dio.interceptors.add(_RetryInterceptor(_dio));
  }

  // ── Health & config ────────────────────────────────────────────────
  Future<HealthResponse> health() async {
    final r = await _dio.get('/v1/health');
    return HealthResponse.fromJson(r.data as Map<String, dynamic>);
  }

  Future<ConfigResponse> config() async {
    final r = await _dio.get('/v1/config');
    return ConfigResponse.fromJson(r.data as Map<String, dynamic>);
  }

  // ── Auth ───────────────────────────────────────────────────────────
  Future<OtpRequestResult> requestOtp({
    required String phone,
    required String language,
  }) async {
    final r = await _dio.post('/v1/auth/otp/request', data: {
      'phone': phone,
      'language': language,
    });
    return OtpRequestResult.fromJson(r.data as Map<String, dynamic>);
  }

  Future<OtpVerifyResult> verifyOtp({
    required String phone,
    required String otp,
  }) async {
    final r = await _dio.post('/v1/auth/otp/verify', data: {
      'phone': phone,
      'otp': otp,
    });
    return OtpVerifyResult.fromJson(r.data as Map<String, dynamic>);
  }

  // ── Sessions ───────────────────────────────────────────────────────
  Future<SessionState> createSession({
    required String role,
    required String language,
    required String candidateName,
    required String candidatePhone,
    required String recruiterEmail,
  }) async {
    final r = await _dio.post('/v1/sessions', data: {
      'role': role,
      'language': language,
      'candidate_name': candidateName,
      'candidate_phone': candidatePhone,
      'recruiter_email': recruiterEmail,
    });
    return SessionState.fromJson(r.data as Map<String, dynamic>);
  }

  Future<SessionState> getSession(String sessionId) async {
    final r = await _dio.get('/v1/sessions/$sessionId');
    return SessionState.fromJson(r.data as Map<String, dynamic>);
  }

  Future<void> abortSession(String sessionId) async {
    await _dio.delete('/v1/sessions/$sessionId');
  }

  // ── Answers + audio ────────────────────────────────────────────────
  Future<SessionState> submitAnswer({
    required String sessionId,
    required File audio,
  }) async {
    final form = FormData.fromMap({
      'audio': await MultipartFile.fromFile(
        audio.path,
        filename: 'answer.wav',
      ),
    });
    final r = await _dio.post(
      '/v1/sessions/$sessionId/answer',
      data: form,
      options: Options(contentType: 'multipart/form-data'),
    );
    return SessionState.fromJson(r.data as Map<String, dynamic>);
  }

  /// Download the current question's TTS WAV. The audio URL is whatever
  /// the backend returned in `SessionState.currentQuestion.audioUrl`.
  Future<List<int>> downloadAudio(String url) async {
    final r = await _dio.get<List<int>>(
      url,
      options: Options(responseType: ResponseType.bytes),
    );
    return r.data ?? <int>[];
  }

  // ── Resume (candidate-side, generated at end of profile loop) ─────
  Future<String> fetchResumeText(String sessionId) async {
    final r = await _dio.get('/v1/sessions/$sessionId/resume.text');
    return (r.data['text'] ?? '') as String;
  }

  Future<List<int>> downloadResumePdf(String sessionId) async {
    final r = await _dio.get<List<int>>(
      '/v1/sessions/$sessionId/resume.pdf',
      options: Options(responseType: ResponseType.bytes),
    );
    return r.data ?? <int>[];
  }

  Future<SessionState> advancePastReview(String sessionId) async {
    final r = await _dio.post('/v1/sessions/$sessionId/advance');
    return SessionState.fromJson(r.data as Map<String, dynamic>);
  }

  // ── Report (recruiter side, also surfaced to candidate post-finalize) ──
  Future<Map<String, dynamic>> fetchReport(String sessionId) async {
    final r = await _dio.get('/v1/sessions/$sessionId/report');
    return r.data as Map<String, dynamic>;
  }

  Future<List<int>> downloadReportPdf(String sessionId) async {
    final r = await _dio.get<List<int>>(
      '/v1/sessions/$sessionId/report.pdf',
      options: Options(responseType: ResponseType.bytes),
    );
    return r.data ?? <int>[];
  }

  // ── Finalize ───────────────────────────────────────────────────────
  Future<SessionState> finalize(String sessionId) async {
    // /finalize triggers BOTH evaluations (technical + behavioral) on the
    // server. Hindi/Indic interviews can take 2-3 minutes because
    // Devanagari tokens cost ~3× the English budget. Override the
    // default 90s receive timeout to 4 minutes for this call only.
    final r = await _dio.post(
      '/v1/sessions/$sessionId/finalize',
      options: Options(
        receiveTimeout: const Duration(minutes: 4),
        sendTimeout: const Duration(minutes: 4),
      ),
    );
    return SessionState.fromJson(r.data as Map<String, dynamic>);
  }
}
