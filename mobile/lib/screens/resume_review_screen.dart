import 'dart:io';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:open_filex/open_filex.dart';
import 'package:path_provider/path_provider.dart';

import '../config.dart';
import '../state/providers.dart';
import '../widgets/resume_view.dart';

/// Resume Review screen — shown right after the 13-question profile
/// loop completes. The backend has already generated the ATS resume
/// PDF and the plain-text body. This screen:
///
///   • shows the text body (scrollable) so the candidate can verify
///     the bot extracted things correctly
///   • offers a "Download PDF" button that opens the file in the
///     phone's PDF viewer (via open_filex)
///   • "Continue to technical interview →" advances the FSM
///   • Top-level back button goes to /loop (continue editing profile)
class ResumeReviewScreen extends ConsumerStatefulWidget {
  const ResumeReviewScreen({super.key});
  @override
  ConsumerState<ResumeReviewScreen> createState() => _ResumeReviewScreenState();
}

class _ResumeReviewScreenState extends ConsumerState<ResumeReviewScreen> {
  String? _resumeText;
  bool _loading = true;
  bool _advancing = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _fetchResume());
  }

  Future<void> _fetchResume() async {
    final session = ref.read(sessionProvider);
    if (session == null) {
      setState(() => _loading = false);
      return;
    }
    try {
      final api = ref.read(apiClientProvider);
      final text = await api.fetchResumeText(session.sessionId);
      if (!mounted) return;
      setState(() {
        _resumeText = text;
        _loading = false;
      });
    } catch (e) {
      if (!mounted) return;
      setState(() {
        _error = '$e';
        _loading = false;
      });
    }
  }

  Future<void> _downloadAndOpenPdf() async {
    final session = ref.read(sessionProvider);
    if (session == null) return;
    final api = ref.read(apiClientProvider);
    final messenger = ScaffoldMessenger.of(context);
    try {
      messenger.showSnackBar(const SnackBar(content: Text('Preparing resume PDF…')));
      final bytes = await api.downloadResumePdf(session.sessionId);
      Directory dir;
      try {
        dir = (await getExternalStorageDirectory()) ?? await getTemporaryDirectory();
      } catch (_) {
        dir = await getTemporaryDirectory();
      }
      final candidateName =
          (session.candidateName).replaceAll(' ', '_');
      final file = File('${dir.path}/Resume_$candidateName.pdf');
      await file.writeAsBytes(Uint8List.fromList(bytes));
      final result = await OpenFilex.open(file.path, type: 'application/pdf');
      if (result.type != ResultType.done) {
        messenger.showSnackBar(SnackBar(
          content: Text('Saved to ${file.path}. Install a PDF viewer to open.'),
          duration: const Duration(seconds: 5),
        ));
      }
    } catch (e) {
      messenger.showSnackBar(SnackBar(content: Text('PDF unavailable: $e')));
    }
  }

  Future<void> _continue() async {
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
        _error = 'Could not advance: $e';
        _advancing = false;
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFFAFAFA),
      appBar: AppBar(
        title: const Text('Review your resume'),
        backgroundColor: const Color(0xFFFAFAFA),
        surfaceTintColor: Colors.transparent,
        elevation: 0,
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                Expanded(
                  child: SingleChildScrollView(
                    padding: const EdgeInsets.all(20),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.stretch,
                      children: [
                        Container(
                          padding: const EdgeInsets.all(14),
                          decoration: BoxDecoration(
                            color: const Color(0xFFEEF2FF),
                            borderRadius: BorderRadius.circular(12),
                          ),
                          child: const Row(
                            children: [
                              Icon(Icons.auto_awesome,
                                  color: Color(0xFF6366F1)),
                              SizedBox(width: 10),
                              Expanded(
                                child: Text(
                                  'Your ATS-ready resume has been generated from '
                                  'your answers. Quickly check the details before '
                                  'we begin the technical round.',
                                  style: TextStyle(height: 1.4, fontSize: 14),
                                ),
                              ),
                            ],
                          ),
                        ),
                        const SizedBox(height: 16),
                        if (_error != null) ...[
                          Text(_error!,
                              style: const TextStyle(color: Colors.red)),
                          const SizedBox(height: 16),
                        ],
                        if (_resumeText == null)
                          const Padding(
                            padding: EdgeInsets.all(20),
                            child: Text(
                              '(Resume could not be loaded — please continue.)',
                              style: TextStyle(color: Color(0xFF71717A)),
                            ),
                          )
                        else
                          ResumeView(text: _resumeText!),
                        const SizedBox(height: 16),
                        OutlinedButton.icon(
                          onPressed: _downloadAndOpenPdf,
                          icon: const Icon(Icons.picture_as_pdf),
                          label: const Text('Download PDF'),
                        ),
                      ],
                    ),
                  ),
                ),
                SafeArea(
                  child: Padding(
                    padding: const EdgeInsets.all(20),
                    child: ElevatedButton(
                      onPressed: _advancing ? null : _continue,
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
                          : const Text('Continue to technical interview  →'),
                    ),
                  ),
                ),
              ],
            ),
    );
  }
}
