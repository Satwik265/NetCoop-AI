/**
 * Internationalization (i18n) and Locale-Aware Formatting Utilities
 * Adheres to W3C Internationalization Guidance and WCAG 2.2 AA.
 *
 * Rules:
 * - Machine-readable protocol codes, RFC terms, and device identifiers are NEVER translated.
 * - Dates and timestamps always include explicit timezone indicators (e.g. 'UTC', 'IST').
 * - Numbers and metrics are formatted using standard browser Intl APIs without mutating
 *   canonical underlying SI units.
 */

export type SupportedTimezone = "UTC" | "Asia/Kolkata" | "LOCAL";

export interface TimezoneOption {
  id: SupportedTimezone;
  label: string;
  badge: string;
  timeZoneString?: string;
}

export const TIMEZONE_OPTIONS: TimezoneOption[] = [
  { id: "UTC", label: "Coordinated Universal Time (UTC)", badge: "UTC", timeZoneString: "UTC" },
  { id: "Asia/Kolkata", label: "Campus Time (IST / Asia/Kolkata)", badge: "IST", timeZoneString: "Asia/Kolkata" },
  { id: "LOCAL", label: "Operator Local Time", badge: "LOCAL" },
];

/**
 * Format an ISO timestamp or Date into a human-readable, locale-aware date string
 * with an explicit timezone suffix.
 */
export function formatDateTime(
  dateInput: string | number | Date | null | undefined,
  timezone: SupportedTimezone = "UTC",
  options?: {
    includeSeconds?: boolean;
    locale?: string;
  }
): string {
  if (!dateInput) return "N/A";

  const date = typeof dateInput === "object" ? dateInput : new Date(dateInput);
  if (isNaN(date.getTime())) {
    return String(dateInput);
  }

  const locale = options?.locale || "en-US";
  const includeSeconds = options?.includeSeconds ?? true;

  const resolvedTz = timezone === "LOCAL" ? undefined : timezone;
  const tzBadge = timezone === "UTC" ? "UTC" : timezone === "Asia/Kolkata" ? "IST" : "LOCAL";

  try {
    const formatter = new Intl.DateTimeFormat(locale, {
      year: "numeric",
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
      second: includeSeconds ? "2-digit" : undefined,
      hour12: false,
      timeZone: resolvedTz,
    });

    return `${formatter.format(date)} ${tzBadge}`;
  } catch {
    // Fallback if environment lacks specified timezone
    return `${date.toISOString().replace("T", " ").replace("Z", "")} UTC`;
  }
}

/**
 * Format a floating-point confidence or probability as a localized percentage string.
 */
export function formatPercent(
  value: number | null | undefined,
  decimals: number = 1,
  locale: string = "en-US"
): string {
  if (value === null || value === undefined || isNaN(value)) {
    return "N/A";
  }

  try {
    const formatter = new Intl.NumberFormat(locale, {
      style: "percent",
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
    return formatter.format(value);
  } catch {
    return `${(value * 100).toFixed(decimals)}%`;
  }
}

/**
 * Format numeric telemetry counts (drops, packets, errors) with locale-aware digit groupings.
 */
export function formatNumber(
  value: number | null | undefined,
  decimals: number = 0,
  locale: string = "en-US"
): string {
  if (value === null || value === undefined || isNaN(value)) {
    return "0";
  }

  try {
    const formatter = new Intl.NumberFormat(locale, {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    });
    return formatter.format(value);
  } catch {
    return decimals > 0 ? value.toFixed(decimals) : String(Math.round(value));
  }
}

/**
 * Format bytes into human-readable data volume with SI prefixes.
 */
export function formatBytes(bytes: number | null | undefined, locale: string = "en-US"): string {
  if (bytes === null || bytes === undefined || isNaN(bytes)) return "0 B";
  if (bytes === 0) return "0 B";

  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB", "PB"];
  const i = Math.floor(Math.log(Math.abs(bytes)) / Math.log(k));
  const idx = Math.min(i, sizes.length - 1);
  const val = bytes / Math.pow(k, idx);

  return `${formatNumber(val, idx === 0 ? 0 : 2, locale)} ${sizes[idx]}`;
}

/**
 * Format bitrates (bps, Kbps, Mbps, Gbps).
 */
export function formatRate(bps: number | null | undefined, locale: string = "en-US"): string {
  if (bps === null || bps === undefined || isNaN(bps)) return "0 bps";
  if (bps === 0) return "0 bps";

  const k = 1000;
  const units = ["bps", "Kbps", "Mbps", "Gbps", "Tbps"];
  const i = Math.floor(Math.log(Math.abs(bps)) / Math.log(k));
  const idx = Math.min(i, units.length - 1);
  const val = bps / Math.pow(k, idx);

  return `${formatNumber(val, idx === 0 ? 0 : 1, locale)} ${units[idx]}`;
}

/**
 * Format milliseconds with appropriate precision.
 */
export function formatDurationMs(ms: number | null | undefined, locale: string = "en-US"): string {
  if (ms === null || ms === undefined || isNaN(ms)) return "0 ms";
  if (ms < 1000) {
    return `${formatNumber(ms, 1, locale)} ms`;
  }
  return `${formatNumber(ms / 1000, 2, locale)} s`;
}
