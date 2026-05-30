import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../state/providers.dart';

/// First screen the user sees on cold launch. Shows the ShramSaathi
/// logo with a brief fade-in animation, then automatically navigates
/// to the Setup screen after ~1.6 seconds — UNLESS there's a session
/// to resume from a previous run, in which case it routes back into
/// the matching screen.
///
/// Keeping this on-brand is the strongest "feels like a product" cue
/// — most polished mobile apps spend the first second on a splash.
class SplashScreen extends ConsumerStatefulWidget {
  const SplashScreen({super.key});
  @override
  ConsumerState<SplashScreen> createState() => _SplashScreenState();
}

class _SplashScreenState extends ConsumerState<SplashScreen>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final Animation<double> _fade;
  late final Animation<double> _scale;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 900),
    );
    _fade = CurvedAnimation(parent: _controller, curve: Curves.easeOut);
    _scale = Tween<double>(begin: 0.85, end: 1.0).animate(
      CurvedAnimation(parent: _controller, curve: Curves.easeOutBack),
    );
    _controller.forward();
    // Auto-navigate after the animation settles. If there's a session
    // in progress (persisted across app kills), restore + jump to the
    // appropriate screen instead of forcing the candidate to start over.
    Future.delayed(const Duration(milliseconds: 1600), () async {
      if (!mounted) return;
      final stage = await ref.read(sessionProvider.notifier).tryRestore();
      if (!mounted) return;
      switch (stage) {
        case 'profile':
        case 'interview':
        case 'behavioral':
          GoRouter.of(context).go('/loop');
          break;
        case 'profile_review':
          GoRouter.of(context).go('/resume');
          break;
        case 'behavioral_intro':
          GoRouter.of(context).go('/behavioral-intro');
          break;
        case 'awaiting_finalize':
          GoRouter.of(context).go('/finalize');
          break;
        default:
          GoRouter.of(context).go('/setup');
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Container(
        decoration: const BoxDecoration(
          gradient: LinearGradient(
            colors: [Color(0xFF6366F1), Color(0xFF06B6D4)],
            begin: Alignment.topLeft,
            end: Alignment.bottomRight,
          ),
        ),
        child: Center(
          child: FadeTransition(
            opacity: _fade,
            child: ScaleTransition(
              scale: _scale,
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    padding: const EdgeInsets.all(16),
                    decoration: BoxDecoration(
                      color: Colors.white,
                      shape: BoxShape.circle,
                      boxShadow: [
                        BoxShadow(
                          color: Colors.black.withValues(alpha: 0.20),
                          blurRadius: 24,
                          offset: const Offset(0, 8),
                        ),
                      ],
                    ),
                    child: ClipOval(
                      child: Image.asset(
                        'assets/logo.png',
                        width: 120, height: 120, fit: BoxFit.cover,
                      ),
                    ),
                  ),
                  const SizedBox(height: 28),
                  const Text(
                    'श्रमसाथी AI',
                    style: TextStyle(
                      fontSize: 36,
                      fontWeight: FontWeight.w800,
                      color: Colors.white,
                      letterSpacing: 0.5,
                    ),
                  ),
                  const SizedBox(height: 6),
                  const Text(
                    'ShramSaathi AI',
                    style: TextStyle(
                      fontSize: 18,
                      color: Colors.white70,
                      fontWeight: FontWeight.w500,
                    ),
                  ),
                  const SizedBox(height: 24),
                  const Text(
                    'हर भाषा में, हर भारतीय श्रमिक के साथ',
                    style: TextStyle(
                      fontSize: 14,
                      color: Colors.white,
                      fontWeight: FontWeight.w400,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
