import 'package:flutter/material.dart';

/// Colourful, mobile-friendly render of the ATS-style resume text the
/// backend produces.
///
/// The backend emits a deterministic shape:
///
///   <Name>
///   Phone: <number>
///
///   PROFESSIONAL SUMMARY
///   …
///
///   WORK EXPERIENCE
///   …
///
///   EDUCATION & CERTIFICATIONS
///   …
///
///   CORE SKILLS & TOOLS
///   - bullet
///   - bullet
///
///   LANGUAGES KNOWN
///   Hindi, English
///
/// We split on blank lines, classify each block as either a section
/// (its first line is an ALL-CAPS header) or as a contact line
/// (``Phone: ...``), then render each with a coloured icon + card.
class ResumeView extends StatelessWidget {
  const ResumeView({super.key, required this.text});
  final String text;

  // Map of section-header keyword → icon + accent colour. First match
  // wins. Order matters — more specific keys come first.
  static const List<(String, IconData, Color)> _sectionStyles = [
    ('SUMMARY',     Icons.auto_awesome_outlined,    Color(0xFF6366F1)),
    ('OBJECTIVE',   Icons.flag_outlined,            Color(0xFF6366F1)),
    ('WORK',        Icons.work_outline,             Color(0xFF06B6D4)),
    ('EXPERIENCE',  Icons.work_outline,             Color(0xFF06B6D4)),
    ('EDUCATION',   Icons.school_outlined,          Color(0xFF10B981)),
    ('CERTIFICATI', Icons.verified_outlined,        Color(0xFF10B981)),
    ('SKILL',       Icons.star_outline,             Color(0xFFF59E0B)),
    ('TOOL',        Icons.build_outlined,           Color(0xFFF59E0B)),
    ('LANGUAGE',    Icons.translate,                Color(0xFFEC4899)),
    ('PROJECT',     Icons.folder_outlined,          Color(0xFF8B5CF6)),
    ('REFERENCE',   Icons.contacts_outlined,        Color(0xFF71717A)),
  ];

  static (IconData, Color) _styleFor(String heading) {
    final up = heading.toUpperCase();
    for (final s in _sectionStyles) {
      if (up.contains(s.$1)) return (s.$2, s.$3);
    }
    return (Icons.notes_outlined, const Color(0xFF52525B));
  }

  /// Split into hero (name + contact) + sections.
  _Parsed _parse() {
    final blocks = text
        .split(RegExp(r'\n\s*\n'))
        .map((b) => b.trim())
        .where((b) => b.isNotEmpty)
        .toList();
    if (blocks.isEmpty) {
      return _Parsed(name: '', contactLines: const [], sections: const []);
    }
    // First block: name + contact lines (Phone: …, optionally Email: …)
    final firstLines = blocks.first.split('\n');
    final name = firstLines.isNotEmpty ? firstLines.first.trim() : '';
    final contactLines = firstLines.skip(1).map((l) => l.trim()).where((l) => l.isNotEmpty).toList();

    // Remaining blocks: each starts with a heading (typically ALL CAPS)
    final sections = <_Section>[];
    for (final block in blocks.skip(1)) {
      final lines = block.split('\n');
      if (lines.isEmpty) continue;
      final heading = lines.first.trim();
      final body = lines.skip(1).map((l) => l.trim()).where((l) => l.isNotEmpty).toList();
      sections.add(_Section(heading: heading, bodyLines: body));
    }
    return _Parsed(name: name, contactLines: contactLines, sections: sections);
  }

  @override
  Widget build(BuildContext context) {
    final parsed = _parse();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        _HeroCard(name: parsed.name, contactLines: parsed.contactLines),
        const SizedBox(height: 14),
        for (final section in parsed.sections) ...[
          _SectionCard(section: section),
          const SizedBox(height: 12),
        ],
      ],
    );
  }
}

// ──────────────────────────────────────────────────────────────────────
// Internal
// ──────────────────────────────────────────────────────────────────────
class _Parsed {
  _Parsed({
    required this.name,
    required this.contactLines,
    required this.sections,
  });
  final String name;
  final List<String> contactLines;
  final List<_Section> sections;
}

class _Section {
  _Section({required this.heading, required this.bodyLines});
  final String heading;
  final List<String> bodyLines;
}

class _HeroCard extends StatelessWidget {
  const _HeroCard({required this.name, required this.contactLines});
  final String name;
  final List<String> contactLines;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.fromLTRB(18, 20, 18, 18),
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(16),
        gradient: const LinearGradient(
          colors: [Color(0xFF6366F1), Color(0xFF06B6D4)],
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
        ),
        boxShadow: [
          BoxShadow(
            color: const Color(0xFF6366F1).withValues(alpha: 0.25),
            blurRadius: 14,
            offset: const Offset(0, 6),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: Colors.white.withValues(alpha: 0.18),
              borderRadius: BorderRadius.circular(20),
            ),
            child: const Text(
              '✨  AI-generated ATS resume',
              style: TextStyle(
                color: Colors.white, fontSize: 11, fontWeight: FontWeight.w600,
                letterSpacing: 0.3,
              ),
            ),
          ),
          const SizedBox(height: 12),
          Text(
            name.isEmpty ? 'Candidate' : name,
            style: const TextStyle(
              color: Colors.white,
              fontSize: 26,
              fontWeight: FontWeight.w800,
              height: 1.15,
            ),
          ),
          if (contactLines.isNotEmpty) ...[
            const SizedBox(height: 10),
            for (final line in contactLines) ...[
              Row(
                children: [
                  const Icon(Icons.phone_iphone, color: Colors.white70, size: 16),
                  const SizedBox(width: 6),
                  Flexible(
                    child: Text(
                      line,
                      style: const TextStyle(color: Colors.white, fontSize: 14),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 2),
            ],
          ],
        ],
      ),
    );
  }
}

class _SectionCard extends StatelessWidget {
  const _SectionCard({required this.section});
  final _Section section;

  @override
  Widget build(BuildContext context) {
    final (icon, accent) = ResumeView._styleFor(section.heading);
    final isSkillSection =
        section.heading.toUpperCase().contains('SKILL') ||
        section.heading.toUpperCase().contains('TOOL') ||
        section.heading.toUpperCase().contains('LANGUAGE');

    return Container(
      decoration: BoxDecoration(
        color: Colors.white,
        borderRadius: BorderRadius.circular(14),
        border: Border(left: BorderSide(color: accent, width: 4)),
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.04),
            blurRadius: 8,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      padding: const EdgeInsets.fromLTRB(14, 14, 14, 14),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Container(
                padding: const EdgeInsets.all(7),
                decoration: BoxDecoration(
                  color: accent.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(icon, color: accent, size: 18),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Text(
                  _titleCase(section.heading),
                  style: TextStyle(
                    color: accent,
                    fontWeight: FontWeight.w700,
                    fontSize: 13,
                    letterSpacing: 0.4,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 10),
          if (isSkillSection)
            _ChipList(items: _splitSkillItems(section.bodyLines), accent: accent)
          else
            ..._renderProseBody(section.bodyLines),
        ],
      ),
    );
  }

  /// Convert ALL CAPS / Title Case to a nicely cased title.
  static String _titleCase(String s) {
    final clean = s.trim();
    if (clean.length <= 3) return clean;
    return clean
        .toLowerCase()
        .split(RegExp(r'\s+'))
        .map((w) => w.isEmpty ? w : '${w[0].toUpperCase()}${w.substring(1)}')
        .join(' ');
  }

  /// Skills sometimes come as bullet lines ("- Cleaning") and sometimes
  /// as comma-separated strings ("Hindi, English"). Handle both.
  static List<String> _splitSkillItems(List<String> lines) {
    final out = <String>[];
    for (final l in lines) {
      final cleaned = l.replaceFirst(RegExp(r'^[\-•▪◦*]\s*'), '').trim();
      if (cleaned.isEmpty) continue;
      if (cleaned.contains(',') && !cleaned.startsWith('-')) {
        out.addAll(cleaned.split(',').map((p) => p.trim()).where((p) => p.isNotEmpty));
      } else {
        out.add(cleaned);
      }
    }
    return out;
  }

  /// Render multi-line prose with bullet/title cues from the backend.
  List<Widget> _renderProseBody(List<String> lines) {
    final widgets = <Widget>[];
    for (var i = 0; i < lines.length; i++) {
      final line = lines[i];
      final isBullet = line.startsWith('- ') || line.startsWith('• ');
      // Treat "Company | duration" lines as bolder mini-headers
      final isMiniHeader = line.contains(' | ') && !isBullet;
      widgets.add(Padding(
        padding: EdgeInsets.only(top: i == 0 ? 0 : 4),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (isBullet)
              const Padding(
                padding: EdgeInsets.only(top: 6, right: 8),
                child: Icon(Icons.circle, size: 6, color: Color(0xFF71717A)),
              ),
            Expanded(
              child: Text(
                isBullet ? line.replaceFirst(RegExp(r'^[\-•]\s*'), '') : line,
                style: TextStyle(
                  fontSize: 13.5,
                  height: 1.5,
                  color: const Color(0xFF27272A),
                  fontWeight: isMiniHeader ? FontWeight.w700 : FontWeight.w400,
                ),
              ),
            ),
          ],
        ),
      ));
    }
    return widgets;
  }
}

class _ChipList extends StatelessWidget {
  const _ChipList({required this.items, required this.accent});
  final List<String> items;
  final Color accent;
  @override
  Widget build(BuildContext context) {
    return Wrap(
      spacing: 6, runSpacing: 6,
      children: [
        for (final item in items)
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
            decoration: BoxDecoration(
              color: accent.withValues(alpha: 0.10),
              borderRadius: BorderRadius.circular(20),
              border: Border.all(color: accent.withValues(alpha: 0.30)),
            ),
            child: Text(
              item,
              style: TextStyle(
                fontSize: 12,
                color: accent,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
      ],
    );
  }
}
