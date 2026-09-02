# CLAUDE.md — Angband 자동 QA 파이프라인

## 프로젝트 목적

Angband(오픈소스 로그라이크)의 **아이템 수식자 × 몬스터 특성 상호작용 규칙**을
결정 테이블로 전수 생성하고, 실제 게임 엔진에 돌려서 문서화된 규칙과
어긋나는 지점을 찾아내는 자동 QA 파이프라인.

## 디렉토리 구조

```
qa/
  parser/parse_gamedata.py     item-parser: 게임데이터 -> 구조화 스펙(JSON)
  generator/
    reference_model.py         oracle: 문서 규칙만으로 만든 독립 참조 모델
    generate_cases.py          case-generator: 결정 테이블 전개
  runner/
    render_c_test.py           engine-adapter: 케이스 -> C 하네스 렌더링
    run_suite.sh               C 하네스를 엔진에 주입/빌드/실행
    smoke_e2e.py               채널 B: -mtest 자가 플레이 스모크
  analyzer/analyze.py          diff-analyzer + reporter
  pipeline.sh                  전 단계 오케스트레이터
scripts/setup-angband.sh       Angband 클론 + 빌드 (멱등)
specs/                         생성된 스펙 (gitignore)
test-cases/generated/          생성된 케이스/C코드/실행결과 (gitignore)
reports/                       리포트 산출물 (gitignore)
docs/domain-mapping.md         도메인 매핑 + 결정 테이블 정의
vendor/angband/                게임 소스 (gitignore, 스크립트로 취득)
```

## 실행

```sh
scripts/setup-angband.sh        # 최초 1회: 클론 + 빌드 + 게임데이터 설치
qa/pipeline.sh                  # 전체 회귀 (전 브랜드/슬레이)
qa/pipeline.sh --brands FIRE_3 --slays ORC_3   # 부분 실행
python3 qa/runner/smoke_e2e.py --angband-src vendor/angband --out reports/smoke-e2e.json
```

`qa/pipeline.sh`는 불일치가 있으면 **비정상 종료(exit 1)** 하므로 CI 게이트로
바로 쓸 수 있다.

## 설계상 반드시 지켜야 할 규칙

1. **참조 모델은 구현 코드를 보고 만들지 않는다.**
   `reference_model.py`는 `brand.txt`/`slay.txt`의 선언적 데이터와
   `docs/domain-mapping.md`에 정리된 규칙만으로 작성한다. `obj-slays.c`를
   그대로 옮기면 파이프라인이 자기 자신과 비교하는 꼴이 되어 무의미해진다.

2. **불일치는 "버그 확정"이 아니라 "검토 대상"으로 리포트한다.**
   엔진 버그 / 문서 규칙 오류 / 케이스 설정 오류 세 가능성이 항상 있다.

3. **하네스는 C에서 단정(assert)하지 않고 결과를 출력한다.**
   비교는 파이썬에서 한다. 그래야 실패 시 조건 행 전체가 리포트에 남는다.

4. **불가능한 조합은 생성하지 않는다.**
   취약 플래그가 없는 원소에 "취약함" 조건을 붙이는 식의 행은 pruning한다.
   과생성은 리포트 신호 대 잡음비를 떨어뜨린다.

5. **파이프라인을 바꿨으면 뮤테이션 테스트로 탐지력을 확인한다.**
   `vendor/angband/src/obj-slays.c`의 배율 계산을 일부러 훼손하고
   파이프라인이 이를 잡아내는지 검증한 뒤 되돌린다. 아래 "탐지력 검증" 참고.

## 두 개의 실행 채널

| 채널 | 도구 | 검증 대상 |
|---|---|---|
| A (정밀) | `src/tests/`에 생성 C 하네스 주입 → `make` → 실행 | 배율·선택된 수식자·동사 |
| B (e2e) | `angband -mtest` + stdin 커맨드 + `term-text` 파싱 | 게임 부팅/캐릭터 생성 스모크 |

채널 A가 주 회귀 채널. 채널 B는 엔진이 실제 구동 가능한지 확인하는 용도.

## 코드 스타일

- C 하네스: Angband 컨벤션(탭 들여쓰기, `snake_case`)을 따른다.
  생성 파일 상단에 "GENERATED FILE, DO NOT EDIT BY HAND" 배너를 유지한다.
- 파이썬: PEP 8, 표준 라이브러리만 사용(외부 의존성 추가 금지).
- 케이스 ID는 `case_%04d` 형식.

## 탐지력 검증 (mutation test)

파이프라인이 실제로 버그를 잡는지 확인하는 절차:

```sh
cp vendor/angband/src/obj-slays.c /tmp/obj-slays.c.orig
# get_monster_brand_multiplier()의 취약 배수 적용부를 훼손 (mult *= 2 -> mult *= 1)
(cd vendor/angband && make -j4)
qa/pipeline.sh          # 불일치가 보고되어야 정상 (exit 1)
cp /tmp/obj-slays.c.orig vendor/angband/src/obj-slays.c
(cd vendor/angband && make -j4)
qa/pipeline.sh          # 다시 0건이어야 정상 (exit 0)
```

이 절차로 검증된 실적: 배율 관측을 추가하기 전 4건 → 추가 후 28건 검출.
