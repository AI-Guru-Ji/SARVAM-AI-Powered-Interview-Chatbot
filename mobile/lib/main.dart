import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import 'screens/behavioral_intro_screen.dart';
import 'screens/finalize_screen.dart';
import 'screens/otp_screen.dart';
import 'screens/resume_review_screen.dart';
import 'screens/setup_screen.dart';
import 'screens/splash_screen.dart';
import 'screens/submitted_screen.dart';
import 'screens/voice_loop_screen.dart';
import 'theme.dart';

void main() {
  // Crash reporting (Sentry) is intentionally deferred — its current
  // Kotlin version is incompatible with our Flutter SDK. Add it back
  // post-demo with a compatible plugin version. The AppConfig.sentryDsn
  // build-time constant is retained so the call-site is one line away.
  runApp(const ProviderScope(child: ShramSaathiApp()));
}

class ShramSaathiApp extends StatelessWidget {
  const ShramSaathiApp({super.key});

  @override
  Widget build(BuildContext context) {
    final router = GoRouter(
      initialLocation: '/',
      routes: [
        GoRoute(
          path: '/',
          builder: (ctx, _) => const SplashScreen(),
        ),
        GoRoute(
          path: '/setup',
          builder: (ctx, _) => const SetupScreen(),
        ),
        GoRoute(
          path: '/otp',
          builder: (ctx, state) {
            final args = (state.extra ?? <String, String>{}) as Map<String, dynamic>;
            return OtpScreen(
              setupArgs: args.map((k, v) => MapEntry(k, v.toString())),
            );
          },
        ),
        GoRoute(
          path: '/loop',
          builder: (ctx, _) => const VoiceLoopScreen(),
        ),
        GoRoute(
          path: '/resume',
          builder: (ctx, _) => const ResumeReviewScreen(),
        ),
        GoRoute(
          path: '/behavioral-intro',
          builder: (ctx, _) => const BehavioralIntroScreen(),
        ),
        GoRoute(
          path: '/finalize',
          builder: (ctx, _) => const FinalizeScreen(),
        ),
        GoRoute(
          path: '/submitted',
          builder: (ctx, _) => const SubmittedScreen(),
        ),
      ],
    );

    return MaterialApp.router(
      title: 'ShramSaathi AI',
      theme: buildAppTheme(),
      routerConfig: router,
      debugShowCheckedModeBanner: false,
    );
  }
}
