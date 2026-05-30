import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../config.dart';
import '../state/providers.dart';

/// Behavioral-intro screen — shown after the candidate finishes the
/// last technical question. Mirrors the web app's "Begin behavioral
/// round (5 questions)" button. Acts as a deliberate breather so the
/// candidate knows the format is about to change from skill-based
/// questions to personality scenarios.
class BehavioralIntroScreen extends ConsumerStatefulWidget {
  const BehavioralIntroScreen({super.key});
  @override
  ConsumerState<BehavioralIntroScreen> createState() =>
      _BehavioralIntroScreenState();
}

class _BehavioralIntroScreenState extends ConsumerState<BehavioralIntroScreen> {
  bool _advancing = false;
  String? _error;

  Future<void> _begin() async {
    setState(() {
      _advancing = true;
      _error = null;
    });
    try {
      await ref.read(sessionProvider.notifier).advancePastReview();
      if (!mounted) return;
      GoRouter.of(context).go('/loop');
    } catch (e) {
      setState(() {
        _error = 'Could not start the round: $e';
        _advancing = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              const Icon(Icons.psychology_outlined,
                  size: 96, color: Color(0xFF6366F1)),
              const SizedBox(height: 24),
              const Text(
                'Technical round complete ✓',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
              ),
              const SizedBox(height: 12),
              const Text(
                'Now we will move to the personality round.\n\n'
                '5 short scenario-based questions to understand how you '
                'handle real workplace situations — honesty, reliability, '
                'stress, customer focus, and earning attitude.\n\n'
                'There are no right or wrong answers. Just be honest.',
                textAlign: TextAlign.center,
                style: TextStyle(fontSize: 15, height: 1.55,
                                 color: Color(0xFF52525B)),
              ),
              const SizedBox(height: 36),
              ElevatedButton(
                onPressed: _advancing ? null : _begin,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Color(AppConfig.primaryColorValue),
                  foregroundColor: Colors.white,
                ),
                child: _advancing
                    ? const SizedBox(
                        width: 22, height: 22,
                        child: CircularProgressIndicator(
                          strokeWidth: 2, color: Colors.white,
                        ),
                      )
                    : const Text('🧭  Begin personality round  →'),
              ),
              if (_error != null) ...[
                const SizedBox(height: 12),
                Text(_error!, style: const TextStyle(color: Colors.red)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}
