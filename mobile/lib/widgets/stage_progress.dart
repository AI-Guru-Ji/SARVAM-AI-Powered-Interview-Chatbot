import 'package:flutter/material.dart';

import '../config.dart';

/// Top-of-screen stepper that shows the candidate where they are in
/// the interview journey: Profile → Technical → Personality → Done.
///
/// Mirrors the web-app's progress bar and gives the customer demo a
/// clear "we're in stage X of N" cue throughout the flow.
class StageProgress extends StatelessWidget {
  const StageProgress({
    super.key,
    required this.currentStage,
    required this.progress,
  });

  /// Backend stage name — one of: profile, interview, behavioral,
  /// awaiting_finalize, evaluating, completed.
  final String currentStage;

  /// Overall 0..1 — driven by backend's progress field.
  final double progress;

  static const _stages = [
    ('profile',    'Profile',    Icons.person_outline),
    ('interview',  'Technical',  Icons.work_outline),
    ('behavioral', 'Personality', Icons.psychology_outlined),
    ('completed',  'Done',       Icons.check_circle_outline),
  ];

  int get _currentIdx {
    final stage = currentStage;
    for (int i = 0; i < _stages.length; i++) {
      if (_stages[i].$1 == stage) return i;
    }
    // FSM-transient stages live "after" the visible one
    if (stage == 'awaiting_finalize' || stage == 'evaluating') return 3;
    return 0;
  }

  @override
  Widget build(BuildContext context) {
    final primary = Color(AppConfig.primaryColorValue);
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      decoration: BoxDecoration(
        color: Colors.white,
        border: Border(
          bottom: BorderSide(color: Colors.grey.shade200, width: 1),
        ),
      ),
      child: Column(
        children: [
          Row(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              for (int i = 0; i < _stages.length; i++)
                _StageDot(
                  label: _stages[i].$2,
                  icon: _stages[i].$3,
                  state: i < _currentIdx
                      ? _DotState.done
                      : i == _currentIdx
                          ? _DotState.active
                          : _DotState.upcoming,
                  primary: primary,
                ),
            ],
          ),
          const SizedBox(height: 8),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: LinearProgressIndicator(
              value: progress,
              minHeight: 4,
              backgroundColor: Colors.grey.shade200,
              valueColor: AlwaysStoppedAnimation<Color>(primary),
            ),
          ),
        ],
      ),
    );
  }
}

enum _DotState { upcoming, active, done }

class _StageDot extends StatelessWidget {
  const _StageDot({
    required this.label,
    required this.icon,
    required this.state,
    required this.primary,
  });
  final String label;
  final IconData icon;
  final _DotState state;
  final Color primary;

  @override
  Widget build(BuildContext context) {
    late Color bg;
    late Color iconColour;
    late Color textColour;
    switch (state) {
      case _DotState.done:
        bg = primary;
        iconColour = Colors.white;
        textColour = primary;
        break;
      case _DotState.active:
        bg = primary;
        iconColour = Colors.white;
        textColour = primary;
        break;
      case _DotState.upcoming:
        bg = Colors.grey.shade200;
        iconColour = Colors.grey.shade500;
        textColour = Colors.grey.shade500;
        break;
    }
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        AnimatedContainer(
          duration: const Duration(milliseconds: 250),
          width: 28, height: 28,
          decoration: BoxDecoration(color: bg, shape: BoxShape.circle),
          child: Icon(
            state == _DotState.done ? Icons.check : icon,
            size: 16, color: iconColour,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          label,
          style: TextStyle(
            fontSize: 11,
            color: textColour,
            fontWeight: state == _DotState.active
                ? FontWeight.w700
                : FontWeight.w500,
          ),
        ),
      ],
    );
  }
}
