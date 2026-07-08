# FloodSight 🌧️

**서울·인천 행정동 단위 실시간 침수 위험 시각화 서비스**

기상청 실황 강수량, 지형 취약도(HAND), 불투수율, 침수 이력을 결합해  
서울·인천 580개 행정동의 침수 위험도를 4단계로 실시간 표시합니다.

---

## 주요 기능

- **실시간 위험 지도** — 행정동 경계 폴리곤에 안전/주의/경보/위험 4색 표시
- **10분 자동 갱신** — 기상청 초단기실황 + 한강홍수통제소 수위 데이터 반영
- **동별 격자 강수** — 서울·인천 74개 KMA 격자를 개별 조회, 동마다 다른 강수량 적용
- **예보 시나리오** — 현재 / +1시간 / +3시간 전환
- **상세 패널** — 강수량, 하수도 용량 대비 진행 바, 예측 바 차트, 자연어 위험 근거
- **내 위치** — GPS 기반 현재 위치 행정동 위험도 즉시 확인
- **다크모드** 지원

## 위험도 산출 공식

```
R = 0.40 × f_rainfall + 0.30 × f_HAND + 0.20 × f_imperv + 0.10 × f_history
```

| 항목 | 의미 | 데이터 출처 |
|------|------|-------------|
| f_rainfall (40%) | 강수량 / 하수도 설계 용량 | 기상청 초단기실황 API |
| f_HAND (30%) | 지형 저지대 취약도 | NASA SRTM DEM → HAND 지수 |
| f_imperv (20%) | 불투수면(콘크리트·아스팔트) 비율 | 환경부 토지피복도 |
| f_history (10%) | 과거 침수 발생 빈도 | 행안부 침수흔적도 |

| 등급 | 점수 | 색상 |
|------|------|------|
| 안전 | R < 0.45 | 🟢 초록 |
| 주의 | 0.45 ≤ R < 0.60 | 🟡 노랑 |
| 경보 | 0.60 ≤ R < 0.75 | 🟠 주황 |
| 위험 | R ≥ 0.75 | 🔴 빨강 |

> 강수 5mm/hr 미만이면 최대 '주의'로 제한 (오탐 방지)  
> 한강 수위가 경보 수위 50% 초과 시 위험도 추가 보정 (최대 +0.10)

## 검증

2022년 8월 8일 강남역 침수 이벤트 back-test 결과:

| 동 | 21시 (75.5mm/hr) | 22시 (92.5mm/hr) |
|----|-----------------|-----------------|
| 역삼1동 | 🔶 경보 | 🚨 위험 |
| 서초4동 | 🔶 경보 | 🚨 위험 |
| 신림동 | 🚨 위험 | 🚨 위험 |
| 대림2동 | 🚨 위험 | 🚨 위험 |

---

## 기술 스택

| 구분 | 기술 |
|------|------|
| Frontend | React 18, Vite, Tailwind CSS, react-leaflet, Mapbox |
| Backend | Python FastAPI, APScheduler, httpx |
| 공간 분석 | rasterio, GeoPandas, scipy (HAND 지수 계산) |
| 외부 API | 기상청 초단기실황·단기예보, 한강홍수통제소 HRFCO |
| 배포 | GitHub Pages (Frontend) + Render (Backend) |

---

## 로컬 실행

> Python 3.10+, Node.js 18+ 필요

```bash
git clone https://github.com/Seoksj/FloodSight.git
cd FloodSight
```

### 백엔드

```bash
cd flood-risk-demo/backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8000
```

`flood-risk-demo/backend/.env` (선택 — 없으면 더미 데이터로 자동 동작):

```
KMA_API_KEY=기상청_API_키
HRFCO_API_KEY=홍수통제소_API_키
```

### 프론트엔드

```bash
cd flood-risk-demo/frontend
npm install
npm run dev   # http://localhost:5173
```

`flood-risk-demo/frontend/.env.local`:

```
VITE_MAPBOX_TOKEN=Mapbox_퍼블릭_토큰
```

| 주소 | 내용 |
|------|------|
| http://localhost:5173 | 프론트엔드 |
| http://localhost:8000/docs | API 문서 (Swagger) |
| http://localhost:8000/risk | 전체 동 위험도 GeoJSON |

---

## 배포 구조

```
GitHub main 브랜치 push
  ├── GitHub Actions → Vite 빌드 → GitHub Pages 배포 (frontend)
  └── Render          → uvicorn 재시작              (backend)
```

Render 환경변수 설정 필요: `KMA_API_KEY`, `HRFCO_API_KEY`  
GitHub Secrets 설정 필요: `VITE_API_BASE_URL`, `VITE_MAPBOX_TOKEN`

---

## 팀

| 이름 | 전공 | 담당 |
|------|------|------|
| 석승준 | 인공지능공학 | 백엔드, 위험도 엔진, API 연동, 배포 |
| 김형주 | 데이터사이언스 | 취약 동 선별, 강수 데이터 수집, 가중치 분석 |
| 박민수 | 공간정보공학 | DEM 처리, HAND 지수 산출, 토지피복도 |
| 이채원 | 공간정보공학 | 행정동 경계 GeoJSON, 침수흔적도, 발표자료 |
