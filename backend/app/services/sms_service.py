"""SMS character and segment counting (GSM 7-bit and UCS-2).

Implements the real SMS encoding rules:

- GSM 7-bit default alphabet: 160 chars per segment, 153 when
  concatenated (7 remaining chars are used for the UDH).
- UCS-2 (any non-GSM character present): 70 chars per segment, 67 when
  concatenated.

The character set tables follow 3GPP TS 23.038 (basic + extension table).
"""

from dataclasses import dataclass

# GSM 7-bit default alphabet (basic table).
GSM_BASIC = (
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞ\x1bÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?"
    "¡ABCDEFGHIJKLMNOPQRSTUVWXYZÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà"
)

# GSM 7-bit extension table characters (each counts as 2 chars in a segment).
GSM_EXTENDED = set("^{}\\[~]|€")

GSM_ESCAPE = "\x1b"

# Characters that the GSM basic table contains but which are problematic
# to type directly (CR etc. are in the table already via literals).


def is_gsm_7bit(text: str) -> bool:
    """True when every character exists in the GSM 7-bit alphabet."""
    for ch in text:
        if ch == GSM_ESCAPE:
            continue
        if ch in GSM_EXTENDED:
            continue
        if ch not in GSM_BASIC:
            return False
    return True


def gsm_segment_length(text: str) -> int:
    """Length of a string in GSM 7-bit 'characters' (escapes count 2)."""
    length = 0
    for ch in text:
        if ch in GSM_EXTENDED or ch == GSM_ESCAPE:
            length += 2
        else:
            length += 1
    return length


@dataclass
class SmsAnalysis:
    characters: int
    segments: int
    encoding: str  # "GSM-7" | "UCS-2"
    per_segment: int  # max chars per segment for this encoding
    truncated: bool  # True when content would exceed a single segment
    exceed_limit: bool  # True when > 10 segments (practical SMS limit)

    @property
    def segment_count(self) -> int:
        return self.segments


MAX_GSM_SEGMENTS = 10  # practical hard limit used by most providers


def analyze_message(text: str | None) -> SmsAnalysis:
    """Analyze a message and return character + segment counts.

    Mirrors the logic used by the frontend `smsCounter` utility so the
    user sees identical numbers on both sides.
    """
    if text is None:
        text = ""

    if is_gsm_7bit(text):
        encoding = "GSM-7"
        chars = gsm_segment_length(text)
        per_segment = 160
        per_segment_concat = 153
    else:
        encoding = "UCS-2"
        chars = len(text)
        per_segment = 70
        per_segment_concat = 67

    if chars <= per_segment:
        segments = 1
    else:
        capacity = per_segment_concat
        segments = (chars + capacity - 1) // capacity

    return SmsAnalysis(
        characters=chars,
        segments=segments,
        encoding=encoding,
        per_segment=per_segment,
        truncated=chars > per_segment,
        exceed_limit=segments > MAX_GSM_SEGMENTS,
    )
