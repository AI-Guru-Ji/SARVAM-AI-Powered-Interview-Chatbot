/// Dart mirrors of the FastAPI Pydantic response models.
///
/// Keep field names in sync with `ui/fastapi/schemas.py` — anything
/// the backend renames here must be renamed there too (or the JSON
/// decoders below adjusted).

class RoleOption {
  final String key;
  final String title;
  const RoleOption({required this.key, required this.title});
  factory RoleOption.fromJson(Map<String, dynamic> j) =>
      RoleOption(key: j['key'], title: j['title']);
}

class LanguageOption {
  final String code;
  final String label;
  final String bcp47;
  const LanguageOption({required this.code, required this.label, required this.bcp47});
  factory LanguageOption.fromJson(Map<String, dynamic> j) => LanguageOption(
        code: j['code'],
        label: j['label'],
        bcp47: j['bcp47'],
      );
}

class ConfigResponse {
  final List<RoleOption> roles;
  final List<LanguageOption> languages;
  final int behavioralQuestionCount;
  final int profileQuestionCount;
  const ConfigResponse({
    required this.roles,
    required this.languages,
    required this.behavioralQuestionCount,
    required this.profileQuestionCount,
  });
  factory ConfigResponse.fromJson(Map<String, dynamic> j) => ConfigResponse(
        roles: (j['roles'] as List).map((e) => RoleOption.fromJson(e)).toList(),
        languages: (j['languages'] as List)
            .map((e) => LanguageOption.fromJson(e))
            .toList(),
        behavioralQuestionCount: j['behavioral_question_count'],
        profileQuestionCount: j['profile_question_count'],
      );
}

class QuestionInfo {
  final String text;
  final String audioUrl;
  const QuestionInfo({required this.text, required this.audioUrl});
  factory QuestionInfo.fromJson(Map<String, dynamic> j) => QuestionInfo(
        text: j['text'],
        audioUrl: j['audio_url'],
      );
}

class SessionState {
  final String sessionId;
  final String stage;
  final double progress;
  final bool isTerminal;
  final String candidateName;
  final String role;
  final String language;
  final QuestionInfo? currentQuestion;
  final String? finalReportUrl;
  final String lastTranscript;

  const SessionState({
    required this.sessionId,
    required this.stage,
    required this.progress,
    required this.isTerminal,
    required this.candidateName,
    required this.role,
    required this.language,
    required this.currentQuestion,
    required this.finalReportUrl,
    this.lastTranscript = '',
  });

  factory SessionState.fromJson(Map<String, dynamic> j) => SessionState(
        sessionId: j['session_id'],
        stage: j['stage'],
        progress: (j['progress'] as num).toDouble(),
        isTerminal: j['is_terminal'] ?? false,
        candidateName: j['candidate_name'],
        role: j['role'],
        language: j['language'],
        currentQuestion: j['current_question'] == null
            ? null
            : QuestionInfo.fromJson(j['current_question']),
        finalReportUrl: j['final_report_url'],
        lastTranscript: j['last_transcript'] ?? '',
      );

  bool get isAwaitingFinalize => stage == 'awaiting_finalize';
  bool get isCompleted        => stage == 'completed';
  bool get isProfileReview    => stage == 'profile_review';
}

class OtpRequestResult {
  final bool ok;
  final String message;
  final String? demoOtp;
  const OtpRequestResult({required this.ok, required this.message, this.demoOtp});
  factory OtpRequestResult.fromJson(Map<String, dynamic> j) => OtpRequestResult(
        ok: j['ok'],
        message: j['message'],
        demoOtp: j['demo_otp'],
      );
}

class OtpVerifyResult {
  final bool ok;
  final String token;
  final String candidatePhone;
  const OtpVerifyResult({
    required this.ok,
    required this.token,
    required this.candidatePhone,
  });
  factory OtpVerifyResult.fromJson(Map<String, dynamic> j) => OtpVerifyResult(
        ok: j['ok'],
        token: j['token'],
        candidatePhone: j['candidate_phone'],
      );
}

class HealthResponse {
  final bool ok;
  final bool sarvamOk;
  final bool dbOk;
  final bool demoMode;
  const HealthResponse({
    required this.ok,
    required this.sarvamOk,
    required this.dbOk,
    required this.demoMode,
  });
  factory HealthResponse.fromJson(Map<String, dynamic> j) => HealthResponse(
        ok: j['ok'],
        sarvamOk: j['sarvam_ok'],
        dbOk: j['db_ok'],
        demoMode: j['demo_mode'],
      );
}
