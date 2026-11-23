"""Mini NPU 시뮬레이터

MAC(Multiply-Accumulate) 연산으로 Cross / X 패턴을 판별하는 콘솔 애플리케이션.
표준 라이브러리만 사용한다.
"""

import json
import math
import os
import re
import sys
import time

EPSILON = 1e-9          # 점수 비교 허용오차
REPEAT = 10             # 성능 측정 반복 횟수
DATA_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data.json")

CROSS = "Cross"
X = "X"
UNDECIDED = "UNDECIDED"

LABEL_MAP = {
    "+": CROSS,
    "cross": CROSS,
    "x": X,
}

# 모드 1 기본 예시 (3x3)
SAMPLE_CROSS = [[0, 1, 0], [1, 1, 1], [0, 1, 0]]
SAMPLE_X = [[1, 0, 1], [0, 1, 0], [1, 0, 1]]


# ---------------------------------------------------------------------------
# 핵심 연산
# ---------------------------------------------------------------------------
def mac(pattern, filt):
    """같은 위치끼리 곱하고 모두 더한다 (반복문 직접 구현)."""
    n = len(pattern)
    total = 0.0
    for i in range(n):
        for j in range(n):
            total += pattern[i][j] * filt[i][j]
    return total


def judge(score_a, score_b, label_a, label_b):
    """epsilon 기반 비교. 동점이면 UNDECIDED."""
    if abs(score_a - score_b) < EPSILON:
        return UNDECIDED
    return label_a if score_a > score_b else label_b


def measure_ms(pattern, filt, repeat=REPEAT):
    """MAC 연산 1회당 평균 시간(ms). I/O는 포함하지 않는다."""
    elapsed = 0.0
    for _ in range(repeat):
        start = time.perf_counter()
        mac(pattern, filt)
        elapsed += time.perf_counter() - start
    return elapsed / repeat * 1000.0


def normalize_label(raw):
    """다양한 라벨 표기를 표준 라벨(Cross / X)로 변환. 알 수 없으면 None."""
    if not isinstance(raw, str):
        return None
    return LABEL_MAP.get(raw.strip().lower())


def fmt_matrix_size(n):
    return "{0}×{0}".format(n)


# ---------------------------------------------------------------------------
# 행렬 검증
# ---------------------------------------------------------------------------
def matrix_error(matrix, expected_n=None):
    """올바른 n×n 숫자 행렬이면 None, 아니면 오류 사유 문자열."""
    if not isinstance(matrix, list) or not matrix:
        return "2차원 배열이 아님"
    n = len(matrix)
    for row in matrix:
        if not isinstance(row, list):
            return "2차원 배열이 아님"
        if len(row) != n:
            return "정사각형이 아님 (행 {0}개, 열 {1}개)".format(n, len(row))
        for v in row:
            if isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v):
                return "숫자가 아닌 값 포함: {0!r}".format(v)
    if expected_n is not None and n != expected_n:
        return "크기 불일치 (기대 {0}×{0}, 실제 {1}×{1})".format(expected_n, n)
    return None


# ---------------------------------------------------------------------------
# 모드 1: 사용자 입력 (3x3)
# ---------------------------------------------------------------------------
def read_matrix(title, n=3):
    """n줄을 입력받는다. 형식 오류 시 안내 후 처음부터 다시 입력."""
    while True:
        print("{0} ({1}줄 입력, 공백 구분)".format(title, n))
        rows = []
        error = None
        for _ in range(n):
            line = input()
            parts = line.split()
            if len(parts) != n:
                error = "입력 형식 오류: 각 줄에 {0}개의 숫자를 공백으로 구분해 입력하세요.".format(n)
            else:
                try:
                    row = [float(p) for p in parts]
                except ValueError:
                    error = "입력 형식 오류: 숫자만 입력하세요."
                else:
                    if not all(math.isfinite(v) for v in row):
                        error = "입력 형식 오류: 유한한 숫자만 입력하세요."
                    else:
                        rows.append(row)
            if error:
                break
        if error is None:
            return rows
        print(error)
        print("{0}을(를) 처음부터 다시 입력해 주세요.\n".format(title))


def print_header(text):
    print("#" + "-" * 39)
    print("# " + text)
    print("#" + "-" * 39)


def run_mode1():
    print_header("[1] 필터 입력")
    filt_a = read_matrix("필터 A")
    print()
    filt_b = read_matrix("필터 B")
    print("\n✓ 필터 A, B 저장 완료\n")

    print_header("[2] 패턴 입력")
    pattern = read_matrix("패턴")
    print("\n✓ 패턴 저장 완료\n")

    score_a = mac(pattern, filt_a)
    score_b = mac(pattern, filt_b)
    avg_ms = (measure_ms(pattern, filt_a) + measure_ms(pattern, filt_b)) / 2

    print_header("[3] MAC 결과")
    print("A 점수: {0!r}".format(score_a))
    print("B 점수: {0!r}".format(score_b))
    print("연산 시간(평균/{0}회): {1:.4f} ms".format(REPEAT, avg_ms))
    result = judge(score_a, score_b, "A", "B")
    if result == UNDECIDED:
        print("판정: 판정 불가 (|A-B| < 1e-9)")
    else:
        print("판정: {0}".format(result))
    print()

    print_header("[4] 성능 분석 (3×3)")
    print_perf_table([(3, avg_ms)])


# ---------------------------------------------------------------------------
# 모드 2: data.json 분석
# ---------------------------------------------------------------------------
def load_json(path):
    """JSON 로드. 실패 시 (None, 사유)."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f), None
    except FileNotFoundError:
        return None, "파일을 찾을 수 없음: {0}".format(path)
    except json.JSONDecodeError as e:
        return None, "JSON 파싱 실패: {0}".format(e)
    except OSError as e:
        return None, "파일 읽기 실패: {0}".format(e)


def load_filters(raw_filters):
    """filters 섹션 검증/정규화.

    반환: {size: {표준라벨: 행렬}}, 크기별 오류 {키: 사유}
    """
    filters = {}
    errors = {}
    if not isinstance(raw_filters, dict):
        return filters, {"filters": "filters 섹션이 객체가 아님"}

    for key, group in raw_filters.items():
        m = re.fullmatch(r"size_(\d+)", str(key))
        if not m:
            errors[key] = "필터 키 형식 오류 (size_N 이어야 함)"
            continue
        n = int(m.group(1))
        if not isinstance(group, dict):
            errors[key] = "필터 그룹이 객체가 아님"
            continue

        normalized = {}
        problem = None
        for raw_label, matrix in group.items():
            label = normalize_label(raw_label)
            if label is None:
                problem = "알 수 없는 필터 라벨: {0!r}".format(raw_label)
                break
            err = matrix_error(matrix, n)
            if err:
                problem = "{0} 필터 오류: {1}".format(label, err)
                break
            normalized[label] = matrix
        if problem is None and (CROSS not in normalized or X not in normalized):
            problem = "Cross/X 필터가 모두 필요함 (현재: {0})".format(", ".join(normalized) or "없음")
        if problem:
            errors[key] = problem
        else:
            filters[n] = normalized
    return filters, errors


def analyze_pattern(key, item, filters, filter_errors):
    """패턴 1건 분석. 결과 dict 반환 (예외로 중단되지 않음)."""
    result = {"key": key, "status": "FAIL", "reason": "", "lines": []}

    m = re.fullmatch(r"size_(\d+)_(\w+)", str(key))
    if not m:
        result["reason"] = "패턴 키 형식 오류 (size_N_idx 이어야 함)"
        return result
    n = int(m.group(1))

    if not isinstance(item, dict):
        result["reason"] = "패턴 항목이 객체가 아님"
        return result
    if "input" not in item or "expected" not in item:
        missing = [k for k in ("input", "expected") if k not in item]
        result["reason"] = "스키마 오류: {0} 누락".format(", ".join(missing))
        return result

    expected = normalize_label(item["expected"])
    if expected is None:
        result["reason"] = "expected 라벨 오류: {0!r}".format(item["expected"])
        return result

    size_key = "size_{0}".format(n)
    if n not in filters:
        reason = filter_errors.get(size_key, "{0} 필터가 없음".format(size_key))
        result["reason"] = "필터 사용 불가: {0}".format(reason)
        return result

    err = matrix_error(item["input"], n)
    if err:
        result["reason"] = "패턴 오류: {0}".format(err)
        return result

    pattern = item["input"]
    score_cross = mac(pattern, filters[n][CROSS])
    score_x = mac(pattern, filters[n][X])
    verdict = judge(score_cross, score_x, CROSS, X)

    result["lines"] = [
        "Cross 점수: {0!r}".format(score_cross),
        "X 점수: {0!r}".format(score_x),
    ]
    if verdict == expected:
        result["status"] = "PASS"
        result["line"] = "판정: {0} | expected: {1} | PASS".format(verdict, expected)
    else:
        if verdict == UNDECIDED:
            result["reason"] = "동점(UNDECIDED) 처리 규칙에 따라 FAIL"
            note = " (동점 규칙)"
        else:
            result["reason"] = "판정 {0} != expected {1}".format(verdict, expected)
            note = ""
        result["line"] = "판정: {0} | expected: {1} | FAIL{2}".format(verdict, expected, note)
    return result


def print_perf_table(rows):
    print("{0:<10}{1:>16}{2:>14}".format("크기", "평균 시간(ms)", "연산 횟수"))
    print("-" * 40)
    for n, ms in rows:
        print("{0:<10}{1:>16.4f}{2:>14}".format(fmt_matrix_size(n), ms, n * n))
    print()


def run_mode2(path=DATA_FILE):
    data, err = load_json(path)
    if err:
        print("오류: {0}".format(err))
        return
    if not isinstance(data, dict):
        print("오류: 최상위 JSON이 객체가 아닙니다.")
        return

    print_header("[1] 필터 로드")
    filters, filter_errors = load_filters(data.get("filters"))
    for n in sorted(filters):
        print("✓ size_{0:<3} 필터 로드 완료 ({1}, {2})".format(n, CROSS, X))
    for key, reason in filter_errors.items():
        print("✗ {0} 필터 로드 실패: {1}".format(key, reason))
    print()

    print_header("[2] 패턴 분석 (라벨 정규화 적용)")
    patterns = data.get("patterns")
    results = []
    if not isinstance(patterns, dict):
        print("오류: patterns 섹션이 없거나 객체가 아닙니다.")
        patterns = {}
    for key, item in patterns.items():
        res = analyze_pattern(key, item, filters, filter_errors)
        results.append(res)
        print("--- {0} ---".format(key))
        for line in res["lines"]:
            print(line)
        if "line" in res:
            print(res["line"])
        else:
            print("FAIL: {0}".format(res["reason"]))
    print()

    print_header("[3] 성능 분석 (평균/{0}회)".format(REPEAT))
    perf_rows = [(3, (measure_ms(SAMPLE_CROSS, SAMPLE_X) + measure_ms(SAMPLE_X, SAMPLE_CROSS)) / 2)]
    for n in sorted(filters):
        if n == 3:
            continue
        cross, xf = filters[n][CROSS], filters[n][X]
        perf_rows.append((n, (measure_ms(cross, xf) + measure_ms(xf, cross)) / 2))
    print_perf_table(perf_rows)

    print_header("[4] 결과 요약")
    total = len(results)
    passed = sum(1 for r in results if r["status"] == "PASS")
    failed = total - passed
    print("총 테스트: {0}개".format(total))
    print("통과: {0}개".format(passed))
    print("실패: {0}개".format(failed))
    if failed:
        print("\n실패 케이스:")
        for r in results:
            if r["status"] == "FAIL":
                print("- {0}: {1}".format(r["key"], r["reason"]))


# ---------------------------------------------------------------------------
# 진입점
# ---------------------------------------------------------------------------
def menu():
    print("=== Mini NPU Simulator ===\n")
    print("[모드 선택]\n")
    print("1. 사용자 입력 (3x3)")
    print("2. data.json 분석")
    while True:
        try:
            choice = input("선택: ").strip()
        except EOFError:
            print()
            return
        if choice == "1":
            print()
            run_mode1()
            return
        if choice == "2":
            print()
            run_mode2()
            return
        print("잘못된 선택입니다. 1 또는 2를 입력하세요.")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    try:
        menu()
    except (KeyboardInterrupt, EOFError):
        print("\n종료합니다.")
