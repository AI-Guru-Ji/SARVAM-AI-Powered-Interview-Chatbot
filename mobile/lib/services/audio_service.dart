import 'dart:io';
import 'dart:typed_data';

import 'package:audioplayers/audioplayers.dart';
import 'package:path_provider/path_provider.dart';
import 'package:permission_handler/permission_handler.dart';
import 'package:record/record.dart';

/// Thin wrapper around the native mic + speaker.
///
/// Recording: emits WAV files at 16 kHz mono (matches Sarvam STT's
/// AUDIO_SAMPLE_RATE in the existing Python codebase).
/// Playback : streams the current question's TTS WAV from a byte
/// buffer downloaded from the backend.
class AudioService {
  final _recorder = AudioRecorder();
  final _player   = AudioPlayer();

  /// Whether the user has granted RECORD_AUDIO. Should be called once
  /// from the setup screen before any recording attempt.
  Future<bool> ensureMicPermission() async {
    final status = await Permission.microphone.request();
    return status.isGranted;
  }

  // ── Recording ──────────────────────────────────────────────────────
  Future<void> startRecording() async {
    final dir = await getTemporaryDirectory();
    final path = '${dir.path}/answer_${DateTime.now().millisecondsSinceEpoch}.wav';
    await _recorder.start(
      const RecordConfig(
        encoder: AudioEncoder.wav,
        sampleRate: 16000,
        numChannels: 1,
      ),
      path: path,
    );
  }

  Future<File?> stopRecording() async {
    final path = await _recorder.stop();
    if (path == null) return null;
    return File(path);
  }

  Future<bool> get isRecording => _recorder.isRecording();

  // ── Playback ───────────────────────────────────────────────────────
  /// Play the given WAV bytes. Useful for the question audio the
  /// backend streamed back to us.
  Future<void> playBytes(Uint8List bytes) async {
    await _player.stop();
    await _player.play(BytesSource(bytes));
  }

  Future<void> stopPlayback() => _player.stop();

  /// Future that completes when playback naturally ends. Useful to
  /// auto-enable the record button only after the question has been
  /// heard.
  Stream<void> get onPlaybackComplete => _player.onPlayerComplete;

  // ── Cleanup ────────────────────────────────────────────────────────
  Future<void> dispose() async {
    await _recorder.dispose();
    await _player.dispose();
  }
}
