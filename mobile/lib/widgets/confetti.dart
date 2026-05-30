import 'dart:math' as math;

import 'package:flutter/material.dart';

/// Lightweight confetti animation — no third-party package.
///
/// Drops ~40 coloured "petals" from above the widget, settling under
/// gravity over ~2.4 seconds. Plays once on first build (e.g. when
/// the Submitted screen appears). Cheap enough to leave running even
/// after the visible animation ends — paint becomes a no-op.
class Confetti extends StatefulWidget {
  const Confetti({super.key, this.duration = const Duration(seconds: 3)});
  final Duration duration;
  @override
  State<Confetti> createState() => _ConfettiState();
}

class _ConfettiState extends State<Confetti>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;
  late final List<_Particle> _particles;

  static const _colors = [
    Color(0xFF6366F1),
    Color(0xFF06B6D4),
    Color(0xFF10B981),
    Color(0xFFF59E0B),
    Color(0xFFEF4444),
  ];

  @override
  void initState() {
    super.initState();
    final rand = math.Random();
    _particles = List.generate(40, (i) {
      return _Particle(
        x: rand.nextDouble(),
        delay: rand.nextDouble() * 0.3,
        rotation: rand.nextDouble() * math.pi * 2,
        rotationSpeed: (rand.nextDouble() - 0.5) * 6,
        size: 6 + rand.nextDouble() * 8,
        color: _colors[rand.nextInt(_colors.length)],
        drift: (rand.nextDouble() - 0.5) * 0.3,
      );
    });
    _controller = AnimationController(vsync: this, duration: widget.duration)
      ..forward();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return IgnorePointer(
      child: AnimatedBuilder(
        animation: _controller,
        builder: (_, __) {
          return CustomPaint(
            painter: _ConfettiPainter(_particles, _controller.value),
            size: Size.infinite,
          );
        },
      ),
    );
  }
}

class _Particle {
  _Particle({
    required this.x,
    required this.delay,
    required this.rotation,
    required this.rotationSpeed,
    required this.size,
    required this.color,
    required this.drift,
  });
  final double x;          // 0..1 horizontal start
  final double delay;      // 0..0.3 of total time before this one appears
  final double rotation;
  final double rotationSpeed;
  final double size;
  final Color color;
  final double drift;      // horizontal drift over the fall
}

class _ConfettiPainter extends CustomPainter {
  _ConfettiPainter(this.particles, this.t);
  final List<_Particle> particles;
  final double t;

  @override
  void paint(Canvas canvas, Size size) {
    for (final p in particles) {
      final localT = ((t - p.delay) / (1 - p.delay)).clamp(0.0, 1.0);
      if (localT <= 0) continue;
      final x = (p.x + p.drift * localT) * size.width;
      // gravity-like fall
      final y = -p.size + (size.height + p.size * 2) * (localT * localT);
      final paint = Paint()..color = p.color.withValues(alpha: 1 - localT * 0.4);
      canvas.save();
      canvas.translate(x, y);
      canvas.rotate(p.rotation + p.rotationSpeed * localT);
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromCenter(center: Offset.zero, width: p.size, height: p.size * 0.5),
          const Radius.circular(2),
        ),
        paint,
      );
      canvas.restore();
    }
  }

  @override
  bool shouldRepaint(_ConfettiPainter old) => old.t != t;
}
