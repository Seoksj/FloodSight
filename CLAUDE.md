# FloodSight — CLAUDE.md

## Project Overview
FloodSight is a real-time urban flood risk visualization web service.
Collects rainfall intensity, sewer capacity, terrain vulnerability (HAND index),
and flood history to calculate flood risk scores for flood-prone districts in Seoul,
visualized as colored polygons on an interactive Leaflet map.

## Tech Stack
- Frontend: React 18 + Vite + Tailwind CSS + Leaflet (react-leaflet)
- Backend: FastAPI + APScheduler + httpx
- Spatial: rasterio + GeoPandas + scipy (IDW interpolation)
- Deploy: GitHub Pages (frontend) + Render (backend, free tier 512MB RAM)

## Target Area
- Seoul Metropolitan City only
- District unit: 행정동 (dong) level, flood-prone areas only
- Selection criteria: MOIS (행안부) flood trace records 기반 반복 침수 동
- Non-Seoul polygons: already removed from GeoJSON

## Risk Score Formula
R = 0.40 × f_rainfall + 0.30 × f_HAND + 0.20 × f_imperv + 0.10 × f_history

where each feature is normalized to [0, 1]:
- f_rainfall = hourly_rainfall / sewer_design_capacity
- f_HAND     = 1 - (HAND_value / HAND_max)
- f_imperv   = impervious surface ratio (concrete + asphalt)
- f_history  = flood trace frequency score

Risk grades:
- Safe    : R < 0.30  → green
- Caution : 0.30 ≤ R < 0.50 → yellow
- Warning : 0.50 ≤ R < 0.70 → orange
- Danger  : R ≥ 0.70  → red

## Current Implementation Status

### Done ✅
- React frontend with Leaflet map
- Dark / light mode UI
- Forecast time toggle (now / +1h / +3h)
- GPS-based location risk panel with arc gauge + natural language reason
- GitHub Pages + Render deployment pipeline

### Dummy / Not Implemented ❌
- f_rainfall : random dummy (KMA API key needed)
- f_HAND     : not implemented (awaiting SRTM GeoTIFF from GIS team)
- f_imperv   : not implemented (awaiting land cover GeoTIFF from GIS team)
- f_history  : not implemented (awaiting flood trace shapefile from GIS team)
- Water level: not implemented (HRFCO API key needed)
- District polygons: partially complete, circle approximation for missing ones

## Team

### 석승준 (인공지능공학) — Backend lead, 나
- [x] FastAPI 백엔드 전체 구현 및 유지보수
- [x] 위험도 산출 로직 (risk_engine.py)
- [x] APScheduler 10분 주기 파이프라인
- [x] 프론트엔드 ↔ 백엔드 API 연동 디버깅 (GitHub Pages + Render 배포)
- [ ] 기상청 KMA API 실데이터 연동
- [ ] 홍수통제소 HRFCO API 실데이터 연동
- [ ] GIS 데이터 백엔드 ingestion 모듈 (HAND / 불투수율 / 침수흔적도)
- [ ] HAND 산출 스크립트 작성 후 박민수에게 전달
- [ ] 2022 강남역 이벤트 back-test

### 김형주 (데이터사이언스)
- [ ] 서울시 침수 취약 동 목록 선별 (행안부 침수흔적도 분석 기반)
- [ ] 2022 강남역 이벤트 강수 데이터 수집 → CSV 정리
- [ ] 가중치 w_i 근거 선행 연구 서치 → 문서 정리
- [ ] 성능 검증 리포트 작성

### 박민수 (공간정보공학)
- [ ] NASA SRTM DEM 서울시 clip (QGIS) → .tif 준비
- [ ] 석승준이 전달한 스크립트로 HAND 지수 산출 → .tif 준비
- [ ] 결과물 좌표계 EPSG:4326 확인 후 공유
- [ ] 국토부 토지피복도 서울시 범위 → .tif 또는 .shp 준비

### 이채원 (공간정보공학)
- [ ] 서울시 행정동 경계 GeoJSON → EPSG:4326 준비
- [ ] 행안부 침수흔적도 서울시 범위 → .shp 준비
- [ ] 지구명 / 행정구역명 오탈자 검수
- [ ] 발표자료 제작 (PPT)
- [ ] 발표 시나리오 점검
- [ ] README 스크린샷 삽입 및 문서 정리

## API Integration

### KMA Short-term Forecast API
- Base URL: http://apis.data.go.kr/1360000/VilageFcstInfoService_2.0/getVilageFcst
- Auth: serviceKey (query param)
- Key fields: PCP (precipitation mm/h), POP (probability %)
- Grid system: Lambert Conformal Conic (nx, ny) — use KMA grid converter
- Update cycle: 1 hour

### HRFCO Water Level API
- Base URL: http://www.hrfco.go.kr/openapi/obsDataList.do
- Auth: apiKey (query param)
- Key fields: wl (water level m), rf (rainfall mm)
- Update cycle: 10 minutes

### Dummy Fallback Rule
If API key is missing or request fails:
→ automatically switch to dummy data
→ log warning but do not crash
→ frontend must display "더미 데이터" indicator

## GIS Data Interface
Static files delivered by GIS team. All must be EPSG:4326.

| File | Format | Source | Status |
|---|---|---|---|
| Seoul dong boundary | GeoJSON | Overpass OSM | 🔄 partial |
| HAND index | GeoTIFF | NASA SRTM + richdem | ❌ pending |
| Impervious rate | GeoTIFF or CSV | 국토부 토지피복도 | ❌ pending |
| Flood trace | Shapefile (.shp) | 행안부 재해정보포털 | ❌ pending |

Ingestion rule:
- Load static files at server startup
- Serve as cached in-memory dict keyed by dong code
- Do NOT reload every 10 minutes (static data)

## Coordinate System Rules
- All output: EPSG:4326 (WGS84)
- KMA grid: Lambert → convert using KMA official grid formula
- GIS team input may be EPSG:5179 (Korean TM) → always reproject to 4326

## Validation Target
Reproduce 2022-08-08 Gangnam Station flood event:
- Sindang-dong, Sillim-dong → must reach Warning or Danger grade
- Forecast mode (+1h/+3h) → must show escalating risk before peak

## Constraints
- No GPU: rule-based model only, no ML training in scope
- Render free tier: 512MB RAM, cold start ~30s, no persistent disk
- Static GIS files must be committed to repo or loaded from URL at startup
- Always maintain dummy fallback for all external API calls