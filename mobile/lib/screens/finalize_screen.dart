import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../config.dart';
import '../state/providers.dart';

/// Final screen before the wait: shows a confirmation + "Generate
/// Final Report" button. The /finalize call can take 30-60s while
/// both LLM evaluations run, so we show a meaningful spinner.
class FinalizeScreen extends ConsumerStatefulWidget {
  const FinalizeScreen({super.key});
  @override
  ConsumerState<FinalizeScreen> createState() => _FinalizeScreenState();
}

class _FinalizeScreenState extends ConsumerState<FinalizeScreen> {
  bool _running = false;
  String? _error;

  Future<void> _finalize() async {
    setState(() {
      _running = true;
      _error = null;
    });
    try {
      await ref.read(sessionProvider.notifier).finalize();
      if (!mounted) return;
      GoRouter.of(context).go('/submitted');
    } catch (e) {
      setState(() => _error = 'Could not finalize: $e');
    } finally {
      setState(() => _running = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Almost done')),
      body: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: 16),
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: const Color(0xFFEEF2FF),
                borderRadius: BorderRadius.circular(12),
              ),
              child: const Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    'Both rounds complete ✓',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w700),
                  ),
                  SizedBox(height: 8),
                  Text(
                    'Tap below to generate your final report. We will '
                    'combine your technical answers and your personality '
                    'answers into one scorecard. This usually takes 30 to '
                    '60 seconds.',
                    style: TextStyle(height: 1.5),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 32),
            if (_running) ...[
              const Center(
                child: SizedBox(
                  width: 64,
                  height: 64,
                  child: CircularProgressIndicator(strokeWidth: 4),
                ),
              ),
              const SizedBox(height: 16),
              const Center(
                child: Text(
                  'Scoring your answers — please don’t close the app.',
                  textAlign: TextAlign.center,
                ),
              ),
            ] else
              ElevatedButton(
                onPressed: _finalize,
                style: ElevatedButton.styleFrom(
                  backgroundColor: Color(AppConfig.primaryColorValue),
                  foregroundColor: Colors.white,
                ),
                child: const Text('📊  Generate Final Report  →'),
              ),
            if (_error != null) ...[
              const SizedBox(height: 12),
              Text(_error!, style: const TextStyle(color: Colors.red)),
            ],
          ],
        ),
      ),
    );
  }
}
