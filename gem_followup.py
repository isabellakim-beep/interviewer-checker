#!/usr/bin/env python3
"""
GEM 후보자 팔로업 이메일 생성 스크립트
GEM Candidate Follow-up Email Generation Script

이 스크립트는 GEM에서 내보낸 CSV 파일을 읽어 후보자를 HOT/WARM/COLD로 분류하고
각 그룹에 맞는 팔로업 이메일을 자동 생성합니다.

This script reads a CSV exported from GEM, classifies candidates into HOT/WARM/COLD,
and automatically generates follow-up emails tailored to each group.

사용법 / Usage:
    pip install anthropic
    export ANTHROPIC_API_KEY="sk-ant-..."
    python gem_followup.py
"""

import csv
import os
import sys
import logging
from typing import Optional

import anthropic

# ============================================================
# ⚙️  설정 변수 — 여기를 수정하세요 (Configuration — edit here)
# ============================================================

# 입력 CSV 파일 경로 (Input CSV file path)
INPUT_FILE = "gem_candidates.csv"

# 출력 파일 경로 (Output file paths)
OUTPUT_HOT_WARM = "gem_warm_hot_drafts.csv"
OUTPUT_COLD     = "gem_cold_bulk.csv"

# 이메일 템플릿에 사용할 회사명 / 발신자명
# Company name and sender name used in email templates
COMPANY_NAME = "[회사명]"
SENDER_NAME  = "[이름]"

# Claude 모델 — 사용자 지정: claude-sonnet-4-20250514 (alias)
# Claude model — user-specified: claude-sonnet-4-20250514
CLAUDE_MODEL = "claude-sonnet-4-0"

# HOT + WARM 합산 일일 최대 발송 수 (HOT 우선)
# Max daily sends for HOT + WARM combined (HOT gets priority)
MAX_DAILY_HOT_WARM = 20

# ============================================================
# 로깅 설정 (Logging setup)
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ============================================================
# 컬럼 매핑 — CSV 헤더명이 다를 경우 자동 매핑
# Column aliases — auto-maps when CSV header names differ
# ============================================================
COLUMN_ALIASES: dict[str, list[str]] = {
    "candidate_name": [
        "Candidate Name", "candidate_name", "name", "Name",
        "Full Name", "full_name", "Candidate", "candidate",
    ],
    "email_address": [
        "Email Address", "email_address", "email", "Email",
        "Email ID", "email_id",
    ],
    "sequence_name": [
        "Sequence Name", "sequence_name", "sequence", "Sequence",
        "Campaign Name", "campaign_name", "Position", "position",
        "Role", "role",
    ],
    "email_subject": [
        "Email Subject", "email_subject", "subject", "Subject",
        "Last Subject", "last_subject",
    ],
    "open_count": [
        "Open Count", "open_count", "opens", "Opens",
        "Email Opens", "email_opens", "Times Opened", "times_opened",
    ],
    "opened_at": [
        "Opened At", "opened_at", "Last Opened", "last_opened",
        "Last Open Date", "last_open_date", "Open Date", "open_date",
    ],
    "replied": [
        "Replied", "replied", "Has Replied", "has_replied",
        "Reply", "reply", "Responded", "responded",
    ],
}


# ============================================================
# 유틸리티 함수 (Utility helpers)
# ============================================================

def find_column(headers: list[str], field_key: str) -> Optional[str]:
    """CSV 헤더에서 필드에 해당하는 컬럼명을 찾습니다.
    Find the matching column name from CSV headers for a given field."""
    for alias in COLUMN_ALIASES.get(field_key, []):
        if alias in headers:
            return alias
    return None


def safe_get(row: dict, col: Optional[str], default: str = "") -> str:
    """컬럼이 없거나 값이 없을 때 기본값을 반환합니다.
    Return default if column is missing or value is empty."""
    if col is None:
        return default
    return str(row.get(col, default)).strip()


def parse_open_count(value: str) -> int:
    """오픈 횟수 문자열을 정수로 변환합니다.
    Parse open count string to integer."""
    try:
        return int(float(value.strip()))
    except (ValueError, AttributeError):
        return 0


def is_replied(value: str) -> bool:
    """회신 여부를 불리언으로 변환합니다.
    Convert replied field to boolean."""
    if not value:
        return False
    return value.strip().lower() in ("yes", "true", "1", "y", "replied", "응답함", "회신함")


def classify_candidate(open_count: int) -> str:
    """오픈 횟수에 따라 후보자를 HOT/WARM/COLD로 분류합니다.
    Classify candidate into HOT / WARM / COLD based on open count."""
    if open_count >= 3:
        return "HOT"
    elif open_count >= 1:
        return "WARM"
    return "COLD"


def priority_score(open_count: int) -> int:
    """우선순위 점수 = 오픈 횟수 × 10, 최대 100.
    Priority score = open_count × 10, capped at 100."""
    return min(open_count * 10, 100)


# ============================================================
# CSV 읽기 (CSV reading)
# ============================================================

def read_csv(file_path: str) -> tuple[list[dict], dict[str, Optional[str]]]:
    """CSV 파일을 읽고 컬럼 매핑을 반환합니다.
    Read CSV file and return (rows, column_mapping)."""
    if not os.path.exists(file_path):
        logger.error(f"입력 파일 없음 / File not found: {file_path}")
        sys.exit(1)

    rows: list[dict] = []
    col_map: dict[str, Optional[str]] = {}

    # UTF-8-BOM → UTF-8 → CP949(EUC-KR) 순으로 시도
    # Try encodings in order: UTF-8-BOM, UTF-8, CP949
    for encoding in ("utf-8-sig", "utf-8", "cp949"):
        try:
            with open(file_path, "r", encoding=encoding, newline="") as f:
                reader = csv.DictReader(f)
                headers = list(reader.fieldnames or [])
                logger.info(f"인코딩 / Encoding: {encoding}  |  헤더 / Headers: {headers}")

                # 컬럼 매핑 구성 (Build column mapping)
                for field_key in COLUMN_ALIASES:
                    matched = find_column(headers, field_key)
                    col_map[field_key] = matched
                    status = f"→ '{matched}'" if matched else "→ 없음 (missing)"
                    logger.info(f"  {'✓' if matched else '✗'} {field_key:20s} {status}")

                rows = [dict(r) for r in reader]
            break  # 성공 시 루프 탈출 (exit loop on success)
        except UnicodeDecodeError:
            continue
        except Exception as e:
            logger.error(f"CSV 읽기 오류 / Read error: {e}")
            sys.exit(1)
    else:
        logger.error("CSV 인코딩 변환 실패 / Could not decode CSV with any supported encoding")
        sys.exit(1)

    logger.info(f"총 {len(rows)}행 로드 / Loaded {len(rows)} rows")
    return rows, col_map


# ============================================================
# 후보자 분류 (Candidate classification)
# ============================================================

def process_candidates(
    rows: list[dict], col_map: dict[str, Optional[str]]
) -> tuple[list[dict], list[dict], list[dict]]:
    """후보자를 HOT / WARM / COLD로 분류합니다 (회신자 제외).
    Classify candidates into HOT / WARM / COLD (excludes replied)."""
    hot, warm, cold = [], [], []
    skipped = 0

    for i, row in enumerate(rows, start=2):  # row 2 = first data row after header
        try:
            name        = safe_get(row, col_map.get("candidate_name"))
            email       = safe_get(row, col_map.get("email_address"))
            sequence    = safe_get(row, col_map.get("sequence_name"))
            subject     = safe_get(row, col_map.get("email_subject"))
            open_raw    = safe_get(row, col_map.get("open_count"), "0")
            opened_at   = safe_get(row, col_map.get("opened_at"))
            replied_raw = safe_get(row, col_map.get("replied"), "No")

            # 이름·이메일 둘 다 없으면 건너뜀 (Skip if both name and email missing)
            if not name and not email:
                logger.warning(f"행 {i}: 이름/이메일 없음 — 건너뜀 / Row {i}: no name/email — skipped")
                skipped += 1
                continue

            open_count = parse_open_count(open_raw)
            replied    = is_replied(replied_raw)

            # 이미 회신한 후보자 제외 (Exclude candidates who have already replied)
            if replied:
                skipped += 1
                continue

            temp  = classify_candidate(open_count)
            score = priority_score(open_count)

            candidate = {
                "name":           name or "Unknown",
                "email":          email,
                "sequence":       sequence,
                "subject":        subject,
                "open_count":     open_count,
                "opened_at":      opened_at,
                "temperature":    temp,
                "priority_score": score,
            }

            if temp == "HOT":
                hot.append(candidate)
            elif temp == "WARM":
                warm.append(candidate)
            else:
                cold.append(candidate)

        except Exception as e:
            logger.warning(f"행 {i} 처리 오류 / Row {i} error: {e} — 건너뜀")
            skipped += 1
            continue

    # 오픈 횟수 내림차순 정렬 (Sort descending by open_count)
    hot.sort(key=lambda x: x["open_count"], reverse=True)
    warm.sort(key=lambda x: x["open_count"], reverse=True)

    logger.info(
        f"분류 결과 / Classification: HOT={len(hot)}, WARM={len(warm)}, "
        f"COLD={len(cold)}, 건너뜀/Skipped={skipped}"
    )
    return hot, warm, cold


def apply_daily_cap(
    hot: list[dict], warm: list[dict]
) -> tuple[list[dict], list[dict]]:
    """일일 최대 발송 수 적용 (HOT 우선, 나머지 WARM으로 채움).
    Apply daily cap — HOT first, fill remainder with WARM."""
    capped_hot  = hot[:MAX_DAILY_HOT_WARM]
    remaining   = MAX_DAILY_HOT_WARM - len(capped_hot)
    capped_warm = warm[:remaining]
    return capped_hot, capped_warm


# ============================================================
# 이메일 생성 — HOT & WARM (Claude API)
# Email generation — HOT & WARM via Claude API
# ============================================================

def generate_hot_warm_email(
    client: anthropic.Anthropic,
    candidate: dict,
) -> tuple[str, str]:
    """Claude API를 호출하여 HOT/WARM 이메일을 생성합니다.
    Call Claude API to generate HOT/WARM follow-up email.
    Returns (korean_email, english_email)."""

    name       = candidate["name"]
    sequence   = candidate["sequence"]
    subject    = candidate["subject"]
    open_count = candidate["open_count"]
    temp       = candidate["temperature"]

    # 온도별 지침 (Temperature-specific instructions)
    if temp == "HOT":
        tone = f"""
[HOT 가이드라인]
- 후보자가 이메일을 {open_count}번 확인했음을 자연스럽게 언급 (예: "몇 차례 메시지를 확인하신 것 같아 다시 연락드립니다")
- 이름({name})과 포지션({sequence}) 맥락 포함
- 강하고 직접적인 CTA: "이번 주 짧게 통화 나눠보실 수 있을까요?"
- 최대 5문장, 전문적인 한국어 마무리

[HOT Guidelines]
- Naturally reference that they opened the email {open_count} times
  e.g. "I noticed you've had a chance to look at my message a few times"
- Include name ({name}) and position context ({sequence})
- Strong, direct CTA: "Would you be available for a quick call this week?"
- Max 5 sentences, professional closing
"""
    else:  # WARM
        tone = f"""
[WARM 가이드라인]
- 이름({name})과 포지션({sequence})을 가볍게 언급
- 부드러운 CTA: "혹시 관심 있으시면 편하게 연락 주세요"
- 최대 5문장, 전문적인 한국어 마무리

[WARM Guidelines]
- Briefly mention name ({name}) and position ({sequence})
- Soft CTA: "Feel free to reach out if you're interested"
- Max 5 sentences, professional closing
"""

    prompt = f"""당신은 B2B 테크 스타트업의 채용 담당자입니다.
You are a recruiter at a B2B tech startup in South Korea.

다음 정보를 바탕으로 팔로업 이메일을 작성하세요:
Write a follow-up recruitment email based on:

- 후보자 이름 / Name: {name}
- 포지션 / Position: {sequence}
- 기존 이메일 제목 / Original Subject: {subject if subject else "(없음/none)"}
- 온도 그룹 / Temperature: {temp}

{tone}

반드시 아래 형식으로만 출력하세요. 다른 설명이나 메타 텍스트 없이:
Output EXACTLY in this format with NO other text:

=== KOREAN ===
(한국어 이메일 전체 내용)

=== ENGLISH ===
(Full English email content)"""

    try:
        response = client.messages.create(
            model=CLAUDE_MODEL,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )

        full_text = next(
            (block.text for block in response.content if block.type == "text"), ""
        )

        # 한국어 / 영어 섹션 파싱 (Parse Korean/English sections)
        if "=== KOREAN ===" in full_text and "=== ENGLISH ===" in full_text:
            parts   = full_text.split("=== ENGLISH ===")
            korean  = parts[0].replace("=== KOREAN ===", "").strip()
            english = parts[1].strip() if len(parts) > 1 else ""
        else:
            # 파싱 실패 — 전체 텍스트를 한국어로 사용
            # Parsing failed — use full text as Korean
            logger.warning(f"섹션 파싱 실패 / Section parse failed for {name}")
            korean  = full_text.strip()
            english = "[Translation pending — please write manually]"

        return korean, english

    except anthropic.APIError as e:
        logger.error(f"API 오류 / API error for {name}: {e}")
        return (
            f"[API 오류 — 수동 작성 필요] {name}님께",
            f"[API Error — please write manually] Dear {name},",
        )
    except Exception as e:
        logger.error(f"예상치 못한 오류 / Unexpected error for {name}: {e}")
        return "[오류 발생 — 수동 작성 필요]", "[Error — please write manually]"


def generate_emails_hot_warm(
    client: anthropic.Anthropic,
    hot_capped: list[dict],
    warm_capped: list[dict],
) -> list[dict]:
    """HOT + WARM 후보자 전체에 대해 Claude API 이메일을 생성합니다.
    Generate Claude API emails for all HOT + WARM candidates."""
    results = []
    all_hw  = hot_capped + warm_capped
    total   = len(all_hw)

    for i, candidate in enumerate(all_hw, start=1):
        logger.info(
            f"[{i}/{total}] {candidate['temperature']} 이메일 생성 중 / "
            f"Generating email: {candidate['name']}"
        )
        korean, english = generate_hot_warm_email(client, candidate)
        results.append({**candidate, "korean_email": korean, "english_email": english})

    return results


# ============================================================
# 이메일 생성 — COLD (템플릿, API 호출 없음)
# Email generation — COLD (template, no API call)
# ============================================================

def generate_cold_email(candidate: dict) -> tuple[str, str]:
    """COLD 후보자용 대량 이메일 템플릿을 채웁니다 (Claude API 미사용 — 비용 절약).
    Fill bulk email template for COLD candidates (no Claude API — cost-saving)."""
    name     = candidate["name"]
    sequence = candidate["sequence"] or "채용 / Recruitment"

    korean = (
        f"제목: {COMPANY_NAME} {sequence} 포지션 관련 안내\n\n"
        f"안녕하세요, {name}님.\n\n"
        f"{COMPANY_NAME}에서 {sequence} 포지션 채용을 진행 중에 있어 연락드립니다.\n"
        f"혹시 새로운 기회에 관심이 있으시다면, 편하게 회신 주시면 감사하겠습니다.\n"
        f"좋은 하루 되세요!\n\n"
        f"감사합니다,\n"
        f"{SENDER_NAME} 드림"
    )

    english = (
        f"Subject: Regarding the {sequence} Position at {COMPANY_NAME}\n\n"
        f"Hello {name},\n\n"
        f"I'm reaching out from {COMPANY_NAME} regarding our ongoing {sequence} position.\n"
        f"If you're open to exploring new opportunities, please feel free to reply at your convenience.\n"
        f"Hope you have a wonderful day!\n\n"
        f"Best regards,\n"
        f"{SENDER_NAME}"
    )

    return korean, english


def generate_emails_cold(cold_all: list[dict]) -> list[dict]:
    """COLD 후보자 전체에 대해 템플릿 이메일을 채웁니다.
    Fill template emails for all COLD candidates."""
    results = []
    for candidate in cold_all:
        korean, english = generate_cold_email(candidate)
        results.append({**candidate, "korean_email": korean, "english_email": english})
    return results


# ============================================================
# CSV 저장 (CSV saving)
# ============================================================

def save_hot_warm_csv(candidates: list[dict], file_path: str) -> None:
    """HOT/WARM 이메일 초안을 CSV로 저장합니다.
    Save HOT/WARM email drafts to CSV."""
    fieldnames = [
        "Candidate Name",
        "Email",
        "Temperature",
        "Open Count",
        "Last Opened At",
        "Original Subject",
        "Follow-Up Email (Korean)",
        "Follow-Up Email (English)",
        "Priority Score",
    ]
    with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in candidates:
            writer.writerow({
                "Candidate Name":           c["name"],
                "Email":                    c["email"],
                "Temperature":              c["temperature"],
                "Open Count":               c["open_count"],
                "Last Opened At":           c["opened_at"],
                "Original Subject":         c["subject"],
                "Follow-Up Email (Korean)": c["korean_email"],
                "Follow-Up Email (English)":c["english_email"],
                "Priority Score":           c["priority_score"],
            })
    logger.info(f"저장 완료 / Saved: {file_path}  ({len(candidates)} rows)")


def save_cold_csv(candidates: list[dict], file_path: str) -> None:
    """COLD 대량 이메일을 CSV로 저장합니다.
    Save COLD bulk emails to CSV."""
    fieldnames = [
        "Candidate Name",
        "Email",
        "Sequence Name",
        "Bulk Email (Korean)",
        "Bulk Email (English)",
    ]
    with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for c in candidates:
            writer.writerow({
                "Candidate Name":      c["name"],
                "Email":               c["email"],
                "Sequence Name":       c["sequence"],
                "Bulk Email (Korean)": c["korean_email"],
                "Bulk Email (English)":c["english_email"],
            })
    logger.info(f"저장 완료 / Saved: {file_path}  ({len(candidates)} rows)")


# ============================================================
# 터미널 요약 출력 (Terminal summary)
# ============================================================

def print_summary(
    hot_total: int,
    warm_total: int,
    cold_total: int,
    hot_sent: int,
    warm_sent: int,
) -> None:
    daily = hot_sent + warm_sent
    print()
    print("=" * 45)
    print("  ====== GEM 팔로업 이메일 생성 완료 ======")
    print("=" * 45)
    print(f"  🔥 HOT 후보자:       {hot_total}명")
    print(f"  🌤️  WARM 후보자:      {warm_total}명")
    print(f"  ❄️  COLD 후보자:      {cold_total}명")
    print("  " + "-" * 41)
    print(f"  오늘 발송 대상 (HOT+WARM): {daily}명 (최대 {MAX_DAILY_HOT_WARM}명)")
    if hot_total > hot_sent:
        print(f"    ※ HOT 초과 {hot_total - hot_sent}명 내일 대상")
    if warm_total > warm_sent:
        print(f"    ※ WARM 초과 {warm_total - warm_sent}명 내일 대상")
    print(f"  COLD 대량 발송 대상:        {cold_total}명")
    print("  " + "-" * 41)
    print("  파일 저장 완료:")
    print(f"    → {OUTPUT_HOT_WARM}")
    print(f"    → {OUTPUT_COLD}")
    print("  발송 전 반드시 내용을 검토하세요 ✅")
    print("=" * 45)
    print()


# ============================================================
# 메인 진입점 (Main entry point)
# ============================================================

def main() -> None:
    print(f"\n📋 입력 파일 / Input: {INPUT_FILE}")
    print(f"🤖 모델 / Model:      {CLAUDE_MODEL}")
    print(f"🏢 회사명 / Company:  {COMPANY_NAME}\n")

    # 1. API 키 확인 (Validate API key)
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        logger.error(
            "ANTHROPIC_API_KEY 환경변수가 없습니다 / "
            "ANTHROPIC_API_KEY environment variable is not set.\n"
            "  export ANTHROPIC_API_KEY='sk-ant-...'"
        )
        sys.exit(1)

    # 2. Anthropic 클라이언트 초기화 (Init Anthropic client)
    client = anthropic.Anthropic(api_key=api_key)

    # 3. CSV 읽기 (Read CSV)
    logger.info("=== STEP 1: CSV 읽기 / Reading CSV ===")
    rows, col_map = read_csv(INPUT_FILE)
    if not rows:
        logger.error("CSV에 데이터가 없습니다 / CSV has no data rows")
        sys.exit(1)

    # 4. 후보자 분류 (Classify candidates)
    logger.info("=== STEP 2: 후보자 분류 / Classifying candidates ===")
    hot_all, warm_all, cold_all = process_candidates(rows, col_map)

    # 5. 일일 캡 적용 (Apply daily cap)
    hot_capped, warm_capped = apply_daily_cap(hot_all, warm_all)
    logger.info(
        f"일일 발송 대상 / Daily targets: "
        f"HOT={len(hot_capped)}, WARM={len(warm_capped)}, "
        f"COLD={len(cold_all)} (전체/all)"
    )

    # 6. HOT/WARM 이메일 생성 — Claude API 호출
    # Generate HOT/WARM emails via Claude API
    logger.info("=== STEP 3A: HOT/WARM 이메일 생성 (Claude API) ===")
    if hot_capped or warm_capped:
        hw_results = generate_emails_hot_warm(client, hot_capped, warm_capped)
    else:
        hw_results = []
        logger.info("HOT/WARM 후보자 없음 / No HOT/WARM candidates to process")

    # 7. COLD 이메일 생성 — 템플릿 (API 미사용, 비용 절약)
    # Generate COLD emails via template (no API, cost-saving)
    logger.info(f"=== STEP 3B: COLD 템플릿 생성 ({len(cold_all)}명) ===")
    cold_results = generate_emails_cold(cold_all)

    # 8. CSV 저장 (Save output CSVs)
    logger.info("=== STEP 4: 결과 저장 / Saving results ===")
    save_hot_warm_csv(hw_results, OUTPUT_HOT_WARM)
    save_cold_csv(cold_results, OUTPUT_COLD)

    # 9. 요약 출력 (Print summary)
    print_summary(
        hot_total=len(hot_all),
        warm_total=len(warm_all),
        cold_total=len(cold_all),
        hot_sent=len(hot_capped),
        warm_sent=len(warm_capped),
    )


if __name__ == "__main__":
    main()
