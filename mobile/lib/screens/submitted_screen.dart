import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';
import 'package:share_plus/share_plus.dart';

import '../config.dart';
import '../state/providers.dart';
import '../widgets/confetti.dart';

/// Terminal screen for the candidate flow.
///
/// The recruiter sees the full scorecard on the web dashboard / via
/// email. The candidate sees a confirmation + key headline numbers
/// (overall score + hire chip) so they don't feel like they shouted
/// into a black box. Optional "View scorecard PDF" button opens the
/// dashboard PDF the backend just generated.
class SubmittedScreen extends ConsumerStatefulWidget {
  const SubmittedScreen({super.key});
  @override
  ConsumerState<SubmittedScreen> createState() => _SubmittedScreenState();
}

class _SubmittedScreenState extends ConsumerState<SubmittedScreen> {
  Map<String, dynamic>? _report;
  bool _loading = true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _fetchReport());
  }

  Future<void> _fetchReport() async {
    final session = ref.read(sessionProvider);
    if (session == null) {
      setState(() => _loading = false);
      return;
    }
    try {
      // Re-use the same dio client; the report endpoint returns plain
      // JSON. We render the headline numbers on-screen.
      final api = ref.read(apiClientProvider);
      final response = await api.fetchReport(session.sessionId);
      setState(() {
        _report = response;
        _loading = false;
      });
    } catch (_) {
      setState(() => _loading = false);
    }
  }

  Future<void> _shareReportLink() async {
    final session = ref.read(sessionProvider);
    if (session == null) return;
    final reportUrl = '${AppConfig.backendUrl}'
        '/v1/sessions/${session.sessionId}/report.pdf';
    final message =
        'Hi! Here is my ShramSaathi AI interview scorecard:\n\n$reportUrl\n\n'
        '— ${session.candidateName}';
    await Share.share(
      message,
      subject: 'ShramSaathi interview · ${session.candidateName}',
    );
  }

  Future<void> _downloadAndOpenPdf() async {
    final session = ref.read(sessionProvider);
    if (session == null) return;
    final api = ref.read(apiClientProvider);
    final messenger = ScaffoldMessenger.of(context);
    try {
      messenger.showSnackBar(
        const SnackBar(content: Text('Downloading scorecard PDF…')),
      );
      final bytes = await api.downloadReportPdf(session.sessionId);
      // Use the app's external-files directory so other apps (the PDF
      // viewer) can read it via FileProvider. Falls back to temp dir
      // if the device blocks external storage access.
      Directory dir;
      try {
        dir = (await getExternalStorageDirectory()) ?? await getTemporaryDirectory();
      } catch (_) {
        dir = await getTemporaryDirectory();
      }
      final filename =
          'ShramSaathi_Scorecard_${session.candidateName.replaceAll(" ", "_")}.pdf';
      final file = File('${dir.path}/$filename');
      await file.writeAsBytes(Uint8List.fromList(bytes));

      // Open with the device's default PDF viewer (Drive / Acrobat / etc.)
      final result = await OpenFilex.open(file.path, type: 'application/pdf');
      if (result.type != ResultType.done) {
        messenger.showSnackBar(
          SnackBar(
            content: Text(
              'Saved to ${file.path}. Install a PDF viewer to open it.',
            ),
            duration: const Duration(seconds: 5),
          ),
        );
      }
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('PDF unavailable: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final session = ref.watch(sessionProvider);
    final ev = (_report?['evaluation'] ?? {}) as Map<String, dynamic>;
    final be = (_report?['behavioral_eval'] ?? {}) as Map<String, dynamic>;

    final overallScore = ev['overall_score'];
    final hireRec     = ev['hire_recommendation'];
    final summary     = (ev['summary'] ?? '') as String;
    final behavSummary = (be['overall_summary'] ?? '') as String;

    return Scaffold(
      body: Stack(
        children: [
          SafeArea(
            child: SingleChildScrollView(
              padding: const EdgeInsets.all(24),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 24),
                  const Icon(Icons.check_circle,
                      color: Color(0xFF10B981), size: 88),
                  const SizedBox(height: 20),
                  Text(
                    session?.candidateName != null
                        ? 'Thank you, ${session!.candidateName}!'
                        : 'Thank you!',
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                        fontSize: 26, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Your interview has been submitted.',
                    textAlign: TextAlign.center,
                    style: TextStyle(
                        fontSize: 15, color: Color(0xFF52525B)),
                  ),
                  const SizedBox(height: 28),
                  if (_loading)
                    const Padding(
                      padding: EdgeInsets.symmetric(vertical: 20),
                      child: Center(child: CircularProgressIndicator()),
                    )
                  else if (_report != null) ...[
                    _ScoreCard(
                      overallScore:
                          overallScore is num ? overallScore.toDouble() : null,
                      hireRecommendation: hireRec is bool ? hireRec : null,
                      summary: summary,
                      behavioralSummary: behavSummary,
                    ),
                    const SizedBox(height: 20),
                    ElevatedButton.icon(
                      onPressed: _downloadAndOpenPdf,
                      icon: const Icon(Icons.picture_as_pdf),
                      label: const Text('Download full scorecard PDF'),
                      style: ElevatedButton.styleFrom(
                        backgroundColor: Color(AppConfig.primaryColorValue),
                        foregroundColor: Colors.white,
                      ),
                    ),
                    const SizedBox(height: 10),
                    OutlinedButton.icon(
                      onPressed: _shareReportLink,
                      icon: const Icon(Icons.share_outlined),
                      label: const Text('Share results with recruiter'),
                    ),
                  ],
                  const SizedBox(height: 24),
                  const _InfoRow(
                    icon: Icons.email_outlined,
                    text:
                        'Recruiter will receive an email with the full report.',
                  ),
                  const SizedBox(height: 8),
                  const _InfoRow(
                    icon: Icons.description_outlined,
                    text: 'ATS resume generated automatically.',
                  ),
                  const SizedBox(height: 8),
                  const _InfoRow(
                    icon: Icons.psychology_outlined,
                    text:
                        'Personality trust profile included in the scorecard.',
                  ),
                  const SizedBox(height: 32),
                  OutlinedButton(
                    onPressed: () {
                      ref.read(sessionProvider.notifier).abort();
                      GoRouter.of(context).go('/');
                    },
                    child: const Text('Start another interview'),
                  ),
                  const SizedBox(height: 16),
                ],
              ),
            ),
          ),
          // Confetti drifts down over the whole screen on first paint
          const Positioned.fill(child: Confetti()),
        ],
      ),
    );
  }
}

// ──────────────────────────────────────────────────────────────────────
// Sub-widgets
// ──────────────────────────────────────────────────────────────────────
class _ScoreCard extends StatelessWidget {
  const _ScoreCard({
    required this.overallScore,
    required this.hireRecommendation,
    required this.summary,
    required this.behavioralSummary,
  });
  final double? overallScore;
  final bool? hireRecommendation;
  final String summary;
  final String behavioralSummary;

  @override
  Widget build(BuildContext context) {
    final score = overallScore != null
        ? overallScore!.toStringAsFixed(overallScore! == overallScore!.roundToDouble() ? 0 : 1)
        : '—';
    return Container(
      padding: const EdgeInsets.all(20),
      decoration: BoxDecoration(
        color: const Color(0xFFEEF2FF),
        borderRadius: BorderRadius.circular(16),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              const Text(
                'Your scorecard',
                style: TextStyle(fontSize: 14, fontWeight: FontWeight.w700,
                                 color: Color(0xFF71717A)),
              ),
              _HireChip(recommendation: hireRecommendation),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                score,
                style: const TextStyle(
                  fontSize: 56, fontWeight: FontWeight.w800,
                  color: Color(0xFF10B981), height: 1.0,
                ),
              ),
              const SizedBox(width: 8),
              const Text('/ 10',
                  style: TextStyle(fontSize: 18, color: Color(0xFF71717A))),
            ],
          ),
          if (summary.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              summary,
              style: const TextStyle(height: 1.5, fontSize: 14),
            ),
          ],
          if (behavioralSummary.isNotEmpty) ...[
            const SizedBox(height: 12),
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.circular(10),
                border: Border.all(color: const Color(0xFFE4E4E7)),
              ),
              child: Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  const Text('🧭  ', style: TextStyle(fontSize: 18)),
                  Expanded(
                    child: Text(
                      behavioralSummary,
                      style: const TextStyle(fontSize: 13, height: 1.45),
                    ),
                  ),
                ],
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _HireChip extends StatelessWidget {
  const _HireChip({required this.recommendation});
  final bool? recommendation;

  @override
  Widget build(BuildContext context) {
    if (recommendation == true) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: const Color(0xFFD1FAE5),
          borderRadius: BorderRadius.circular(20),
        ),
        child: const Text('✓ Recommended',
            style: TextStyle(color: Color(0xFF047857),
                             fontWeight: FontWeight.w700, fontSize: 12)),
      );
    }
    if (recommendation == false) {
      return Container(
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: const Color(0xFFFEE2E2),
          borderRadius: BorderRadius.circular(20),
        ),
        child: const Text('✕ Not recommended',
            style: TextStyle(color: Color(0xFFB91C1C),
                             fontWeight: FontWeight.w700, fontSize: 12)),
      );
    }
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      decoration: BoxDecoration(
        color: const Color(0xFFF4F4F5),
        borderRadius: BorderRadius.circular(20),
      ),
      child: const Text('○ Pending review',
          style: TextStyle(color: Color(0xFF71717A),
                           fontWeight: FontWeight.w700, fontSize: 12)),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.icon, required this.text});
  final IconData icon;
  final String text;
  @override
  Widget build(BuildContext context) {
    return Row(
      children: [
        Icon(icon, size: 20, color: const Color(0xFF6366F1)),
        const SizedBox(width: 10),
        Expanded(
          child: Text(text,
              style: const TextStyle(fontSize: 14, color: Color(0xFF52525B))),
        ),
      ],
    );
  }
}
