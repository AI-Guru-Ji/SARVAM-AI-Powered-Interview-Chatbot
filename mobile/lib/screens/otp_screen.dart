import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../state/providers.dart';

/// OTP screen — verifies the candidate's phone number.
///
/// In demo mode the backend returns the OTP in the request response,
/// so this screen displays it as a hint. In production that hint is
/// hidden and the user reads it from their SMS.
class OtpScreen extends ConsumerStatefulWidget {
  const OtpScreen({super.key, required this.setupArgs});
  final Map<String, String> setupArgs;
  @override
  ConsumerState<OtpScreen> createState() => _OtpScreenState();
}

class _OtpScreenState extends ConsumerState<OtpScreen> {
  final _otpCtrl = TextEditingController();
  String? _demoOtpHint;
  bool _requesting = false;
  bool _verifying = false;
  String? _error;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _requestOtp());
  }

  Future<void> _requestOtp() async {
    setState(() {
      _requesting = true;
      _error = null;
    });
    try {
      final api = ref.read(apiClientProvider);
      final result = await api.requestOtp(
        phone: widget.setupArgs['candidate_phone']!,
        language: widget.setupArgs['language']!,
      );
      setState(() {
        _demoOtpHint = result.demoOtp;   // populated only in demo mode
      });
    } catch (e) {
      setState(() => _error = 'Failed to send OTP: $e');
    } finally {
      setState(() => _requesting = false);
    }
  }

  Future<void> _verify() async {
    if (_otpCtrl.text.trim().length < 4) return;
    setState(() {
      _verifying = true;
      _error = null;
    });
    try {
      final api = ref.read(apiClientProvider);
      final result = await api.verifyOtp(
        phone: widget.setupArgs['candidate_phone']!,
        otp: _otpCtrl.text.trim(),
      );
      ref.read(authTokenProvider.notifier).state = result.token;

      // Create the actual session, then jump straight into the voice loop.
      await ref.read(sessionProvider.notifier).startNewSession(
            role: widget.setupArgs['role']!,
            language: widget.setupArgs['language']!,
            candidateName: widget.setupArgs['candidate_name']!,
            candidatePhone: widget.setupArgs['candidate_phone']!,
            recruiterEmail: widget.setupArgs['recruiter_email']!,
          );
      if (!mounted) return;
      GoRouter.of(context).go('/loop');
    } catch (e) {
      setState(() => _error = 'Invalid OTP. Please try again.');
    } finally {
      setState(() => _verifying = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Verify your phone')),
      body: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const SizedBox(height: 16),
            Text(
              'We sent a code to +91 ${widget.setupArgs['candidate_phone']}',
              style: const TextStyle(fontSize: 16),
            ),
            if (_demoOtpHint != null) ...[
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: const Color(0xFFFFFBEB),
                  borderRadius: BorderRadius.circular(8),
                  border: Border.all(color: const Color(0xFFFCD34D)),
                ),
                child: Text(
                  '🛈  Demo mode — OTP is $_demoOtpHint',
                  style: const TextStyle(color: Color(0xFF92400E)),
                ),
              ),
            ],
            const SizedBox(height: 24),
            TextField(
              controller: _otpCtrl,
              keyboardType: TextInputType.number,
              maxLength: 6,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 24, letterSpacing: 8),
              decoration: const InputDecoration(
                hintText: '••••••',
              ),
              onSubmitted: (_) => _verify(),
            ),
            if (_error != null) ...[
              const SizedBox(height: 8),
              Text(_error!, style: const TextStyle(color: Colors.red)),
            ],
            const SizedBox(height: 24),
            ElevatedButton(
              onPressed: _verifying ? null : _verify,
              child: _verifying
                  ? const SizedBox(
                      width: 22, height: 22,
                      child: CircularProgressIndicator(
                        strokeWidth: 2, color: Colors.white,
                      ),
                    )
                  : const Text('Verify & start interview'),
            ),
            TextButton(
              onPressed: _requesting ? null : _requestOtp,
              child: Text(_requesting ? 'Sending…' : 'Resend OTP'),
            ),
          ],
        ),
      ),
    );
  }
}
