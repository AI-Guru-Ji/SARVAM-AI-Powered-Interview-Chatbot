import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'package:audioplayers/audioplayers.dart';

import '../models/api_models.dart';
import '../state/providers.dart';
import '../widgets/brand_header.dart';

/// Setup screen — role + language + name + phone + recruiter email.
///
/// First step the candidate sees. Talks to `/v1/config` to populate
/// the role/language dropdowns so a backend update doesn't require
/// rebuilding the APK.
class SetupScreen extends ConsumerStatefulWidget {
  const SetupScreen({super.key});
  @override
  ConsumerState<SetupScreen> createState() => _SetupScreenState();
}

class _SetupScreenState extends ConsumerState<SetupScreen> {
  final _formKey = GlobalKey<FormState>();
  String? _role;
  String? _language;
  final _name = TextEditingController();
  final _phone = TextEditingController();
  final _recruiterEmail = TextEditingController();
  final _welcomePlayer = AudioPlayer();
  static bool _welcomePlayed = false;   // session-level, plays only once

  @override
  void initState() {
    super.initState();
    if (!_welcomePlayed) {
      _welcomePlayed = true;
      // Fire-and-forget: play the pre-baked Hindi welcome WAV. If it
      // fails (no speaker / corrupted asset), the form still works.
      WidgetsBinding.instance.addPostFrameCallback((_) async {
        try {
          await _welcomePlayer.play(AssetSource('welcome.wav'));
        } catch (_) {}
      });
    }
  }

  @override
  void dispose() {
    _name.dispose();
    _phone.dispose();
    _recruiterEmail.dispose();
    _welcomePlayer.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final cfg = ref.watch(configProvider);
    return Scaffold(
      body: cfg.when(
        loading: () => const Center(child: CircularProgressIndicator()),
        error: (e, _) => _ErrorView(
          message: 'Could not reach backend.\n$e',
          onRetry: () => ref.invalidate(configProvider),
        ),
        data: (config) => _buildForm(config),
      ),
    );
  }

  Widget _buildForm(ConfigResponse config) {
    return SingleChildScrollView(
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const BrandHeader(
            subtitle: 'Voice-first interviews for India\'s blue-collar workforce.',
          ),
          Padding(
            padding: const EdgeInsets.all(20),
            child: Form(
              key: _formKey,
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  const SizedBox(height: 8),
                  const Text(
                    'Start your interview',
                    style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700),
                  ),
                  const SizedBox(height: 6),
                  Text(
                    'Pick a role and your preferred language. You can answer '
                    'all questions by voice in your own language.',
                    style: TextStyle(color: Colors.grey[600], height: 1.4),
                  ),
                  const SizedBox(height: 24),
                  DropdownButtonFormField<String>(
                    decoration: const InputDecoration(labelText: 'Role'),
                    value: _role,
                    items: [
                      for (final r in config.roles)
                        DropdownMenuItem(value: r.key, child: Text(r.title)),
                    ],
                    onChanged: (v) => setState(() => _role = v),
                    validator: (v) => v == null ? 'Please pick a role' : null,
                  ),
                  const SizedBox(height: 16),
                  DropdownButtonFormField<String>(
                    decoration: const InputDecoration(labelText: 'Language'),
                    value: _language,
                    items: [
                      for (final l in config.languages)
                        DropdownMenuItem(value: l.code, child: Text(l.label)),
                    ],
                    onChanged: (v) => setState(() => _language = v),
                    validator: (v) =>
                        v == null ? 'Please pick a language' : null,
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _name,
                    textCapitalization: TextCapitalization.words,
                    decoration:
                        const InputDecoration(labelText: 'Your full name'),
                    validator: (v) => (v == null || v.trim().isEmpty)
                        ? 'Please enter your name'
                        : null,
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _phone,
                    keyboardType: TextInputType.phone,
                    decoration: const InputDecoration(
                      labelText: 'Mobile number',
                      hintText: '10-digit number',
                    ),
                    validator: (v) {
                      final s = (v ?? '').replaceAll(RegExp(r'\D'), '');
                      if (s.length < 10) return 'Enter a 10-digit mobile';
                      return null;
                    },
                  ),
                  const SizedBox(height: 16),
                  TextFormField(
                    controller: _recruiterEmail,
                    keyboardType: TextInputType.emailAddress,
                    decoration: const InputDecoration(
                      labelText: 'Recruiter email (optional)',
                      hintText: 'where to send the scorecard',
                    ),
                  ),
                  const SizedBox(height: 28),
                  ElevatedButton(
                    onPressed: _onContinue,
                    child: const Text('Continue  →'),
                  ),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }

  void _onContinue() {
    if (!_formKey.currentState!.validate()) return;
    // Stash the candidate's phone + language for the OTP screen
    ref.read(candidatePhoneProvider.notifier).state = _phone.text.trim();
    GoRouter.of(context).push(
      '/otp',
      extra: {
        'role':            _role!,
        'language':        _language!,
        'candidate_name':  _name.text.trim(),
        'candidate_phone': _phone.text.trim(),
        'recruiter_email': _recruiterEmail.text.trim(),
      },
    );
  }
}

class _ErrorView extends StatelessWidget {
  const _ErrorView({required this.message, required this.onRetry});
  final String message;
  final VoidCallback onRetry;
  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            const Icon(Icons.cloud_off, size: 48, color: Colors.grey),
            const SizedBox(height: 16),
            Text(message, textAlign: TextAlign.center),
            const SizedBox(height: 16),
            OutlinedButton(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}
