"""Deterministic time and numeric normalization utilities for operator directives."""

import re
from typing import Optional


def parse_hour_str(s: str) -> Optional[int]:
    """Parse an hour string (e.g., '2 PM', '14:00', 'noon', 'midnight', '14') into 0..23."""
    clean = s.strip().lower()
    if clean in ("noon", "12 noon"):
        return 12
    if clean in ("midnight", "12 midnight"):
        return 0

    # Match format like '14:00' or '2:00 pm'
    m_colon = re.match(r"^(\d{1,2}):(\d{2})\s*(am|pm)?$", clean)
    if m_colon:
        h = int(m_colon.group(1))
        meridiem = m_colon.group(3)
        if meridiem == "pm" and h < 12:
            h += 12
        elif meridiem == "am" and h == 12:
            h = 0
        return h if 0 <= h <= 23 else None

    # Match format like '2 pm' or '11 am'
    m_ampm = re.match(r"^(\d{1,2})\s*(am|pm)$", clean)
    if m_ampm:
        h = int(m_ampm.group(1))
        meridiem = m_ampm.group(2)
        if meridiem == "pm" and h < 12:
            h += 12
        elif meridiem == "am" and h == 12:
            h = 0
        return h if 0 <= h <= 23 else None

    # Word numbers with am/pm or plain
    word_to_num = {
        "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
        "seven": 7, "eight": 8, "nine": 9, "ten": 10, "eleven": 11, "twelve": 12,
    }
    m_word = re.match(r"^(one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve)\s*(am|pm)?$", clean)
    if m_word:
        h = word_to_num[m_word.group(1)]
        meridiem = m_word.group(2)
        if meridiem == "pm" and h < 12:
            h += 12
        elif meridiem == "am" and h == 12:
            h = 0
        return h

    # Plain integer
    if clean.isdigit():
        h = int(clean)
        return h if 0 <= h <= 23 else None

    return None


def extract_time_window(text: str) -> Optional[list[int]]:
    """
    Extract start-inclusive, end-exclusive hour window from natural language.
    E.g. 'from 1 PM to 3 PM' -> [13, 14]
    'from noon until 2 PM' -> [12, 13]
    'between 11 AM and 2 PM' -> [11, 12, 13]
    'from 11 AM until 1 PM' -> [11, 12]
    'from one until three' in afternoon -> [13, 14]
    """
    clean = text.lower()

    # Case 1: Check 1-3 PM or 1–3 PM (with dash)
    m_dash = re.search(r"(\d{1,2})\s*[-–]\s*(\d{1,2})\s*(am|pm)", clean)
    if m_dash:
        start_raw = m_dash.group(1)
        end_raw = m_dash.group(2)
        meridiem = m_dash.group(3)
        start_h = parse_hour_str(f"{start_raw} {meridiem}")
        end_h = parse_hour_str(f"{end_raw} {meridiem}")
        if start_h is not None and end_h is not None:
            if start_h >= end_h and meridiem == "pm" and int(start_raw) > int(end_raw):
                # E.g. 11-2 PM where 11 is AM
                start_h = int(start_raw)
            if start_h < end_h:
                return list(range(start_h, end_h))

    # Case 2: General 'from/between X to/until/and Y'
    patterns = [
        r"(?:from|between|during)\s+([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?|noon|midnight|[a-z]+(?:\s*(?:am|pm))?)\s+(?:until|to|through|and|-)\s+([0-9]{1,2}(?::[0-9]{2})?\s*(?:am|pm)?|noon|midnight|[a-z]+(?:\s*(?:am|pm))?)",
    ]

    for pat in patterns:
        m = re.search(pat, clean)
        if m:
            start_str = m.group(1).strip()
            end_str = m.group(2).strip()

            start_has_meridiem = any(x in start_str for x in ["am", "pm", "noon", "midnight"])
            end_has_meridiem = any(x in end_str for x in ["am", "pm", "noon", "midnight"])

            start_h = parse_hour_str(start_str)
            end_h = parse_hour_str(end_str)

            # If words like 'one until three'
            if start_h is not None and end_h is not None:
                if not start_has_meridiem and not end_has_meridiem:
                    if "afternoon" in clean or "evening" in clean or "pm" in clean:
                        if start_h < 12:
                            start_h += 12
                        if end_h < 12:
                            end_h += 12
                elif not start_has_meridiem and end_has_meridiem:
                    # e.g. 'from 6 until 9 PM' or 'from 2 until 5 AM'
                    if "pm" in end_str:
                        if start_h < 12 and start_h <= end_h % 12:
                            start_h += 12
                    elif "am" in end_str:
                        if start_h == 12:
                            start_h = 0

                if start_h < end_h and 0 <= start_h <= 23 and 0 <= end_h <= 24:
                    return list(range(start_h, end_h))

    return None


def extract_solar_factor(text: str) -> Optional[float]:
    """
    Extract usable solar fraction (0..1) from text.
    Handles 'reduce by X%', 'reduce solar by X%', 'X% reduction', 'drop to X%', 'fraction', etc.
    """
    clean = text.lower()

    # Case 1: Reduction by X% -> factor = 1 - X/100
    m_reduce = re.search(r"(?:reduction of|reduce[a-z]*(?:\s+[a-z]+)?\s+by|drop by)\s+(\d{1,3}(?:\.\d+)?)\s*%", clean)
    if not m_reduce:
        m_reduce = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%\s*reduction", clean)
    if m_reduce:
        pct = float(m_reduce.group(1))
        return round(max(0.0, min(1.0, 1.0 - (pct / 100.0))), 4)

    # Case 2: Drop to X%, treated as X%, limited to X%, around X% -> factor = X/100
    m_pct = re.search(r"(?:drop to|treated as|limited to|leaves?|remain[a-z]* at|about|roughly|output of)\s+(?:about|roughly)?\s*(\d{1,3}(?:\.\d+)?)\s*%", clean)
    if not m_pct:
        m_pct = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:of (?:the )?forecast|of normal)", clean)
    if m_pct:
        pct = float(m_pct.group(1))
        return round(max(0.0, min(1.0, pct / 100.0)), 4)

    # Case 3: Word fractions
    if "half" in clean:
        return 0.50
    if "one-fifth" in clean or "one fifth" in clean:
        return 0.20
    if "one-quarter" in clean or "one quarter" in clean or "one-fourth" in clean:
        return 0.25
    if "three-quarters" in clean or "three quarters" in clean:
        return 0.75

    return None


def extract_battery_reserve(text: str, battery_capacity_kwh: Optional[float] = None) -> Optional[float]:
    """
    Extract minimum battery reserve in kWh.
    If given as percentage (e.g. '50% of the battery capacity'), multiplies by battery_capacity_kwh.
    """
    clean = text.lower()

    # Percentage of capacity
    m_pct = re.search(r"(\d{1,3}(?:\.\d+)?)\s*%\s*(?:of (?:the )?(?:battery )?capacity)", clean)
    if m_pct and battery_capacity_kwh is not None:
        pct = float(m_pct.group(1))
        return round((pct / 100.0) * battery_capacity_kwh, 2)

    # Absolute kWh
    m_kwh = re.search(r"(?:at least|reserve of|remain in the battery|in the battery|in storage)\s+(\d+(?:\.\d+)?)\s*kwh", clean)
    if not m_kwh:
        m_kwh = re.search(r"(\d+(?:\.\d+)?)\s*kwh\s*(?:in (?:the )?(?:battery|storage|reserve))", clean)
    if not m_kwh:
        m_kwh = re.search(r"(\d+(?:\.\d+)?)\s*kwh", clean)
    if m_kwh:
        return round(float(m_kwh.group(1)), 2)

    return None


def extract_max_grid(text: str) -> Optional[float]:
    """Extract max grid import cap in kWh."""
    clean = text.lower()
    m = re.search(r"(?:not exceed|stay at or below|cap(?:ped)? at|limit(?:ed)? to|intake must stay at or below|limit is)\s+(\d+(?:\.\d+)?)\s*kwh", clean)
    if not m:
        m = re.search(r"(\d+(?:\.\d+)?)\s*kwh\s*(?:of grid import|grid cap|grid limit)", clean)
    if m:
        return round(float(m.group(1)), 2)
    return None
