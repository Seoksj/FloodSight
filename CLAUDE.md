# FloodSight — 도시 침수 위험도 모니터링 서비스

## 서비스 컨셉
강수 강도 · 하수도 용량 · 지형 취약도를 결합해 도시 침수 위험을 실시간으로
지도에 표시하는 웹 서비스. 전국 36개 침수 취약 지구를 행정동 경계 폴리곤으로
시각화하고, 현재 / 1시간 후 / 3시간 후 예보를 제공한다.

## 기술 스택
- **Backend**  : FastAPI + APScheduler(10분 주기) + httpx
- **Frontend** : React + Vite + Tailwind CSS + Leaflet (react-leaflet)
- **ML**       : PyTorch — SAR + DEM + 텍스트 멀티모달 (FloodRiskModel)
- **공간처리** : rasterio, scipy IDW 보간
- **Python**   : 3.11 (venv: `flood-risk-demo/.venv2/`)  ← `.venv`는 broken
- **Node**     : `flood-risk-demo/frontend/node_modules/`

## 핵심 규칙
- 모든 응답과 주석은 **한국어**로
- API 키 없을 때 반드시 **더미 데이터로 fallback** 동작
- 위험도 산출 공식 (rule-based):
  `강수초과율×0.4 + 지형취약도×0.3 + 불투수율×0.2 + 침수이력×0.1`
- 등급: `0~0.3 안전(#22c55e)` / `0.3~0.5 주의(#eab308)` / `0.5~0.7 경보(#f97316)` / `0.7+ 위험(#ef4444)`
- ML 블렌딩: 체크포인트 없음 → rule 65% + ML 35% / 있음 → rule 30% + ML 70%
- 배수 상태 표기: 초과율(%) 아닌 절대량(mm 초과 / 여유 mm)

---

## 프로젝트 구조

```
FloodSight/
└── flood-risk-demo/
    ├── .venv2/                           # Python 3.11 가상환경 (사용 중)
    ├── backend/
    │   ├── main.py                       # FastAPI 앱 (포트 8000)
    │   ├── scheduler.py                  # 10분 주기 수집 + ML 추론
    │   ├── risk_engine.py                # rule-based 위험도 계산
    │   ├── predictor.py                  # ML 배치 추론 + blend()
    │   ├── cache.py                      # horizon별 GeoJSON 캐시
    │   ├── inference.py                  # /predict 단일 추론
    │   ├── preprocess.py
    │   ├── schemas.py
    │   ├── requirements.txt
    │   ├── checkpoints/                  # (비어있음) model.pt 여기에
    │   ├── clients/
    │   │   ├── hrfco.py                  # 한강홍수통제소 API (미연동)
    │   │   └── kma.py                    # 기상청 단기예보 API (미연동)
    │   ├── model/
    │   │   ├── __init__.py               # FloodRiskModel
    │   │   ├── encoders.py               # SAREncoder, DEMEncoder, TextEncoder
    │   │   ├── fusion.py                 # CrossAttentionFusion, TextSoftGating
    │   │   ├── decoder.py                # UNetDecoder
    │   │   └── loss.py                   # FocalDiceLoss
    │   └── spatial/
    │       ├── districts.py              # 36개 지구 메타 + GeoJSON 생성
    │       ├── district_boundaries.json  # 실제 행정동 경계 (28/36 수집)
    │       └── interpolate.py            # IDW 보간 (현재 미사용)
    ├── frontend/
    │   ├── src/
    │   │   ├── main.jsx                  # ThemeProvider 래핑
    │   │   ├── App.jsx                   # 레이아웃, horizon 상태, 통계
    │   │   ├── ThemeContext.jsx           # 다크/라이트 모드 (localStorage)
    │   │   ├── index.css                 # CSS 변수 기반 테마
    │   │   └── components/
    │   │       ├── MapView.jsx            # Leaflet + GeoJSON 폴리곤
    │   │       ├── LocationPanel.jsx      # 내 위치 위험도 (SVG 아크 게이지)
    │   │       ├── DistrictPanel.jsx      # 지구 목록 (등급/도시 필터)
    │   │       └── LegendBar.jsx          # 등급 범례
    │   ├── vite.config.js                # /api → localhost:8000 프록시
    │   └── package.json
    └── scripts/
        ├── fetch_boundaries.py           # Overpass API 행정동 경계 수집
        ├── create_test_data.py
        ├── test_model.py
        └── test_predict.py
```

---

## API 엔드포인트

| Method | Path | 설명 |
|--------|------|------|
| GET | `/health` | 서버 상태, 캐시 준비 여부, 지구 수 |
| GET | `/risk?horizon=current\|1h\|3h` | 전체 지구 GeoJSON FeatureCollection |
| GET | `/risk/point?lat=&lon=` | 특정 위경도 → 가장 가까운 지구 위험도 |
| GET | `/districts?city=&grade=` | 지구 목록 (경보↑ 우선 정렬) |
| POST | `/predict` | ML 단일 추론 (SAR + DEM + 강수 텍스트) |

---

## 구현 현황

### ✅ 완성된 것

**프론트엔드**
- 다크/라이트 모드 전환 (CSS `[data-theme]` 변수 + ThemeContext, localStorage 유지)
- 예보 시간대 토글 (현재 / 1시간 후 / 3시간 후) — 헤더에 통합
- 헤더 등급별 현황 통계 (위험 N / 경보 N / 주의 N / 안전 N)
- 내 위치 위험도 패널 (SVG 아크 게이지 + 2×2 수치 그리드)
- 지구 목록 패널 (등급 요약 카드 클릭 필터 + 도시 필터)
- 지도 클릭 팝업 (점수 게이지 바 + 수치 그리드)

**백엔드**
- horizon별 GeoJSON 캐시 (DataCache.update_all_horizons)
- `/risk?horizon=` 파라미터 지원
- 10분 스케줄러 (rule-based 선반영 → ML 후블렌딩)

**공간 데이터**
- 28/36개 실제 행정동 경계 폴리곤 (Overpass OSM admin_level=8)
- 나머지 8개는 radius=0.02도 원형 근사

### ❌ 더미 / 미구현

| 항목 | 현재 상태 | 필요한 것 |
|------|-----------|-----------|
| 강수량 | 10분 버킷 시드 난수 0~90mm/hr | 기상청 API 키 |
| 1h/3h 예보 강수량 | 현재값 × 트렌드 난수 | 동일 |
| 수위 데이터 | 없음 | HRFCO API 키 |
| ML 가중치 | 랜덤 (checkpoints/ 비어있음) | SAR 데이터 + GPU 학습 |
| 불투수면적률 | 수동 추정값 하드코딩 | 환경부 DB |
| 침수이력 지수 | 수동 추정값 하드코딩 | 침수흔적도 GIS |
| 지형 취약도 | 수동 추정값 하드코딩 | SRTM DEM → HAND |
| SAR 입력 | 강수량 수식 변환 (가짜) | Sentinel-1 실데이터 |
| DEM 입력 | topo_depression 기반 텐서 (가짜) | 실제 DEM 래스터 |

### 미수집 행정동 경계 8곳
`천호동(강동구)`, `봉천동(관악구)`, `부평2동(부평구)`,
`온천4동(동래구)`, `봉명동(유성구)`, `인계동(팔달구)`,
`금광동(중원구)`, `중동(원미구)`

---

## 로컬 실행

```bash
# 백엔드 (포트 8000)
cd flood-risk-demo/backend
../.venv2/bin/uvicorn main:app --host 0.0.0.0 --port 8000

# 프론트엔드 (포트 5173)
cd flood-risk-demo/frontend
node_modules/.bin/vite --port 5173

# 행정동 경계 재수집 (Overpass API, 약 2분)
cd flood-risk-demo
.venv2/bin/python scripts/fetch_boundaries.py
```

---

## 팀 역할 분담

| 역할 | 담당 작업 |
|------|-----------|
| **공간정보공학 A** | HAND 지형 취약도, 침수흔적도, 불투수율 실데이터, 행정동 경계 완성, `spatial/hand.py` |
| **공간정보공학 B** | KMA/HRFCO API 실연동, Docker 배포, Nginx, 지도 UX 개선 |
| **데이터사이언스** | EDA, rule-based 가중치 튜닝, ML 학습 데이터셋 구성, 평가 지표 |
| **인공지능공학**  | FloodRiskModel 개선, Sentinel-1 SAR 전처리, 모델 학습, checkpoints/model.pt |

---

## 주요 설계 결정 (변경 시 팀 합의 필요)

- **행정동 경계 소스**: Overpass OSM admin_level=8. 미수집 시 원형 근사
- **위험도 가중치**: 강수초과율 0.4 / 지형 0.3 / 불투수 0.2 / 침수이력 0.1
- **더미 강수 시드**: `int(time.time() / 600)` — 10분마다 갱신, 같은 시간대 재현 가능
- **ML 블렌딩**: `predictor.py:blend()` — 체크포인트 유무로 자동 전환
- **테마 시스템**: CSS `[data-theme="light/dark"]` 변수 선언, JS override 없음
