# 도메인 매핑: 하스스톤 카드 프레임워크 → Angband

원 설계 문서는 "카드 × 카드 상호작용"을 결정 테이블로 검증하는 구조였다.
Angband에는 카드가 없으므로, **"규칙 수식자(rule modifier)를 가진 개체"** 라는
공통 추상을 기준으로 치환한다.

## 1. 개념 치환표

| 하스스톤 프레임워크 | Angband 대응 | 근거 파일 |
|---|---|---|
| 카드 | 무기에 붙은 브랜드(brand) / 슬레이(slay) | `lib/gamedata/brand.txt`, `slay.txt` |
| 카드 효과 발동 조건 | 몬스터 종족 플래그 (`EVIL`, `ORC`, `UNDEAD` …) | `list-mon-race-flags.h` |
| 효과 무효화 (침묵/면역) | 몬스터 저항 플래그 (`IM_FIRE`, `IM_ACID` …) | `brand.txt: resist-flag` |
| 효과 증폭 (콤보) | 몬스터 취약 플래그 (`HURT_FIRE`, `HURT_COLD`) | `brand.txt: vuln-flag` |
| 카드 우선순위 규칙 | 최대 배율 선택 규칙 (`best_mult`) | `obj-slays.c` |
| 게임 모드(정규/야생) | 전투 모드 (기본 / O-combat) | `birth_percent_damage` 옵션 |
| 공격 방식 | 근접(melee) / 원거리(range) | `improve_attack_modifier(range)` |

## 2. 검증 대상 (SUT)

핵심 함수는 `obj-slays.c`의 두 개다.

```c
void improve_attack_modifier(struct player *p, struct object *obj,
        const struct monster *mon, int *brand_used, int *slay_used,
        char *verb, bool range);
int  get_monster_brand_multiplier(const struct monster *mon,
        const struct brand *b, bool is_o_combat);
```

이 함수들이 "무기가 가진 브랜드/슬레이 목록"과 "몬스터의 플래그"를 받아
**최종 데미지 배율과 공격 동사(verb)** 를 결정한다. 즉 카드 상호작용 판정기에
정확히 대응한다.

## 3. 결정 테이블 조건 변수

| 변수 | 값 | 의미 |
|---|---|---|
| `brand` | 없음 / 10종 중 1 | 무기에 부여된 원소 브랜드 |
| `slay` | 없음 / 11종 중 1 | 무기에 부여된 종족 슬레이 |
| `mon_resists` | Y / N | 몬스터가 브랜드 원소에 면역인가 |
| `mon_vulnerable` | Y / N | 몬스터가 브랜드 원소에 특별 취약인가 |
| `mon_matches_slay` | Y / N | 몬스터가 슬레이 대상 종족인가 |
| `o_combat` | Y / N | O-combat(퍼센트 데미지) 모드인가 |
| `range` | Y / N | 원거리 공격인가 |

## 4. 기대 결과 (oracle)

기대값은 **구현 코드를 읽어서 만들지 않는다.** `brand.txt` / `slay.txt`의
선언적 데이터와 파일 주석에 명시된 규칙만으로 파이썬 참조 모델
(`qa/generator/reference_model.py`)을 독립 구현하고, 실제 엔진 실행 결과와
차분(differential) 비교한다.

문서화된 규칙:

1. 브랜드는 몬스터가 `resist-flag`를 가지면 **적용되지 않는다.**
2. 브랜드는 몬스터가 `vuln-flag`를 가지면 추가 데미지가 **2배**가 된다.
   - 기본 모드: `mult * 2`
   - O-combat: `2 * (mult - 10) + 10`  (배율의 "초과분"만 2배)
3. 슬레이는 몬스터가 대상 `race-flag`(또는 `base`)를 가질 때만 적용된다.
4. 브랜드와 슬레이가 동시에 적용 가능하면 **배율이 큰 쪽 하나만** 선택된다.
5. 동점이면 먼저 평가된 쪽이 유지된다 (브랜드가 슬레이보다 먼저 평가됨).
6. 선택된 수식자의 동사가 출력된다. 슬레이는 근접/원거리 동사가 다르고,
   브랜드는 원거리일 때 동사에 `s`가 붙는다.

이 6개 규칙과 엔진 실제 동작이 불일치하면 **버그 후보**로 리포트한다.
(엔진 버그일 수도, 데이터/문서 불일치일 수도 있으므로 리포트는 "불일치"로
분류하고 원인 판정은 사람이 검토한다.)

## 5. 실행 채널

| 채널 | 방식 | 용도 |
|---|---|---|
| A. 유닛 (정밀) | 생성된 C 테스트를 `src/tests/`에 넣고 `make tests` | 배율·동사 정확 검증 |
| B. e2e (자가 플레이) | `angband -mtest` + `key` 입력 스크립트 + `verbose 1`의 `term-text` 출력 파싱 | 캐릭터 생성~던전 진행 스모크 |

채널 A가 결정 테이블 회귀의 주 채널이고, 채널 B는 엔진이 실제로 구동 가능한
상태인지 확인하는 스모크 테스트다.
