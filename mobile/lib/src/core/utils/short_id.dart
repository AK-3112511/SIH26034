/// Abbreviate an identifier for display.
///
/// Callers used to write `id.substring(0, 8)` directly, which throws a
/// RangeError on any id shorter than eight characters - for example the
/// `ACK-<n>` placeholder the sync worker falls back to when a server response
/// omits `scan_id`. Crashing a list tile over a cosmetic abbreviation is never
/// the right trade, so this clamps instead.
String shortId(String? id, {int length = 8}) {
  if (id == null || id.isEmpty) return 'UNKNOWN';
  final take = id.length < length ? id.length : length;
  return id.substring(0, take).toUpperCase();
}
