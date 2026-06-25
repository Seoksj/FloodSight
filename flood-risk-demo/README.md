# Flood Risk Demo

SAR + DEM + 강수 텍스트를 입력받아 홍수 위험 확률 지도를 예측하는 멀티모달 AI 시스템.

## 구조

```
flood-risk-demo/
├── backend/
│   ├── main.py           # FastAPI 앱 (POST /predict, GET /health)
│   ├── inference.py      # 추론 로직 + dummy 폴백
│   ├── preprocess.py     # GeoTIFF 파싱 + 정규화
│   ├── schemas.py        # Pydantic 스키마
│   ├── model/
│   │   ├── __init__.py   # FloodRiskModel 조립
│   │   ├── encoders.py   # SAREncoder, DEMEncoder, TextEncoder
│   │   ├── fusion.py     # CrossAttentionFusion, TextSoftGating
│   │   ├── decoder.py    # UNetDecoder
│   │   └── loss.py       # FocalDiceLoss
│   └── requirements.txt
├── frontend/
│   ├── src/
│   │   ├── App.jsx
│   │   └── components/
│   │       ├── InputPanel.jsx   # 파일 업로드 + 텍스트 입력
│   │       ├── MapView.jsx      # Canvas 히트맵
│   │       └── ResultPanel.jsx  # 위험 등급 배지 + 통계
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
└── scripts/
    ├── create_test_data.py  # 테스트용 GeoTIFF 생성
    ├── test_predict.py      # /predict 엔드포인트 E2E 테스트
    └── test_model.py        # 모델 forward pass shape 검증
```

## 빠른 시작

### 1. Backend 설정

```bash
cd flood-risk-demo/backend

# 가상환경 생성 (권장)
python -m venv .venv && source .venv/bin/activate

# 패키지 설치
pip install -r requirements.txt

# 서버 실행
uvicorn main:app --reload --port 8000
```

체크포인트(`checkpoints/model.pt`)가 없으면 자동으로 **dummy predictor**로 동작합니다.

### 2. Frontend 설정

```bash
cd flood-risk-demo/frontend

npm install
npm run dev    # http://localhost:5173
```

### 3. 검증

```bash
# [1] 테스트 GeoTIFF 생성
python scripts/create_test_data.py

# [2] /predict 엔드포인트 테스트 (backend 실행 중 필요)
python scripts/test_predict.py

# [3] 모델 forward pass shape 검증
cd backend && python ../scripts/test_model.py
```

## API

### GET /health
```json
{
  "status": "ok",
  "model_loaded": false,
  "checkpoint_path": "checkpoints/model.pt",
  "checkpoint_exists": false
}
```

### POST /predict
**Request** (multipart/form-data):
- `sar`: SAR GeoTIFF 파일
- `dem`: DEM GeoTIFF 파일
- `precipitation`: 강수 정보 텍스트

**Response**:
```json
{
  "prob_map": [[0.12, 0.34, ...], ...],
  "risk_level": "HIGH",
  "stats": {
    "max_prob": 0.923,
    "mean_prob": 0.341,
    "high_risk_pct": 28.5
  }
}
```

## 모델 아키텍처

```
SAR (B,T,C,H,W) → SAREncoder (ConvLSTM) ──┐
DEM (B,C,H,W)   → DEMEncoder (ResNet stem)─┤→ CrossAttention → TextSoftGating → UNetDecoder → (B,1,H,W)
Text (B,L)       → TextEncoder (RoBERTa) ──┘
```

- **SAREncoder**: ConvLSTM 기반 시계열 처리, 3D Swin으로 교체 가능한 인터페이스
- **DEMEncoder**: ResNet-18 stem, 고도/경사/향/곡률/유량 5채널
- **TextEncoder**: klue/roberta-base (frozen), transformers 없으면 경량 fallback
- **FocalDiceLoss**: α=0.25, γ=2.0, dice_weight=0.5

## 환경 변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `MODEL_CHECKPOINT` | `checkpoints/model.pt` | 체크포인트 경로 |
