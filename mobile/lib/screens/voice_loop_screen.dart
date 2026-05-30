import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../config.dart';
import '../state/providers.dart';
import '../widgets/stage_progress.dart';

/// Voice loop — the same widget handles profile, technical interview,
/// and behavioral round, because the only thing that changes between
/// them is the question text returned by the backend.
///
/// Lifecycle on every turn:
///   1. Display the current question text from the session state.
///   2. Download + autoplay the question's TTS WAV.
///   3. When playback ends, enable the record button.
///   4. User taps record → record WAV with the mic.
///   5. User taps stop → upload WAV → backend STT + advance FSM.
///   6. New session state arrives → repeat from (1) with the next Q.
class VoiceLoopScreen extends ConsumerStatefulWidget {
  const VoiceLoopScreen({super.key});
  @override
  ConsumerState<VoiceLoopScreen> createState() => _VoiceLoopScreenState();
}

class _VoiceLoopScreenState extends ConsumerState<VoiceLoopScreen> {
  bool _isPlaying = false;
  bool _isRecording = false;
  bool _isUploading = false;
  String? _lastTranscript;
  // Dedupe by question TEXT, not audio URL — the backend reuses the
  // same /audio endpoint for every turn (different state, same URL),
  // so URL-based dedupe would skip Q2 onwards. Question text is unique.
  String? _textPlayed;
  String? _error;
  // Set true when the candidate's recording was too short to be real
  // audio (likely silence). Surfaces a Retry / Skip banner.
  bool _showEmptyRetry = false;
  // Cache the last recorded file so the Skip button can still upload
  // it (advancing the FSM with an empty transcript).
  dynamic _pendingFile;

  // Minimum bytes for the candidate's WAV to be considered "real audio".
  // 16 kHz mono PCM → ~32 KB/sec; <8KB is well under 250ms of speech.
  static const int _minRealAudioBytes = 8000;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      // 1) Set up "playback finished" listener once.
      final audio = ref.read(audioServiceProvider);
      audio.onPlaybackComplete.listen((_) {
        if (mounted) setState(() => _isPlaying = false);
      });
      // 2) Ask for mic permission up front so the user doesn't have to
      //    interrupt playback later when they tap Record.
      await audio.ensureMicPermission();
      // 3) Play the first question.
      _maybePlayQuestion();
    });
  }

  Future<void> _maybePlayQuestion({bool force = false}) async {
    final session = ref.read(sessionProvider);
    final audio = ref.read(audioServiceProvider);
    final api = ref.read(apiClientProvider);
    if (session?.currentQuestion == null) return;
    final text = session!.currentQuestion!.text;
    if (!force && text == _textPlayed) return;   // same question still showing
    _textPlayed = text;
    setState(() => _isPlaying = true);
    try {
      // The backend may need a moment to generate the WAV (lazy TTS).
      // The dio client has 30s receive timeout which is plenty.
      final bytes = await api.downloadAudio(session.currentQuestion!.audioUrl);
      await audio.playBytes(Uint8List.fromList(bytes));
    } catch (e) {
      setState(() {
        _error = 'Could not play question audio: $e';
        _isPlaying = false;
      });
    }
  }

  Future<void> _toggleRecording() async {
    // Subtle vibration so the button feels alive when tapped.
    HapticFeedback.mediumImpact();
    final audio = ref.read(audioServiceProvider);
    if (_isRecording) {
      // Stop & evaluate before uploading
      setState(() {
        _isRecording = false;
        _isUploading = true;
        _error = null;
      });
      try {
        final file = await audio.stopRecording();
        if (file == null) {
          setState(() => _error = 'Recording failed — try again.');
          return;
        }
        // Client-side guard: reject recordings too short to be real
        // speech BEFORE wasting a Sarvam STT call. Stash the file so the
        // user can choose to skip-with-it anyway.
        final size = await file.length();
        if (size < _minRealAudioBytes) {
          setState(() {
            _isUploading = false;
            _showEmptyRetry = true;
            _pendingFile = file;
          });
          return;
        }
        await ref.read(sessionProvider.notifier).submitAnswer(file);
        final session = ref.read(sessionProvider);
        setState(() {
          _lastTranscript = session?.lastTranscript;
        });
        // Auto-play the next question if the FSM produced one
        await _maybePlayQuestion();
        _routeForStage();
      } catch (e) {
        setState(() => _error = 'Could not upload answer: $e');
      } finally {
        setState(() => _isUploading = false);
      }
    } else {
      setState(() {
        _error = null;
        _showEmptyRetry = false;
        _pendingFile = null;
      });
      await audio.startRecording();
      setState(() => _isRecording = true);
    }
  }

  void _routeForStage() {
    final session = ref.read(sessionProvider);
    if (session == null || !mounted) return;
    if (session.stage == 'profile_review') {
      GoRouter.of(context).go('/resume');
    } else if (session.stage == 'behavioral_intro') {
      GoRouter.of(context).go('/behavioral-intro');
    } else if (session.isAwaitingFinalize) {
      GoRouter.of(context).go('/finalize');
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(sessionProvider);
    if (session == null) {
      return const Scaffold(
        body: Center(child: CircularProgressIndicator()),
      );
    }
    // Auto-play whenever the *question text* changes (dedupe in
    // _maybePlayQuestion compares text, so this fires only on a
    // genuinely new turn — no infinite-loop risk).
    WidgetsBinding.instance.addPostFrameCallback((_) => _maybePlayQuestion());

    return Scaffold(
      appBar: AppBar(
        title: Text(_stageLabel(session.stage)),
        actions: [
          IconButton(
            tooltip: 'Abort',
            icon: const Icon(Icons.close),
            onPressed: _confirmAbort,
          ),
        ],
      ),
      body: Column(
        children: [
          StageProgress(
            currentStage: session.stage,
            progress: session.progress,
          ),
          Expanded(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(20),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  if (session.currentQuestion != null) ...[
                    _BotBubble(
                      text: session.currentQuestion!.text,
                      isSpeaking: _isPlaying,
                    ),
                    const SizedBox(height: 8),
                    Align(
                      alignment: Alignment.centerLeft,
                      child: TextButton.icon(
                        icon: const Icon(Icons.replay, size: 18),
                        label: const Text('Replay question'),
                        onPressed: _isPlaying || _isUploading
                            ? null
                            : () => _maybePlayQuestion(force: true),
                      ),
                    ),
                  ],
                  if (_lastTranscript != null && _lastTranscript!.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    Text(
                      'You said:',
                      style: TextStyle(
                        fontSize: 12,
                        color: Colors.grey[600],
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    _UserBubble(text: _lastTranscript!),
                  ],
                  const SizedBox(height: 16),
                  if (_showEmptyRetry)
                    _EmptyRetryBanner(
                      onTryAgain: () {
                        setState(() {
                          _showEmptyRetry = false;
                          _pendingFile = null;
                        });
                      },
                      onSkip: () async {
                        // Submit the (tiny) recording anyway so the
                        // FSM advances with an empty transcript. The
                        // backend / state-machine handle empty.
                        if (_pendingFile == null) {
                          setState(() => _showEmptyRetry = false);
                          return;
                        }
                        setState(() {
                          _showEmptyRetry = false;
                          _isUploading = true;
                        });
                        try {
                          await ref
                              .read(sessionProvider.notifier)
                              .submitAnswer(_pendingFile);
                          await _maybePlayQuestion();
                          _routeForStage();
                        } catch (e) {
                          setState(() => _error = 'Could not skip: $e');
                        } finally {
                          setState(() {
                            _isUploading = false;
                            _pendingFile = null;
                          });
                        }
                      },
                    ),
                  if (_error != null)
                    Container(
                      padding: const EdgeInsets.all(10),
                      decoration: BoxDecoration(
                        color: const Color(0xFFFEF2F2),
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        _error!,
                        style: const TextStyle(color: Color(0xFFB91C1C)),
                      ),
                    ),
                ],
              ),
            ),
          ),
          Padding(
            padding: const EdgeInsets.all(24),
            child: _RecordButton(
              isRecording: _isRecording,
              isBusy: _isUploading || _isPlaying,
              onTap: _toggleRecording,
            ),
          ),
        ],
      ),
    );
  }

  String _stageLabel(String stage) {
    switch (stage) {
      case 'profile':    return 'Onboarding (1/3)';
      case 'interview':  return 'Technical interview (2/3)';
      case 'behavioral': return 'Personality round (3/3)';
      default:           return 'ShramSaathi';
    }
  }

  void _confirmAbort() {
    showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('End interview?'),
        content: const Text('Your answers so far will be discarded.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx, false),
            child: const Text('Keep going'),
          ),
          TextButton(
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('End'),
          ),
        ],
      ),
    ).then((confirmed) async {
      if (confirmed == true) {
        await ref.read(sessionProvider.notifier).abort();
        if (mounted) GoRouter.of(context).go('/');
      }
    });
  }
}

// ──────────────────────────────────────────────────────────────────────
// Sub-widgets
// ──────────────────────────────────────────────────────────────────────
class _EmptyRetryBanner extends StatelessWidget {
  const _EmptyRetryBanner({required this.onTryAgain, required this.onSkip});
  final VoidCallback onTryAgain;
  final VoidCallback onSkip;
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.all(14),
      decoration: BoxDecoration(
        color: const Color(0xFFFEF3C7),
        borderRadius: BorderRadius.circular(10),
        border: Border.all(color: const Color(0xFFFCD34D)),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Row(
            children: [
              Icon(Icons.mic_off_outlined, color: Color(0xFF92400E)),
              SizedBox(width: 10),
              Expanded(
                child: Text(
                  "I couldn't hear you clearly. Try again, or skip this "
                  'question if you prefer.',
                  style: TextStyle(
                    color: Color(0xFF92400E),
                    fontSize: 13,
                    height: 1.4,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          Row(
            children: [
              Expanded(
                child: OutlinedButton.icon(
                  onPressed: onTryAgain,
                  icon: const Icon(Icons.refresh),
                  label: const Text('Try again'),
                ),
              ),
              const SizedBox(width: 8),
              Expanded(
                child: TextButton.icon(
                  onPressed: onSkip,
                  icon: const Icon(Icons.skip_next_outlined),
                  label: const Text('Skip'),
                ),
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _BotBubble extends StatefulWidget {
  const _BotBubble({required this.text, this.isSpeaking = false});
  final String text;
  final bool isSpeaking;
  @override
  State<_BotBubble> createState() => _BotBubbleState();
}

class _BotBubbleState extends State<_BotBubble>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1100),
    );
    if (widget.isSpeaking) _pulse.repeat(reverse: true);
  }

  @override
  void didUpdateWidget(covariant _BotBubble old) {
    super.didUpdateWidget(old);
    if (widget.isSpeaking && !_pulse.isAnimating) {
      _pulse.repeat(reverse: true);
    } else if (!widget.isSpeaking && _pulse.isAnimating) {
      _pulse.stop();
      _pulse.value = 0;
    }
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        AnimatedBuilder(
          animation: _pulse,
          builder: (_, __) => Container(
            padding: EdgeInsets.all(widget.isSpeaking ? 4 * _pulse.value : 0),
            decoration: BoxDecoration(
              shape: BoxShape.circle,
              gradient: widget.isSpeaking
                  ? RadialGradient(
                      colors: [
                        Color(AppConfig.primaryColorValue).withValues(
                          alpha: 0.40 * (1 - _pulse.value),
                        ),
                        Colors.transparent,
                      ],
                    )
                  : null,
            ),
            child: CircleAvatar(
              backgroundColor: Color(AppConfig.primaryColorValue),
              radius: 20,
              child: const Icon(Icons.mic, color: Colors.white, size: 20),
            ),
          ),
        ),
        const SizedBox(width: 10),
        Flexible(
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFFEEF2FF),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(widget.text,
                style: const TextStyle(fontSize: 16, height: 1.4)),
          ),
        ),
      ],
    );
  }
}

class _UserBubble extends StatelessWidget {
  const _UserBubble({required this.text});
  final String text;
  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.end,
      children: [
        Flexible(
          child: Container(
            padding: const EdgeInsets.all(12),
            decoration: BoxDecoration(
              color: const Color(0xFFF4F4F5),
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(text, style: const TextStyle(fontSize: 15, height: 1.4)),
          ),
        ),
      ],
    );
  }
}

class _RecordButton extends StatefulWidget {
  const _RecordButton({
    required this.isRecording,
    required this.isBusy,
    required this.onTap,
  });
  final bool isRecording;
  final bool isBusy;
  final VoidCallback onTap;

  @override
  State<_RecordButton> createState() => _RecordButtonState();
}

class _RecordButtonState extends State<_RecordButton>
    with SingleTickerProviderStateMixin {
  late final AnimationController _pulse;

  @override
  void initState() {
    super.initState();
    _pulse = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _pulse.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final colour = widget.isRecording
        ? const Color(0xFFEF4444)
        : Color(AppConfig.primaryColorValue);
    return GestureDetector(
      onTap: widget.isBusy ? null : widget.onTap,
      child: Stack(
        alignment: Alignment.center,
        children: [
          if (widget.isRecording)
            AnimatedBuilder(
              animation: _pulse,
              builder: (_, __) => Container(
                height: 76 + (24 * _pulse.value),
                width: double.infinity,
                margin: EdgeInsets.symmetric(horizontal: 24 - (12 * _pulse.value)),
                decoration: BoxDecoration(
                  color: const Color(0xFFEF4444).withValues(
                    alpha: 0.20 * (1 - _pulse.value),
                  ),
                  borderRadius: BorderRadius.circular(50),
                ),
              ),
            ),
          AnimatedContainer(
            duration: const Duration(milliseconds: 200),
            height: 76,
            width: double.infinity,
            decoration: BoxDecoration(
              color: widget.isBusy ? Colors.grey : colour,
              borderRadius: BorderRadius.circular(38),
              boxShadow: [
                BoxShadow(
                  color: colour.withValues(alpha: 0.35),
                  blurRadius: 12,
                  offset: const Offset(0, 4),
                ),
              ],
            ),
            child: Center(
              child: widget.isBusy
                  ? const SizedBox(
                      width: 28, height: 28,
                      child: CircularProgressIndicator(
                        color: Colors.white, strokeWidth: 3,
                      ),
                    )
                  : Row(
                      mainAxisAlignment: MainAxisAlignment.center,
                      children: [
                        Icon(
                          widget.isRecording ? Icons.stop : Icons.mic,
                          color: Colors.white,
                          size: 28,
                        ),
                        const SizedBox(width: 12),
                        Text(
                          widget.isRecording
                              ? 'Stop & submit'
                              : 'Tap to answer',
                          style: const TextStyle(
                            color: Colors.white,
                            fontSize: 17,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                      ],
                    ),
            ),
          ),
        ],
      ),
    );
  }
}
