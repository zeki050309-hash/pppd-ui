
import 'package:flutter/material.dart';
import 'package:google_fonts/google_fonts.dart';

class PppdColors {
  static const Color purple = Color(0xFF6C4DFF);
  static const Color deepPurple = Color(0xFF2F245F);
  static const Color lavender = Color(0xFFF4F0FF);
  static const Color softPurple = Color(0xFFE9E2FF);
  static const Color card = Colors.white;
  static const Color text = Color(0xFF211B3A);
  static const Color muted = Color(0xFF7B7394);
  static const Color danger = Color(0xFFFF5B7F);
  static const Color warning = Color(0xFFFFB84D);
  static const Color safe = Color(0xFF3CCB8E);
}

TextStyle pppdText({
  double size = 16,
  FontWeight weight = FontWeight.w500,
  Color color = PppdColors.text,
  double height = 1.25,
}) {
  return GoogleFonts.inter(
    fontSize: size,
    fontWeight: weight,
    color: color,
    height: height,
  );
}

BoxDecoration pppdCardDecoration({Color color = PppdColors.card}) {
  return BoxDecoration(
    color: color,
    borderRadius: BorderRadius.circular(24),
    boxShadow: const [
      BoxShadow(
        color: Color(0x18000000),
        blurRadius: 24,
        offset: Offset(0, 12),
      ),
    ],
  );
}

class PppdScaffold extends StatelessWidget {
  const PppdScaffold({
    super.key,
    required this.title,
    this.subtitle,
    required this.child,
    this.showBack = true,
    this.trailing,
  });

  final String title;
  final String? subtitle;
  final Widget child;
  final bool showBack;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: PppdColors.lavender,
      body: SafeArea(
        child: Container(
          decoration: const BoxDecoration(
            gradient: LinearGradient(
              begin: Alignment.topLeft,
              end: Alignment.bottomRight,
              colors: [Color(0xFFFCFAFF), Color(0xFFF1ECFF)],
            ),
          ),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(20, 18, 20, 12),
                child: Row(
                  children: [
                    if (showBack)
                      _CircleIconButton(
                        icon: Icons.arrow_back_ios_new_rounded,
                        onTap: () => Navigator.of(context).maybePop(),
                      ),
                    if (showBack) const SizedBox(width: 12),
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(title, style: pppdText(size: 25, weight: FontWeight.w800)),
                          if (subtitle != null) ...[
                            const SizedBox(height: 4),
                            Text(subtitle!, style: pppdText(size: 13, color: PppdColors.muted, height: 1.3)),
                          ],
                        ],
                      ),
                    ),
                    if (trailing != null) trailing!,
                  ],
                ),
              ),
              Expanded(child: child),
            ],
          ),
        ),
      ),
    );
  }
}

class _CircleIconButton extends StatelessWidget {
  const _CircleIconButton({required this.icon, required this.onTap});
  final IconData icon;
  final VoidCallback onTap;
  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(18),
      onTap: onTap,
      child: Container(
        width: 42,
        height: 42,
        decoration: pppdCardDecoration(),
        child: Icon(icon, size: 18, color: PppdColors.deepPurple),
      ),
    );
  }
}

class PppdPrimaryButton extends StatelessWidget {
  const PppdPrimaryButton({super.key, required this.text, required this.onTap, this.icon});
  final String text;
  final VoidCallback onTap;
  final IconData? icon;
  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(18),
      onTap: onTap,
      child: Container(
        height: 54,
        alignment: Alignment.center,
        decoration: BoxDecoration(
          borderRadius: BorderRadius.circular(18),
          gradient: const LinearGradient(colors: [Color(0xFF7B61FF), Color(0xFF9D7CFF)]),
          boxShadow: const [BoxShadow(color: Color(0x337B61FF), blurRadius: 20, offset: Offset(0, 10))],
        ),
        child: Row(
          mainAxisAlignment: MainAxisAlignment.center,
          children: [
            if (icon != null) ...[
              Icon(icon, color: Colors.white, size: 20),
              const SizedBox(width: 8),
            ],
            Text(text, style: pppdText(size: 16, weight: FontWeight.w800, color: Colors.white)),
          ],
        ),
      ),
    );
  }
}

class PppdActionCard extends StatelessWidget {
  const PppdActionCard({
    super.key,
    required this.title,
    required this.subtitle,
    required this.icon,
    required this.onTap,
    this.badge,
  });
  final String title;
  final String subtitle;
  final IconData icon;
  final VoidCallback onTap;
  final String? badge;
  @override
  Widget build(BuildContext context) {
    return InkWell(
      borderRadius: BorderRadius.circular(26),
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.all(20),
        decoration: pppdCardDecoration(),
        child: Row(
          children: [
            Container(
              width: 58,
              height: 58,
              decoration: BoxDecoration(
                color: PppdColors.softPurple,
                borderRadius: BorderRadius.circular(20),
              ),
              child: Icon(icon, color: PppdColors.purple, size: 28),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Expanded(child: Text(title, style: pppdText(size: 18, weight: FontWeight.w800))),
                      if (badge != null)
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
                          decoration: BoxDecoration(color: PppdColors.lavender, borderRadius: BorderRadius.circular(99)),
                          child: Text(badge!, style: pppdText(size: 11, color: PppdColors.purple, weight: FontWeight.w800)),
                        ),
                    ],
                  ),
                  const SizedBox(height: 6),
                  Text(subtitle, style: pppdText(size: 13, color: PppdColors.muted, height: 1.35)),
                ],
              ),
            ),
            const SizedBox(width: 8),
            const Icon(Icons.chevron_right_rounded, color: PppdColors.muted),
          ],
        ),
      ),
    );
  }
}

class PppdSectionCard extends StatelessWidget {
  const PppdSectionCard({super.key, required this.child, this.padding = const EdgeInsets.all(20)});
  final Widget child;
  final EdgeInsets padding;
  @override
  Widget build(BuildContext context) {
    return Container(
      width: double.infinity,
      padding: padding,
      decoration: pppdCardDecoration(),
      child: child,
    );
  }
}
