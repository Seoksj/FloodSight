"""
전국 주요 침수 취약 지역 데이터 + 도시 침수 위험도 GeoJSON 생성.

데이터 출처 (실제 연동 시):
  - 행정안전부 침수흔적도 (data.go.kr)
  - 국토부 VWORLD 읍면동 경계
  - 환경부 불투수면적률 DB

현재: 36개 주요 취약 지구 하드코딩 더미.
"""

import json
import math
import os
import random
import time
from typing import List, Dict, Any, Tuple

from risk_engine import compute_urban_flood_risk, score_to_grade, generate_urban_reason

# 실제 행정동 경계 (hangjeongdong_서울특별시.geojson 에서 변환)
_BOUNDARIES_PATH = os.path.join(os.path.dirname(__file__), "district_boundaries.json")
_BOUNDARIES: Dict[str, Dict] = {}   # district_id → {geometry, dong, gu, adm_cd}


def _load_boundaries():
    global _BOUNDARIES
    if os.path.exists(_BOUNDARIES_PATH):
        try:
            with open(_BOUNDARIES_PATH, encoding="utf-8") as f:
                _BOUNDARIES = json.load(f)
        except Exception:
            _BOUNDARIES = {}


_load_boundaries()

# ──────────────────────────────────────────────────────────────
# 정적 취약지 메타데이터
#   drainage_capacity : 하수도 설계 용량 (mm/hr)
#   impervious_ratio  : 불투수율 0~1
#   topo_depression   : 지형 취약도 0~1 (1=극저지대/분지)
#   flood_history     : 침수 이력 지수 0~1
# ──────────────────────────────────────────────────────────────
DISTRICTS: List[Dict[str, Any]] = [
    # 출처: 서울시_침수취약동_종합점수.csv 상위 100개 동
    # drainage_capacity: 서울시 방재성능목표 (중점관리지역 110mm, 전체 100mm)
    # impervious_ratio : 토지피복도_서울시.tif
    # topo_depression  : DEM_서울시.tif → HAND (100개 동 min-max 정규화)
    # flood_history    : 종합취약도점수 (면적점수×0.5 + 빈도점수×0.5)
    {"id":"SL001","name":"대림2동","gu":"영등포구","city":"서울",
     "lat":37.4896,"lon":126.9006,"drainage_capacity":100.0,"impervious_ratio":0.799,
     "topo_depression":0.986,"flood_history":0.547},
    {"id":"SL002","name":"우이동","gu":"강북구","city":"서울",
     "lat":37.6604,"lon":127.0003,"drainage_capacity":100.0,"impervious_ratio":0.107,
     "topo_depression":0.076,"flood_history":0.524},
    {"id":"SL003","name":"인수동","gu":"강북구","city":"서울",
     "lat":37.6376,"lon":127.0040,"drainage_capacity":100.0,"impervious_ratio":0.32,
     "topo_depression":0.401,"flood_history":0.491},
    {"id":"SL004","name":"삼양동","gu":"강북구","city":"서울",
     "lat":37.6238,"lon":127.0147,"drainage_capacity":100.0,"impervious_ratio":0.63,
     "topo_depression":0.696,"flood_history":0.475},
    {"id":"SL005","name":"수유1동","gu":"강북구","city":"서울",
     "lat":37.6299,"lon":127.0088,"drainage_capacity":100.0,"impervious_ratio":0.344,
     "topo_depression":0.488,"flood_history":0.47},
    {"id":"SL006","name":"정릉4동","gu":"성북구","city":"서울",
     "lat":37.6235,"lon":126.9952,"drainage_capacity":100.0,"impervious_ratio":0.188,
     "topo_depression":0.0,"flood_history":0.469},
    {"id":"SL007","name":"대림1동","gu":"영등포구","city":"서울",
     "lat":37.4938,"lon":126.9053,"drainage_capacity":100.0,"impervious_ratio":0.785,
     "topo_depression":0.973,"flood_history":0.303},
    {"id":"SL008","name":"상계1동","gu":"노원구","city":"서울",
     "lat":37.6833,"lon":127.0653,"drainage_capacity":100.0,"impervious_ratio":0.222,
     "topo_depression":0.354,"flood_history":0.296},
    {"id":"SL009","name":"상계3·4동","gu":"노원구","city":"서울",
     "lat":37.6751,"lon":127.0833,"drainage_capacity":100.0,"impervious_ratio":0.187,
     "topo_depression":0.294,"flood_history":0.287},
    {"id":"SL010","name":"사당1동","gu":"동작구","city":"서울",
     "lat":37.4797,"lon":126.9774,"drainage_capacity":100.0,"impervious_ratio":0.789,
     "topo_depression":0.942,"flood_history":0.282},
    {"id":"SL011","name":"신길6동","gu":"영등포구","city":"서울",
     "lat":37.4992,"lon":126.9135,"drainage_capacity":100.0,"impervious_ratio":0.756,
     "topo_depression":0.957,"flood_history":0.246},
    {"id":"SL012","name":"신길5동","gu":"영등포구","city":"서울",
     "lat":37.5011,"lon":126.9056,"drainage_capacity":100.0,"impervious_ratio":0.718,
     "topo_depression":0.975,"flood_history":0.236},
    {"id":"SL013","name":"신사동","gu":"관악구","city":"서울",
     "lat":37.4856,"lon":126.9188,"drainage_capacity":100.0,"impervious_ratio":0.788,
     "topo_depression":0.954,"flood_history":0.232},
    {"id":"SL014","name":"상도4동","gu":"동작구","city":"서울",
     "lat":37.4974,"lon":126.9408,"drainage_capacity":100.0,"impervious_ratio":0.616,
     "topo_depression":0.755,"flood_history":0.166},
    {"id":"SL015","name":"신대방1동","gu":"동작구","city":"서울",
     "lat":37.4899,"lon":126.9107,"drainage_capacity":100.0,"impervious_ratio":0.659,
     "topo_depression":0.945,"flood_history":0.152},
    {"id":"SL016","name":"사당2동","gu":"동작구","city":"서울",
     "lat":37.4982,"lon":126.9752,"drainage_capacity":100.0,"impervious_ratio":0.429,
     "topo_depression":0.874,"flood_history":0.144},
    {"id":"SL017","name":"대림3동","gu":"영등포구","city":"서울",
     "lat":37.4999,"lon":126.8973,"drainage_capacity":100.0,"impervious_ratio":0.775,
     "topo_depression":0.99,"flood_history":0.142},
    {"id":"SL018","name":"상도3동","gu":"동작구","city":"서울",
     "lat":37.4972,"lon":126.9334,"drainage_capacity":100.0,"impervious_ratio":0.674,
     "topo_depression":0.789,"flood_history":0.137},
    {"id":"SL019","name":"방배2동","gu":"서초구","city":"서울",
     "lat":37.4730,"lon":126.9885,"drainage_capacity":100.0,"impervious_ratio":0.455,
     "topo_depression":0.769,"flood_history":0.133},
    {"id":"SL020","name":"신길3동","gu":"영등포구","city":"서울",
     "lat":37.5064,"lon":126.9059,"drainage_capacity":100.0,"impervious_ratio":0.778,
     "topo_depression":0.972,"flood_history":0.131},
    {"id":"SL021","name":"대방동","gu":"동작구","city":"서울",
     "lat":37.5071,"lon":126.9280,"drainage_capacity":100.0,"impervious_ratio":0.651,
     "topo_depression":0.916,"flood_history":0.126},
    {"id":"SL022","name":"문래동","gu":"영등포구","city":"서울",
     "lat":37.5164,"lon":126.8915,"drainage_capacity":100.0,"impervious_ratio":0.748,
     "topo_depression":0.996,"flood_history":0.124},
    {"id":"SL023","name":"신림동","gu":"관악구","city":"서울",
     "lat":37.4869,"lon":126.9276,"drainage_capacity":100.0,"impervious_ratio":0.772,
     "topo_depression":0.945,"flood_history":0.115},
    {"id":"SL024","name":"서초2동","gu":"서초구","city":"서울",
     "lat":37.4888,"lon":127.0279,"drainage_capacity":100.0,"impervious_ratio":0.692,
     "topo_depression":0.931,"flood_history":0.112},
    {"id":"SL025","name":"조원동","gu":"관악구","city":"서울",
     "lat":37.4829,"lon":126.9075,"drainage_capacity":100.0,"impervious_ratio":0.767,
     "topo_depression":0.963,"flood_history":0.111},
    {"id":"SL026","name":"신원동","gu":"관악구","city":"서울",
     "lat":37.4793,"lon":126.9267,"drainage_capacity":100.0,"impervious_ratio":0.647,
     "topo_depression":0.85,"flood_history":0.108},
    {"id":"SL027","name":"미성동","gu":"관악구","city":"서울",
     "lat":37.4759,"lon":126.9154,"drainage_capacity":100.0,"impervious_ratio":0.521,
     "topo_depression":0.835,"flood_history":0.104},
    {"id":"SL028","name":"구로5동","gu":"구로구","city":"서울",
     "lat":37.5020,"lon":126.8885,"drainage_capacity":100.0,"impervious_ratio":0.76,
     "topo_depression":0.989,"flood_history":0.101},
    {"id":"SL029","name":"양재2동","gu":"서초구","city":"서울",
     "lat":37.4511,"lon":127.0459,"drainage_capacity":100.0,"impervious_ratio":0.265,
     "topo_depression":0.567,"flood_history":0.097},
    {"id":"SL030","name":"개봉1동","gu":"구로구","city":"서울",
     "lat":37.4999,"lon":126.8499,"drainage_capacity":100.0,"impervious_ratio":0.656,
     "topo_depression":0.96,"flood_history":0.088},
    {"id":"SL031","name":"보라매동","gu":"관악구","city":"서울",
     "lat":37.4904,"lon":126.9326,"drainage_capacity":100.0,"impervious_ratio":0.666,
     "topo_depression":0.837,"flood_history":0.085},
    {"id":"SL032","name":"은천동","gu":"관악구","city":"서울",
     "lat":37.4868,"lon":126.9422,"drainage_capacity":100.0,"impervious_ratio":0.769,
     "topo_depression":0.822,"flood_history":0.082},
    {"id":"SL033","name":"구로2동","gu":"구로구","city":"서울",
     "lat":37.4975,"lon":126.8795,"drainage_capacity":100.0,"impervious_ratio":0.741,
     "topo_depression":0.982,"flood_history":0.081},
    {"id":"SL034","name":"신길1동","gu":"영등포구","city":"서울",
     "lat":37.5123,"lon":126.9195,"drainage_capacity":100.0,"impervious_ratio":0.731,
     "topo_depression":0.955,"flood_history":0.079},
    {"id":"SL035","name":"서초4동","gu":"서초구","city":"서울",
     "lat":37.4990,"lon":127.0200,"drainage_capacity":110.0,"impervious_ratio":0.752,
     "topo_depression":0.949,"flood_history":0.078},  # 중점관리지역 110mm
    {"id":"SL036","name":"응암3동","gu":"은평구","city":"서울",
     "lat":37.5887,"lon":126.9177,"drainage_capacity":100.0,"impervious_ratio":0.77,
     "topo_depression":0.932,"flood_history":0.078},
    {"id":"SL037","name":"영등포동","gu":"영등포구","city":"서울",
     "lat":37.5215,"lon":126.9078,"drainage_capacity":100.0,"impervious_ratio":0.775,
     "topo_depression":0.993,"flood_history":0.077},
    {"id":"SL038","name":"상도2동","gu":"동작구","city":"서울",
     "lat":37.5037,"lon":126.9421,"drainage_capacity":100.0,"impervious_ratio":0.736,
     "topo_depression":0.836,"flood_history":0.073},
    {"id":"SL039","name":"서초3동","gu":"서초구","city":"서울",
     "lat":37.4854,"lon":127.0096,"drainage_capacity":110.0,"impervious_ratio":0.577,
     "topo_depression":0.792,"flood_history":0.069},  # 중점관리지역 110mm
    {"id":"SL040","name":"노량진2동","gu":"동작구","city":"서울",
     "lat":37.5109,"lon":126.9380,"drainage_capacity":100.0,"impervious_ratio":0.729,
     "topo_depression":0.942,"flood_history":0.067},
    {"id":"SL041","name":"도림동","gu":"영등포구","city":"서울",
     "lat":37.5093,"lon":126.9012,"drainage_capacity":100.0,"impervious_ratio":0.789,
     "topo_depression":0.973,"flood_history":0.066},
    {"id":"SL042","name":"삼성동","gu":"관악구","city":"서울",
     "lat":37.4607,"lon":126.9301,"drainage_capacity":100.0,"impervious_ratio":0.223,
     "topo_depression":0.395,"flood_history":0.066},
    {"id":"SL043","name":"신대방2동","gu":"동작구","city":"서울",
     "lat":37.4943,"lon":126.9215,"drainage_capacity":100.0,"impervious_ratio":0.651,
     "topo_depression":0.93,"flood_history":0.064},
    {"id":"SL044","name":"상도1동","gu":"동작구","city":"서울",
     "lat":37.4983,"lon":126.9535,"drainage_capacity":100.0,"impervious_ratio":0.67,
     "topo_depression":0.673,"flood_history":0.063},
    {"id":"SL045","name":"방배본동","gu":"서초구","city":"서울",
     "lat":37.4949,"lon":126.9878,"drainage_capacity":100.0,"impervious_ratio":0.773,
     "topo_depression":0.953,"flood_history":0.062},
    {"id":"SL046","name":"사당4동","gu":"동작구","city":"서울",
     "lat":37.4806,"lon":126.9708,"drainage_capacity":100.0,"impervious_ratio":0.628,
     "topo_depression":0.868,"flood_history":0.061},
    {"id":"SL047","name":"시흥1동","gu":"금천구","city":"서울",
     "lat":37.4529,"lon":126.9001,"drainage_capacity":100.0,"impervious_ratio":0.728,
     "topo_depression":0.942,"flood_history":0.06},
    {"id":"SL048","name":"흑석동","gu":"동작구","city":"서울",
     "lat":37.5063,"lon":126.9638,"drainage_capacity":100.0,"impervious_ratio":0.565,
     "topo_depression":0.878,"flood_history":0.059},
    {"id":"SL049","name":"불광1동","gu":"은평구","city":"서울",
     "lat":37.6173,"lon":126.9393,"drainage_capacity":100.0,"impervious_ratio":0.362,
     "topo_depression":0.365,"flood_history":0.059},
    {"id":"SL050","name":"논현1동","gu":"강남구","city":"서울",
     "lat":37.5119,"lon":127.0265,"drainage_capacity":110.0,"impervious_ratio":0.784,
     "topo_depression":0.896,"flood_history":0.057},  # 중점관리지역 110mm
    {"id":"SL051","name":"독산1동","gu":"금천구","city":"서울",
     "lat":37.4642,"lon":126.8927,"drainage_capacity":100.0,"impervious_ratio":0.703,
     "topo_depression":0.965,"flood_history":0.052},
    {"id":"SL052","name":"개봉2동","gu":"구로구","city":"서울",
     "lat":37.4927,"lon":126.8564,"drainage_capacity":100.0,"impervious_ratio":0.69,
     "topo_depression":0.975,"flood_history":0.052},
    {"id":"SL053","name":"내곡동","gu":"서초구","city":"서울",
     "lat":37.4565,"lon":127.0705,"drainage_capacity":100.0,"impervious_ratio":0.146,
     "topo_depression":0.598,"flood_history":0.051},
    {"id":"SL054","name":"반포1동","gu":"서초구","city":"서울",
     "lat":37.5055,"lon":127.0166,"drainage_capacity":100.0,"impervious_ratio":0.753,
     "topo_depression":0.956,"flood_history":0.049},
    {"id":"SL055","name":"사당3동","gu":"동작구","city":"서울",
     "lat":37.4888,"lon":126.9709,"drainage_capacity":100.0,"impervious_ratio":0.536,
     "topo_depression":0.804,"flood_history":0.048},
    {"id":"SL056","name":"개봉3동","gu":"구로구","city":"서울",
     "lat":37.4868,"lon":126.8524,"drainage_capacity":100.0,"impervious_ratio":0.506,
     "topo_depression":0.938,"flood_history":0.045},
    {"id":"SL057","name":"청룡동","gu":"관악구","city":"서울",
     "lat":37.4780,"lon":126.9459,"drainage_capacity":100.0,"impervious_ratio":0.58,
     "topo_depression":0.768,"flood_history":0.044},
    {"id":"SL058","name":"역삼1동","gu":"강남구","city":"서울",
     "lat":37.5009,"lon":127.0355,"drainage_capacity":110.0,"impervious_ratio":0.805,
     "topo_depression":0.886,"flood_history":0.044},  # 중점관리지역 110mm
    {"id":"SL059","name":"영등포본동","gu":"영등포구","city":"서울",
     "lat":37.5137,"lon":126.9097,"drainage_capacity":100.0,"impervious_ratio":0.761,
     "topo_depression":0.963,"flood_history":0.044},
    {"id":"SL060","name":"서초1동","gu":"서초구","city":"서울",
     "lat":37.4870,"lon":127.0201,"drainage_capacity":100.0,"impervious_ratio":0.666,
     "topo_depression":0.886,"flood_history":0.044},
    {"id":"SL061","name":"난곡동","gu":"관악구","city":"서울",
     "lat":37.4705,"lon":126.9210,"drainage_capacity":100.0,"impervious_ratio":0.54,
     "topo_depression":0.753,"flood_history":0.043},
    {"id":"SL062","name":"방배1동","gu":"서초구","city":"서울",
     "lat":37.4849,"lon":126.9963,"drainage_capacity":100.0,"impervious_ratio":0.66,
     "topo_depression":0.868,"flood_history":0.043},
    {"id":"SL063","name":"사당5동","gu":"동작구","city":"서울",
     "lat":37.4858,"lon":126.9650,"drainage_capacity":100.0,"impervious_ratio":0.506,
     "topo_depression":0.793,"flood_history":0.041},
    {"id":"SL064","name":"방배4동","gu":"서초구","city":"서울",
     "lat":37.4898,"lon":126.9910,"drainage_capacity":100.0,"impervious_ratio":0.691,
     "topo_depression":0.917,"flood_history":0.041},
    {"id":"SL065","name":"세곡동","gu":"강남구","city":"서울",
     "lat":37.4711,"lon":127.1043,"drainage_capacity":100.0,"impervious_ratio":0.389,
     "topo_depression":0.886,"flood_history":0.038},
    {"id":"SL066","name":"가산동","gu":"금천구","city":"서울",
     "lat":37.4768,"lon":126.8843,"drainage_capacity":100.0,"impervious_ratio":0.782,
     "topo_depression":0.991,"flood_history":0.037},
    {"id":"SL067","name":"갈현1동","gu":"은평구","city":"서울",
     "lat":37.6254,"lon":126.9149,"drainage_capacity":100.0,"impervious_ratio":0.574,
     "topo_depression":0.759,"flood_history":0.037},
    {"id":"SL068","name":"구로4동","gu":"구로구","city":"서울",
     "lat":37.4915,"lon":126.8902,"drainage_capacity":100.0,"impervious_ratio":0.783,
     "topo_depression":0.982,"flood_history":0.036},
    {"id":"SL069","name":"불광2동","gu":"은평구","city":"서울",
     "lat":37.6244,"lon":126.9287,"drainage_capacity":100.0,"impervious_ratio":0.532,
     "topo_depression":0.74,"flood_history":0.035},
    {"id":"SL070","name":"마천1동","gu":"송파구","city":"서울",
     "lat":37.4948,"lon":127.1557,"drainage_capacity":100.0,"impervious_ratio":0.753,
     "topo_depression":0.83,"flood_history":0.035},
    {"id":"SL071","name":"방이2동","gu":"송파구","city":"서울",
     "lat":37.5133,"lon":127.1138,"drainage_capacity":100.0,"impervious_ratio":0.793,
     "topo_depression":0.964,"flood_history":0.035},
    {"id":"SL072","name":"낙성대동","gu":"관악구","city":"서울",
     "lat":37.4672,"lon":126.9600,"drainage_capacity":100.0,"impervious_ratio":0.308,
     "topo_depression":0.429,"flood_history":0.034},
    {"id":"SL073","name":"독산2동","gu":"금천구","city":"서울",
     "lat":37.4638,"lon":126.9026,"drainage_capacity":100.0,"impervious_ratio":0.717,
     "topo_depression":0.864,"flood_history":0.032},
    {"id":"SL074","name":"양재1동","gu":"서초구","city":"서울",
     "lat":37.4696,"lon":127.0225,"drainage_capacity":100.0,"impervious_ratio":0.34,
     "topo_depression":0.772,"flood_history":0.031},
    {"id":"SL075","name":"독산3동","gu":"금천구","city":"서울",
     "lat":37.4759,"lon":126.9046,"drainage_capacity":100.0,"impervious_ratio":0.69,
     "topo_depression":0.889,"flood_history":0.029},
    {"id":"SL076","name":"구로3동","gu":"구로구","city":"서울",
     "lat":37.4849,"lon":126.8950,"drainage_capacity":100.0,"impervious_ratio":0.778,
     "topo_depression":0.966,"flood_history":0.029},
    {"id":"SL077","name":"석촌동","gu":"송파구","city":"서울",
     "lat":37.5027,"lon":127.1025,"drainage_capacity":100.0,"impervious_ratio":0.777,
     "topo_depression":0.977,"flood_history":0.029},
    {"id":"SL078","name":"시흥5동","gu":"금천구","city":"서울",
     "lat":37.4487,"lon":126.9124,"drainage_capacity":100.0,"impervious_ratio":0.32,
     "topo_depression":0.622,"flood_history":0.029},
    {"id":"SL079","name":"남현동","gu":"관악구","city":"서울",
     "lat":37.4625,"lon":126.9766,"drainage_capacity":100.0,"impervious_ratio":0.208,
     "topo_depression":0.321,"flood_history":0.028},
    {"id":"SL080","name":"당산1동","gu":"영등포구","city":"서울",
     "lat":37.5239,"lon":126.8969,"drainage_capacity":100.0,"impervious_ratio":0.793,
     "topo_depression":0.998,"flood_history":0.027},
    {"id":"SL081","name":"시흥4동","gu":"금천구","city":"서울",
     "lat":37.4601,"lon":126.9091,"drainage_capacity":100.0,"impervious_ratio":0.503,
     "topo_depression":0.78,"flood_history":0.027},
    {"id":"SL082","name":"역촌동","gu":"은평구","city":"서울",
     "lat":37.6046,"lon":126.9145,"drainage_capacity":100.0,"impervious_ratio":0.758,
     "topo_depression":0.931,"flood_history":0.027},
    {"id":"SL083","name":"서원동","gu":"관악구","city":"서울",
     "lat":37.4806,"lon":126.9334,"drainage_capacity":100.0,"impervious_ratio":0.696,
     "topo_depression":0.839,"flood_history":0.027},
    {"id":"SL084","name":"중앙동","gu":"관악구","city":"서울",
     "lat":37.4841,"lon":126.9506,"drainage_capacity":100.0,"impervious_ratio":0.785,
     "topo_depression":0.875,"flood_history":0.027},
    {"id":"SL085","name":"서림동","gu":"관악구","city":"서울",
     "lat":37.4735,"lon":126.9392,"drainage_capacity":100.0,"impervious_ratio":0.637,
     "topo_depression":0.768,"flood_history":0.027},
    {"id":"SL086","name":"노량진1동","gu":"동작구","city":"서울",
     "lat":37.5130,"lon":126.9492,"drainage_capacity":100.0,"impervious_ratio":0.64,
     "topo_depression":0.919,"flood_history":0.027},
    {"id":"SL087","name":"방화2동","gu":"강서구","city":"서울",
     "lat":37.5838,"lon":126.8045,"drainage_capacity":100.0,"impervious_ratio":0.489,
     "topo_depression":0.963,"flood_history":0.027},
    {"id":"SL088","name":"가리봉동","gu":"구로구","city":"서울",
     "lat":37.4826,"lon":126.8883,"drainage_capacity":100.0,"impervious_ratio":0.788,
     "topo_depression":0.966,"flood_history":0.026},
    {"id":"SL089","name":"인헌동","gu":"관악구","city":"서울",
     "lat":37.4721,"lon":126.9666,"drainage_capacity":100.0,"impervious_ratio":0.628,
     "topo_depression":0.689,"flood_history":0.026},
    {"id":"SL090","name":"신길7동","gu":"영등포구","city":"서울",
     "lat":37.5058,"lon":126.9198,"drainage_capacity":100.0,"impervious_ratio":0.75,
     "topo_depression":0.923,"flood_history":0.026},
    {"id":"SL091","name":"양평1동","gu":"영등포구","city":"서울",
     "lat":37.5251,"lon":126.8871,"drainage_capacity":100.0,"impervious_ratio":0.717,
     "topo_depression":1.0,"flood_history":0.025},
    {"id":"SL092","name":"북가좌2동","gu":"서대문구","city":"서울",
     "lat":37.5810,"lon":126.9135,"drainage_capacity":100.0,"impervious_ratio":0.776,
     "topo_depression":0.926,"flood_history":0.025},
    {"id":"SL093","name":"개포4동","gu":"강남구","city":"서울",
     "lat":37.4756,"lon":127.0532,"drainage_capacity":100.0,"impervious_ratio":0.445,
     "topo_depression":0.742,"flood_history":0.023},
    {"id":"SL094","name":"행운동","gu":"관악구","city":"서울",
     "lat":37.4809,"lon":126.9606,"drainage_capacity":100.0,"impervious_ratio":0.718,
     "topo_depression":0.753,"flood_history":0.022},
    {"id":"SL095","name":"응암1동","gu":"은평구","city":"서울",
     "lat":37.5983,"lon":126.9269,"drainage_capacity":100.0,"impervious_ratio":0.602,
     "topo_depression":0.781,"flood_history":0.022},
    {"id":"SL096","name":"갈현2동","gu":"은평구","city":"서울",
     "lat":37.6183,"lon":126.9121,"drainage_capacity":100.0,"impervious_ratio":0.616,
     "topo_depression":0.85,"flood_history":0.021},
    {"id":"SL097","name":"신길4동","gu":"영등포구","city":"서울",
     "lat":37.5073,"lon":126.9129,"drainage_capacity":100.0,"impervious_ratio":0.779,
     "topo_depression":0.92,"flood_history":0.021},
    {"id":"SL098","name":"송파1동","gu":"송파구","city":"서울",
     "lat":37.5072,"lon":127.1103,"drainage_capacity":100.0,"impervious_ratio":0.778,
     "topo_depression":0.954,"flood_history":0.02},
    {"id":"SL099","name":"상계2동","gu":"노원구","city":"서울",
     "lat":37.6565,"lon":127.0673,"drainage_capacity":100.0,"impervious_ratio":0.795,
     "topo_depression":0.917,"flood_history":0.02},
    {"id":"SL100","name":"송중동","gu":"강북구","city":"서울",
     "lat":37.6177,"lon":127.0329,"drainage_capacity":100.0,"impervious_ratio":0.718,
     "topo_depression":0.816,"flood_history":0.02},
    # 인천광역시 (IC001~IC043)
        {"id":"IC001","name":"논현고잔동","gu":"남동구","city":"인천","lat":37.3944,"lon":126.703,"drainage_capacity":90.0,"impervious_ratio":0.731,"topo_depression":0.971,"flood_history":0.688},
    {"id":"IC002","name":"동춘3동","gu":"연수구","city":"인천","lat":37.4078,"lon":126.6782,"drainage_capacity":90.0,"impervious_ratio":0.742,"topo_depression":0.976,"flood_history":0.556},
    {"id":"IC003","name":"선학동","gu":"연수구","city":"인천","lat":37.4297,"lon":126.6975,"drainage_capacity":90.0,"impervious_ratio":0.549,"topo_depression":0.676,"flood_history":0.549},
    {"id":"IC004","name":"도화2·3동","gu":"미추홀구","city":"인천","lat":37.4735,"lon":126.6623,"drainage_capacity":90.0,"impervious_ratio":0.768,"topo_depression":0.823,"flood_history":0.528},
    {"id":"IC005","name":"간석4동","gu":"남동구","city":"인천","lat":37.4667,"lon":126.6964,"drainage_capacity":90.0,"impervious_ratio":0.895,"topo_depression":0.916,"flood_history":0.52},
    {"id":"IC006","name":"동춘2동","gu":"연수구","city":"인천","lat":37.4009,"lon":126.6711,"drainage_capacity":90.0,"impervious_ratio":0.688,"topo_depression":0.939,"flood_history":0.504},
    {"id":"IC007","name":"연수2동","gu":"연수구","city":"인천","lat":37.4134,"lon":126.6841,"drainage_capacity":90.0,"impervious_ratio":0.762,"topo_depression":0.967,"flood_history":0.489},
    {"id":"IC008","name":"십정2동","gu":"부평구","city":"인천","lat":37.4731,"lon":126.7027,"drainage_capacity":90.0,"impervious_ratio":0.776,"topo_depression":0.515,"flood_history":0.441},
    {"id":"IC009","name":"청학동","gu":"연수구","city":"인천","lat":37.425,"lon":126.6664,"drainage_capacity":90.0,"impervious_ratio":0.461,"topo_depression":0.242,"flood_history":0.423},
    {"id":"IC010","name":"작전서운동","gu":"계양구","city":"인천","lat":37.5303,"lon":126.748,"drainage_capacity":90.0,"impervious_ratio":0.713,"topo_depression":0.937,"flood_history":0.388},
    {"id":"IC011","name":"논현2동","gu":"남동구","city":"인천","lat":37.4076,"lon":126.7081,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.859,"flood_history":0.354},
    {"id":"IC012","name":"계양3동","gu":"계양구","city":"인천","lat":37.5694,"lon":126.7648,"drainage_capacity":90.0,"impervious_ratio":0.528,"topo_depression":0.93,"flood_history":0.351},
    {"id":"IC013","name":"남촌도림동","gu":"남동구","city":"인천","lat":37.4257,"lon":126.7209,"drainage_capacity":90.0,"impervious_ratio":0.619,"topo_depression":0.782,"flood_history":0.339},
    {"id":"IC014","name":"송림4동","gu":"동구","city":"인천","lat":37.4818,"lon":126.6579,"drainage_capacity":90.0,"impervious_ratio":0.739,"topo_depression":0.922,"flood_history":0.332},
    {"id":"IC015","name":"장수서창동","gu":"남동구","city":"인천","lat":37.4511,"lon":126.7606,"drainage_capacity":90.0,"impervious_ratio":0.351,"topo_depression":0.0,"flood_history":0.325},
    {"id":"IC016","name":"불로대곡동","gu":"서구","city":"인천","lat":37.6179,"lon":126.6771,"drainage_capacity":90.0,"impervious_ratio":0.289,"topo_depression":0.432,"flood_history":0.322},
    {"id":"IC017","name":"연수3동","gu":"연수구","city":"인천","lat":37.4197,"lon":126.6885,"drainage_capacity":90.0,"impervious_ratio":0.605,"topo_depression":0.867,"flood_history":0.316},
    {"id":"IC018","name":"옥련1동","gu":"연수구","city":"인천","lat":37.4202,"lon":126.6498,"drainage_capacity":90.0,"impervious_ratio":0.644,"topo_depression":0.583,"flood_history":0.287},
    {"id":"IC019","name":"연수1동","gu":"연수구","city":"인천","lat":37.4251,"lon":126.6799,"drainage_capacity":90.0,"impervious_ratio":0.475,"topo_depression":0.144,"flood_history":0.281},
    {"id":"IC020","name":"서창2동","gu":"남동구","city":"인천","lat":37.4266,"lon":126.7482,"drainage_capacity":90.0,"impervious_ratio":0.568,"topo_depression":0.918,"flood_history":0.276},
    {"id":"IC021","name":"만수6동","gu":"남동구","city":"인천","lat":37.4419,"lon":126.7399,"drainage_capacity":90.0,"impervious_ratio":0.649,"topo_depression":0.844,"flood_history":0.267},
    {"id":"IC022","name":"숭의1·3동","gu":"미추홀구","city":"인천","lat":37.4649,"lon":126.6453,"drainage_capacity":90.0,"impervious_ratio":0.874,"topo_depression":0.805,"flood_history":0.257},
    {"id":"IC023","name":"송도1동","gu":"연수구","city":"인천","lat":37.3829,"lon":126.6471,"drainage_capacity":90.0,"impervious_ratio":0.545,"topo_depression":0.968,"flood_history":0.256},
    {"id":"IC024","name":"송도3동","gu":"연수구","city":"인천","lat":37.3642,"lon":126.6559,"drainage_capacity":90.0,"impervious_ratio":0.354,"topo_depression":0.981,"flood_history":0.254},
    {"id":"IC025","name":"동춘1동","gu":"연수구","city":"인천","lat":37.4086,"lon":126.6595,"drainage_capacity":90.0,"impervious_ratio":0.371,"topo_depression":0.746,"flood_history":0.215},
    {"id":"IC026","name":"숭의2동","gu":"미추홀구","city":"인천","lat":37.4609,"lon":126.6476,"drainage_capacity":90.0,"impervious_ratio":0.969,"topo_depression":0.89,"flood_history":0.211},
    {"id":"IC027","name":"간석1동","gu":"남동구","city":"인천","lat":37.4597,"lon":126.7017,"drainage_capacity":90.0,"impervious_ratio":0.816,"topo_depression":0.717,"flood_history":0.206},
    {"id":"IC028","name":"논현1동","gu":"남동구","city":"인천","lat":37.409,"lon":126.739,"drainage_capacity":90.0,"impervious_ratio":0.402,"topo_depression":0.912,"flood_history":0.201},
    {"id":"IC029","name":"용현2동","gu":"미추홀구","city":"인천","lat":37.4562,"lon":126.6435,"drainage_capacity":90.0,"impervious_ratio":0.831,"topo_depression":0.934,"flood_history":0.199},
    {"id":"IC030","name":"학익1동","gu":"미추홀구","city":"인천","lat":37.4385,"lon":126.6537,"drainage_capacity":90.0,"impervious_ratio":0.366,"topo_depression":0.559,"flood_history":0.197},
    {"id":"IC031","name":"가좌1동","gu":"서구","city":"인천","lat":37.4914,"lon":126.6626,"drainage_capacity":90.0,"impervious_ratio":0.798,"topo_depression":0.97,"flood_history":0.189},
    {"id":"IC032","name":"송림6동","gu":"동구","city":"인천","lat":37.4818,"lon":126.6484,"drainage_capacity":90.0,"impervious_ratio":0.833,"topo_depression":0.943,"flood_history":0.18},
    {"id":"IC033","name":"계양1동","gu":"계양구","city":"인천","lat":37.5718,"lon":126.7262,"drainage_capacity":90.0,"impervious_ratio":0.462,"topo_depression":0.363,"flood_history":0.17},
    {"id":"IC034","name":"송현3동","gu":"동구","city":"인천","lat":37.4882,"lon":126.6411,"drainage_capacity":90.0,"impervious_ratio":0.849,"topo_depression":0.951,"flood_history":0.161},
    {"id":"IC035","name":"옥련2동","gu":"연수구","city":"인천","lat":37.4289,"lon":126.647,"drainage_capacity":90.0,"impervious_ratio":0.399,"topo_depression":0.589,"flood_history":0.156},
    {"id":"IC036","name":"송림2동","gu":"동구","city":"인천","lat":37.4765,"lon":126.643,"drainage_capacity":90.0,"impervious_ratio":0.913,"topo_depression":0.869,"flood_history":0.131},
    {"id":"IC037","name":"간석2동","gu":"남동구","city":"인천","lat":37.4604,"lon":126.7105,"drainage_capacity":90.0,"impervious_ratio":0.887,"topo_depression":0.604,"flood_history":0.126},
    {"id":"IC038","name":"원당동","gu":"서구","city":"인천","lat":37.5918,"lon":126.7058,"drainage_capacity":90.0,"impervious_ratio":0.435,"topo_depression":0.569,"flood_history":0.126},
    {"id":"IC039","name":"도화1동","gu":"미추홀구","city":"인천","lat":37.4622,"lon":126.6692,"drainage_capacity":90.0,"impervious_ratio":0.829,"topo_depression":0.599,"flood_history":0.125},
    {"id":"IC040","name":"가좌3동","gu":"서구","city":"인천","lat":37.4877,"lon":126.6802,"drainage_capacity":90.0,"impervious_ratio":0.789,"topo_depression":0.687,"flood_history":0.063},
    {"id":"IC041","name":"송도5동","gu":"연수구","city":"인천","lat":37.42,"lon":126.6169,"drainage_capacity":90.0,"impervious_ratio":0.289,"topo_depression":1.0,"flood_history":0.062},
    {"id":"IC042","name":"송림3·5동","gu":"동구","city":"인천","lat":37.4731,"lon":126.6484,"drainage_capacity":90.0,"impervious_ratio":0.672,"topo_depression":0.72,"flood_history":0.002},
    {"id":"IC043","name":"주안5동","gu":"미추홀구","city":"인천","lat":37.4692,"lon":126.6805,"drainage_capacity":90.0,"impervious_ratio":0.937,"topo_depression":0.971,"flood_history":0.0},
    # 서울 비취약 동 (SL101~)
    {"id":"SL101","name":"사직동","gu":"종로구","city":"서울","lat":37.5741,"lon":126.9701,"drainage_capacity":100.0,"impervious_ratio":0.676,"topo_depression":0.851,"flood_history":0.0},
    {"id":"SL102","name":"삼청동","gu":"종로구","city":"서울","lat":37.588,"lon":126.9811,"drainage_capacity":100.0,"impervious_ratio":0.222,"topo_depression":0.631,"flood_history":0.0},
    {"id":"SL103","name":"부암동","gu":"종로구","city":"서울","lat":37.5967,"lon":126.9626,"drainage_capacity":100.0,"impervious_ratio":0.301,"topo_depression":0.463,"flood_history":0.0},
    {"id":"SL104","name":"평창동","gu":"종로구","city":"서울","lat":37.614,"lon":126.9693,"drainage_capacity":100.0,"impervious_ratio":0.182,"topo_depression":0.0,"flood_history":0.0},
    {"id":"SL105","name":"무악동","gu":"종로구","city":"서울","lat":37.5777,"lon":126.959,"drainage_capacity":100.0,"impervious_ratio":0.386,"topo_depression":0.587,"flood_history":0.0},
    {"id":"SL106","name":"교남동","gu":"종로구","city":"서울","lat":37.5711,"lon":126.9642,"drainage_capacity":100.0,"impervious_ratio":0.86,"topo_depression":0.814,"flood_history":0.0},
    {"id":"SL107","name":"가회동","gu":"종로구","city":"서울","lat":37.5827,"lon":126.9866,"drainage_capacity":100.0,"impervious_ratio":0.662,"topo_depression":0.81,"flood_history":0.0},
    {"id":"SL108","name":"종로1·2·3·4가동","gu":"종로구","city":"서울","lat":37.5751,"lon":126.9897,"drainage_capacity":100.0,"impervious_ratio":0.61,"topo_depression":0.908,"flood_history":0.0},
    {"id":"SL109","name":"종로5·6가동","gu":"종로구","city":"서울","lat":37.573,"lon":127.0042,"drainage_capacity":100.0,"impervious_ratio":0.835,"topo_depression":0.934,"flood_history":0.0},
    {"id":"SL110","name":"이화동","gu":"종로구","city":"서울","lat":37.5797,"lon":127.0031,"drainage_capacity":100.0,"impervious_ratio":0.611,"topo_depression":0.856,"flood_history":0.0},
    {"id":"SL111","name":"창신1동","gu":"종로구","city":"서울","lat":37.5723,"lon":127.014,"drainage_capacity":100.0,"impervious_ratio":0.917,"topo_depression":0.952,"flood_history":0.0},
    {"id":"SL112","name":"창신2동","gu":"종로구","city":"서울","lat":37.5758,"lon":127.0103,"drainage_capacity":100.0,"impervious_ratio":0.794,"topo_depression":0.84,"flood_history":0.0},
    {"id":"SL113","name":"창신3동","gu":"종로구","city":"서울","lat":37.5788,"lon":127.0132,"drainage_capacity":100.0,"impervious_ratio":0.536,"topo_depression":0.844,"flood_history":0.0},
    {"id":"SL114","name":"숭인1동","gu":"종로구","city":"서울","lat":37.5772,"lon":127.0169,"drainage_capacity":100.0,"impervious_ratio":0.69,"topo_depression":0.895,"flood_history":0.0},
    {"id":"SL115","name":"숭인2동","gu":"종로구","city":"서울","lat":37.5743,"lon":127.0206,"drainage_capacity":100.0,"impervious_ratio":0.947,"topo_depression":0.958,"flood_history":0.0},
    {"id":"SL116","name":"청운효자동","gu":"종로구","city":"서울","lat":37.5847,"lon":126.9704,"drainage_capacity":100.0,"impervious_ratio":0.359,"topo_depression":0.708,"flood_history":0.0},
    {"id":"SL117","name":"혜화동","gu":"종로구","city":"서울","lat":37.5875,"lon":126.9977,"drainage_capacity":100.0,"impervious_ratio":0.612,"topo_depression":0.816,"flood_history":0.0},
    {"id":"SL118","name":"소공동","gu":"중구","city":"서울","lat":37.5643,"lon":126.9744,"drainage_capacity":100.0,"impervious_ratio":0.716,"topo_depression":0.897,"flood_history":0.0},
    {"id":"SL119","name":"회현동","gu":"중구","city":"서울","lat":37.557,"lon":126.9767,"drainage_capacity":100.0,"impervious_ratio":0.813,"topo_depression":0.821,"flood_history":0.0},
    {"id":"SL120","name":"명동","gu":"중구","city":"서울","lat":37.5637,"lon":126.9844,"drainage_capacity":100.0,"impervious_ratio":0.855,"topo_depression":0.866,"flood_history":0.0},
    {"id":"SL121","name":"필동","gu":"중구","city":"서울","lat":37.5568,"lon":126.9938,"drainage_capacity":100.0,"impervious_ratio":0.38,"topo_depression":0.673,"flood_history":0.0},
    {"id":"SL122","name":"장충동","gu":"중구","city":"서울","lat":37.5556,"lon":127.0023,"drainage_capacity":100.0,"impervious_ratio":0.548,"topo_depression":0.716,"flood_history":0.0},
    {"id":"SL123","name":"광희동","gu":"중구","city":"서울","lat":37.5652,"lon":127.0036,"drainage_capacity":100.0,"impervious_ratio":0.925,"topo_depression":0.932,"flood_history":0.0},
    {"id":"SL124","name":"을지로동","gu":"중구","city":"서울","lat":37.5666,"lon":126.9965,"drainage_capacity":100.0,"impervious_ratio":0.761,"topo_depression":0.936,"flood_history":0.0},
    {"id":"SL125","name":"신당5동","gu":"중구","city":"서울","lat":37.5636,"lon":127.022,"drainage_capacity":100.0,"impervious_ratio":0.897,"topo_depression":0.873,"flood_history":0.0},
    {"id":"SL126","name":"황학동","gu":"중구","city":"서울","lat":37.5684,"lon":127.0208,"drainage_capacity":100.0,"impervious_ratio":0.977,"topo_depression":0.944,"flood_history":0.0},
    {"id":"SL127","name":"중림동","gu":"중구","city":"서울","lat":37.5573,"lon":126.966,"drainage_capacity":100.0,"impervious_ratio":0.754,"topo_depression":0.853,"flood_history":0.0},
    {"id":"SL128","name":"신당동","gu":"중구","city":"서울","lat":37.5657,"lon":127.0138,"drainage_capacity":100.0,"impervious_ratio":0.848,"topo_depression":0.94,"flood_history":0.0},
    {"id":"SL129","name":"다산동","gu":"중구","city":"서울","lat":37.5547,"lon":127.0083,"drainage_capacity":100.0,"impervious_ratio":0.955,"topo_depression":0.836,"flood_history":0.0},
    {"id":"SL130","name":"약수동","gu":"중구","city":"서울","lat":37.5498,"lon":127.0102,"drainage_capacity":100.0,"impervious_ratio":0.698,"topo_depression":0.691,"flood_history":0.0},
    {"id":"SL131","name":"청구동","gu":"중구","city":"서울","lat":37.5569,"lon":127.015,"drainage_capacity":100.0,"impervious_ratio":0.9,"topo_depression":0.825,"flood_history":0.0},
    {"id":"SL132","name":"동화동","gu":"중구","city":"서울","lat":37.5606,"lon":127.0187,"drainage_capacity":100.0,"impervious_ratio":0.837,"topo_depression":0.849,"flood_history":0.0},
    {"id":"SL133","name":"후암동","gu":"용산구","city":"서울","lat":37.5499,"lon":126.9806,"drainage_capacity":100.0,"impervious_ratio":0.713,"topo_depression":0.695,"flood_history":0.0},
    {"id":"SL134","name":"용산2가동","gu":"용산구","city":"서울","lat":37.5402,"lon":126.9835,"drainage_capacity":100.0,"impervious_ratio":0.192,"topo_depression":0.807,"flood_history":0.0},
    {"id":"SL135","name":"남영동","gu":"용산구","city":"서울","lat":37.5451,"lon":126.9735,"drainage_capacity":100.0,"impervious_ratio":0.766,"topo_depression":0.931,"flood_history":0.0},
    {"id":"SL136","name":"원효로2동","gu":"용산구","city":"서울","lat":37.5331,"lon":126.9514,"drainage_capacity":100.0,"impervious_ratio":0.557,"topo_depression":0.973,"flood_history":0.0},
    {"id":"SL137","name":"효창동","gu":"용산구","city":"서울","lat":37.5431,"lon":126.9613,"drainage_capacity":100.0,"impervious_ratio":0.71,"topo_depression":0.89,"flood_history":0.0},
    {"id":"SL138","name":"용문동","gu":"용산구","city":"서울","lat":37.5381,"lon":126.9586,"drainage_capacity":100.0,"impervious_ratio":0.886,"topo_depression":0.944,"flood_history":0.0},
    {"id":"SL139","name":"이촌1동","gu":"용산구","city":"서울","lat":37.5173,"lon":126.971,"drainage_capacity":100.0,"impervious_ratio":0.364,"topo_depression":0.991,"flood_history":0.0},
    {"id":"SL140","name":"이촌2동","gu":"용산구","city":"서울","lat":37.5233,"lon":126.9539,"drainage_capacity":100.0,"impervious_ratio":0.253,"topo_depression":0.994,"flood_history":0.0},
    {"id":"SL141","name":"이태원1동","gu":"용산구","city":"서울","lat":37.5334,"lon":126.9932,"drainage_capacity":100.0,"impervious_ratio":0.81,"topo_depression":0.819,"flood_history":0.0},
    {"id":"SL142","name":"이태원2동","gu":"용산구","city":"서울","lat":37.5417,"lon":126.9921,"drainage_capacity":100.0,"impervious_ratio":0.636,"topo_depression":0.634,"flood_history":0.0},
    {"id":"SL143","name":"서빙고동","gu":"용산구","city":"서울","lat":37.5225,"lon":126.9884,"drainage_capacity":100.0,"impervious_ratio":0.297,"topo_depression":0.959,"flood_history":0.0},
    {"id":"SL144","name":"보광동","gu":"용산구","city":"서울","lat":37.5259,"lon":127.0013,"drainage_capacity":100.0,"impervious_ratio":0.593,"topo_depression":0.936,"flood_history":0.0},
    {"id":"SL145","name":"청파동","gu":"용산구","city":"서울","lat":37.5479,"lon":126.9672,"drainage_capacity":100.0,"impervious_ratio":0.792,"topo_depression":0.892,"flood_history":0.0},
    {"id":"SL146","name":"원효로1동","gu":"용산구","city":"서울","lat":37.5375,"lon":126.9666,"drainage_capacity":100.0,"impervious_ratio":0.913,"topo_depression":0.964,"flood_history":0.0},
    {"id":"SL147","name":"한강로동","gu":"용산구","city":"서울","lat":37.5292,"lon":126.9679,"drainage_capacity":100.0,"impervious_ratio":0.475,"topo_depression":0.976,"flood_history":0.0},
    {"id":"SL148","name":"한남동","gu":"용산구","city":"서울","lat":37.5371,"lon":127.0058,"drainage_capacity":100.0,"impervious_ratio":0.563,"topo_depression":0.851,"flood_history":0.0},
    {"id":"SL149","name":"왕십리2동","gu":"성동구","city":"서울","lat":37.5615,"lon":127.0277,"drainage_capacity":100.0,"impervious_ratio":0.872,"topo_depression":0.87,"flood_history":0.0},
    {"id":"SL150","name":"마장동","gu":"성동구","city":"서울","lat":37.5676,"lon":127.0405,"drainage_capacity":100.0,"impervious_ratio":0.812,"topo_depression":0.964,"flood_history":0.0},
    {"id":"SL151","name":"사근동","gu":"성동구","city":"서울","lat":37.558,"lon":127.0454,"drainage_capacity":100.0,"impervious_ratio":0.444,"topo_depression":0.943,"flood_history":0.0},
    {"id":"SL152","name":"행당1동","gu":"성동구","city":"서울","lat":37.559,"lon":127.0361,"drainage_capacity":100.0,"impervious_ratio":0.809,"topo_depression":0.949,"flood_history":0.0},
    {"id":"SL153","name":"행당2동","gu":"성동구","city":"서울","lat":37.5567,"lon":127.0295,"drainage_capacity":100.0,"impervious_ratio":0.803,"topo_depression":0.86,"flood_history":0.0},
    {"id":"SL154","name":"응봉동","gu":"성동구","city":"서울","lat":37.551,"lon":127.034,"drainage_capacity":100.0,"impervious_ratio":0.594,"topo_depression":0.943,"flood_history":0.0},
    {"id":"SL155","name":"금호1가동","gu":"성동구","city":"서울","lat":37.5537,"lon":127.0251,"drainage_capacity":100.0,"impervious_ratio":0.673,"topo_depression":0.793,"flood_history":0.0},
    {"id":"SL156","name":"금호4가동","gu":"성동구","city":"서울","lat":37.5446,"lon":127.0246,"drainage_capacity":100.0,"impervious_ratio":0.457,"topo_depression":0.948,"flood_history":0.0},
    {"id":"SL157","name":"성수1가1동","gu":"성동구","city":"서울","lat":37.5404,"lon":127.041,"drainage_capacity":100.0,"impervious_ratio":0.373,"topo_depression":0.983,"flood_history":0.0},
    {"id":"SL158","name":"성수1가2동","gu":"성동구","city":"서울","lat":37.5491,"lon":127.044,"drainage_capacity":100.0,"impervious_ratio":0.684,"topo_depression":0.988,"flood_history":0.0},
    {"id":"SL159","name":"성수2가1동","gu":"성동구","city":"서울","lat":37.5367,"lon":127.0553,"drainage_capacity":100.0,"impervious_ratio":0.629,"topo_depression":0.987,"flood_history":0.0},
    {"id":"SL160","name":"성수2가3동","gu":"성동구","city":"서울","lat":37.5455,"lon":127.0581,"drainage_capacity":100.0,"impervious_ratio":0.969,"topo_depression":0.985,"flood_history":0.0},
    {"id":"SL161","name":"송정동","gu":"성동구","city":"서울","lat":37.5523,"lon":127.0657,"drainage_capacity":100.0,"impervious_ratio":0.635,"topo_depression":0.98,"flood_history":0.0},
    {"id":"SL162","name":"용답동","gu":"성동구","city":"서울","lat":37.5585,"lon":127.0578,"drainage_capacity":100.0,"impervious_ratio":0.401,"topo_depression":0.991,"flood_history":0.0},
    {"id":"SL163","name":"왕십리도선동","gu":"성동구","city":"서울","lat":37.5668,"lon":127.0296,"drainage_capacity":100.0,"impervious_ratio":0.92,"topo_depression":0.944,"flood_history":0.0},
    {"id":"SL164","name":"금호2·3가동","gu":"성동구","city":"서울","lat":37.5514,"lon":127.0199,"drainage_capacity":100.0,"impervious_ratio":0.741,"topo_depression":0.83,"flood_history":0.0},
    {"id":"SL165","name":"옥수동","gu":"성동구","city":"서울","lat":37.542,"lon":127.0162,"drainage_capacity":100.0,"impervious_ratio":0.529,"topo_depression":0.9,"flood_history":0.0},
    {"id":"SL166","name":"화양동","gu":"광진구","city":"서울","lat":37.5433,"lon":127.0735,"drainage_capacity":100.0,"impervious_ratio":0.625,"topo_depression":0.959,"flood_history":0.0},
    {"id":"SL167","name":"군자동","gu":"광진구","city":"서울","lat":37.5531,"lon":127.0737,"drainage_capacity":100.0,"impervious_ratio":0.822,"topo_depression":0.965,"flood_history":0.0},
    {"id":"SL168","name":"중곡1동","gu":"광진구","city":"서울","lat":37.562,"lon":127.0777,"drainage_capacity":100.0,"impervious_ratio":0.822,"topo_depression":0.971,"flood_history":0.0},
    {"id":"SL169","name":"중곡2동","gu":"광진구","city":"서울","lat":37.5589,"lon":127.0846,"drainage_capacity":100.0,"impervious_ratio":0.97,"topo_depression":0.938,"flood_history":0.0},
    {"id":"SL170","name":"중곡3동","gu":"광진구","city":"서울","lat":37.5679,"lon":127.082,"drainage_capacity":100.0,"impervious_ratio":0.784,"topo_depression":0.943,"flood_history":0.0},
    {"id":"SL171","name":"중곡4동","gu":"광진구","city":"서울","lat":37.5639,"lon":127.0944,"drainage_capacity":100.0,"impervious_ratio":0.296,"topo_depression":0.501,"flood_history":0.0},
    {"id":"SL172","name":"능동","gu":"광진구","city":"서울","lat":37.5507,"lon":127.0816,"drainage_capacity":100.0,"impervious_ratio":0.523,"topo_depression":0.936,"flood_history":0.0},
    {"id":"SL173","name":"구의1동","gu":"광진구","city":"서울","lat":37.5415,"lon":127.086,"drainage_capacity":100.0,"impervious_ratio":0.971,"topo_depression":0.947,"flood_history":0.0},
    {"id":"SL174","name":"구의2동","gu":"광진구","city":"서울","lat":37.551,"lon":127.0945,"drainage_capacity":100.0,"impervious_ratio":0.568,"topo_depression":0.779,"flood_history":0.0},
    {"id":"SL175","name":"구의3동","gu":"광진구","city":"서울","lat":37.5351,"lon":127.0952,"drainage_capacity":100.0,"impervious_ratio":0.545,"topo_depression":0.977,"flood_history":0.0},
    {"id":"SL176","name":"광장동","gu":"광진구","city":"서울","lat":37.5483,"lon":127.1049,"drainage_capacity":100.0,"impervious_ratio":0.414,"topo_depression":0.883,"flood_history":0.0},
    {"id":"SL177","name":"자양1동","gu":"광진구","city":"서울","lat":37.5355,"lon":127.0804,"drainage_capacity":100.0,"impervious_ratio":0.985,"topo_depression":0.958,"flood_history":0.0},
    {"id":"SL178","name":"자양2동","gu":"광진구","city":"서울","lat":37.5293,"lon":127.0833,"drainage_capacity":100.0,"impervious_ratio":0.449,"topo_depression":0.966,"flood_history":0.0},
    {"id":"SL179","name":"자양3동","gu":"광진구","city":"서울","lat":37.5317,"lon":127.0712,"drainage_capacity":100.0,"impervious_ratio":0.58,"topo_depression":0.984,"flood_history":0.0},
    {"id":"SL180","name":"자양4동","gu":"광진구","city":"서울","lat":37.5339,"lon":127.0638,"drainage_capacity":100.0,"impervious_ratio":0.604,"topo_depression":0.985,"flood_history":0.0},
    {"id":"SL181","name":"회기동","gu":"동대문구","city":"서울","lat":37.5937,"lon":127.0514,"drainage_capacity":100.0,"impervious_ratio":0.531,"topo_depression":0.877,"flood_history":0.0},
    {"id":"SL182","name":"휘경1동","gu":"동대문구","city":"서울","lat":37.5919,"lon":127.0625,"drainage_capacity":100.0,"impervious_ratio":0.778,"topo_depression":0.969,"flood_history":0.0},
    {"id":"SL183","name":"휘경2동","gu":"동대문구","city":"서울","lat":37.5865,"lon":127.0664,"drainage_capacity":100.0,"impervious_ratio":0.593,"topo_depression":0.945,"flood_history":0.0},
    {"id":"SL184","name":"청량리동","gu":"동대문구","city":"서울","lat":37.5889,"lon":127.0451,"drainage_capacity":100.0,"impervious_ratio":0.521,"topo_depression":0.912,"flood_history":0.0},
    {"id":"SL185","name":"용신동","gu":"동대문구","city":"서울","lat":37.5756,"lon":127.0323,"drainage_capacity":100.0,"impervious_ratio":0.883,"topo_depression":0.968,"flood_history":0.0},
    {"id":"SL186","name":"제기동","gu":"동대문구","city":"서울","lat":37.5837,"lon":127.0372,"drainage_capacity":100.0,"impervious_ratio":0.924,"topo_depression":0.968,"flood_history":0.0},
    {"id":"SL187","name":"전농1동","gu":"동대문구","city":"서울","lat":37.579,"lon":127.051,"drainage_capacity":100.0,"impervious_ratio":0.898,"topo_depression":0.946,"flood_history":0.0},
    {"id":"SL188","name":"전농2동","gu":"동대문구","city":"서울","lat":37.5807,"lon":127.0611,"drainage_capacity":100.0,"impervious_ratio":0.402,"topo_depression":0.886,"flood_history":0.0},
    {"id":"SL189","name":"답십리2동","gu":"동대문구","city":"서울","lat":37.5709,"lon":127.0611,"drainage_capacity":100.0,"impervious_ratio":0.733,"topo_depression":0.944,"flood_history":0.0},
    {"id":"SL190","name":"장안1동","gu":"동대문구","city":"서울","lat":37.5662,"lon":127.0686,"drainage_capacity":100.0,"impervious_ratio":0.842,"topo_depression":0.99,"flood_history":0.0},
    {"id":"SL191","name":"장안2동","gu":"동대문구","city":"서울","lat":37.5758,"lon":127.0725,"drainage_capacity":100.0,"impervious_ratio":0.838,"topo_depression":0.989,"flood_history":0.0},
    {"id":"SL192","name":"이문1동","gu":"동대문구","city":"서울","lat":37.5972,"lon":127.0603,"drainage_capacity":100.0,"impervious_ratio":0.528,"topo_depression":0.942,"flood_history":0.0},
    {"id":"SL193","name":"이문2동","gu":"동대문구","city":"서울","lat":37.6028,"lon":127.0675,"drainage_capacity":100.0,"impervious_ratio":0.735,"topo_depression":0.972,"flood_history":0.0},
    {"id":"SL194","name":"답십리1동","gu":"동대문구","city":"서울","lat":37.5709,"lon":127.0517,"drainage_capacity":100.0,"impervious_ratio":0.878,"topo_depression":0.967,"flood_history":0.0},
    {"id":"SL195","name":"면목2동","gu":"중랑구","city":"서울","lat":37.5894,"lon":127.0781,"drainage_capacity":100.0,"impervious_ratio":0.867,"topo_depression":0.981,"flood_history":0.0},
    {"id":"SL196","name":"면목4동","gu":"중랑구","city":"서울","lat":37.5735,"lon":127.0865,"drainage_capacity":100.0,"impervious_ratio":0.543,"topo_depression":0.705,"flood_history":0.0},
    {"id":"SL197","name":"면목5동","gu":"중랑구","city":"서울","lat":37.583,"lon":127.0797,"drainage_capacity":100.0,"impervious_ratio":0.736,"topo_depression":0.979,"flood_history":0.0},
    {"id":"SL198","name":"면목7동","gu":"중랑구","city":"서울","lat":37.5773,"lon":127.0927,"drainage_capacity":100.0,"impervious_ratio":0.436,"topo_depression":0.538,"flood_history":0.0},
    {"id":"SL199","name":"상봉1동","gu":"중랑구","city":"서울","lat":37.602,"lon":127.0895,"drainage_capacity":100.0,"impervious_ratio":0.689,"topo_depression":0.876,"flood_history":0.0},
    {"id":"SL200","name":"상봉2동","gu":"중랑구","city":"서울","lat":37.5942,"lon":127.0839,"drainage_capacity":100.0,"impervious_ratio":0.988,"topo_depression":0.965,"flood_history":0.0},
    {"id":"SL201","name":"중화1동","gu":"중랑구","city":"서울","lat":37.6023,"lon":127.0831,"drainage_capacity":100.0,"impervious_ratio":0.714,"topo_depression":0.894,"flood_history":0.0},
    {"id":"SL202","name":"중화2동","gu":"중랑구","city":"서울","lat":37.5987,"lon":127.0752,"drainage_capacity":100.0,"impervious_ratio":0.793,"topo_depression":0.98,"flood_history":0.0},
    {"id":"SL203","name":"묵1동","gu":"중랑구","city":"서울","lat":37.6137,"lon":127.0825,"drainage_capacity":100.0,"impervious_ratio":0.673,"topo_depression":0.879,"flood_history":0.0},
    {"id":"SL204","name":"묵2동","gu":"중랑구","city":"서울","lat":37.6104,"lon":127.0747,"drainage_capacity":100.0,"impervious_ratio":0.759,"topo_depression":0.974,"flood_history":0.0},
    {"id":"SL205","name":"망우3동","gu":"중랑구","city":"서울","lat":37.5918,"lon":127.1029,"drainage_capacity":100.0,"impervious_ratio":0.488,"topo_depression":0.64,"flood_history":0.0},
    {"id":"SL206","name":"신내1동","gu":"중랑구","city":"서울","lat":37.6128,"lon":127.1045,"drainage_capacity":100.0,"impervious_ratio":0.599,"topo_depression":0.827,"flood_history":0.0},
    {"id":"SL207","name":"신내2동","gu":"중랑구","city":"서울","lat":37.611,"lon":127.0916,"drainage_capacity":100.0,"impervious_ratio":0.453,"topo_depression":0.836,"flood_history":0.0},
    {"id":"SL208","name":"면목본동","gu":"중랑구","city":"서울","lat":37.5883,"lon":127.0895,"drainage_capacity":100.0,"impervious_ratio":0.98,"topo_depression":0.932,"flood_history":0.0},
    {"id":"SL209","name":"면목3·8동","gu":"중랑구","city":"서울","lat":37.5846,"lon":127.0974,"drainage_capacity":100.0,"impervious_ratio":0.517,"topo_depression":0.646,"flood_history":0.0},
    {"id":"SL210","name":"망우본동","gu":"중랑구","city":"서울","lat":37.602,"lon":127.1075,"drainage_capacity":100.0,"impervious_ratio":0.486,"topo_depression":0.752,"flood_history":0.0},
    {"id":"SL211","name":"돈암1동","gu":"성북구","city":"서울","lat":37.5993,"lon":127.024,"drainage_capacity":100.0,"impervious_ratio":0.625,"topo_depression":0.727,"flood_history":0.0},
    {"id":"SL212","name":"돈암2동","gu":"성북구","city":"서울","lat":37.5973,"lon":127.0116,"drainage_capacity":100.0,"impervious_ratio":0.697,"topo_depression":0.748,"flood_history":0.0},
    {"id":"SL213","name":"안암동","gu":"성북구","city":"서울","lat":37.5873,"lon":127.0273,"drainage_capacity":100.0,"impervious_ratio":0.538,"topo_depression":0.878,"flood_history":0.0},
    {"id":"SL214","name":"보문동","gu":"성북구","city":"서울","lat":37.5826,"lon":127.0192,"drainage_capacity":100.0,"impervious_ratio":0.836,"topo_depression":0.913,"flood_history":0.0},
    {"id":"SL215","name":"정릉1동","gu":"성북구","city":"서울","lat":37.6033,"lon":127.0167,"drainage_capacity":100.0,"impervious_ratio":0.959,"topo_depression":0.799,"flood_history":0.0},
    {"id":"SL216","name":"정릉2동","gu":"성북구","city":"서울","lat":37.6038,"lon":127.0081,"drainage_capacity":100.0,"impervious_ratio":0.59,"topo_depression":0.696,"flood_history":0.0},
    {"id":"SL217","name":"정릉3동","gu":"성북구","city":"서울","lat":37.6123,"lon":126.9938,"drainage_capacity":100.0,"impervious_ratio":0.255,"topo_depression":0.368,"flood_history":0.0},
    {"id":"SL218","name":"길음1동","gu":"성북구","city":"서울","lat":37.6081,"lon":127.0197,"drainage_capacity":100.0,"impervious_ratio":0.792,"topo_depression":0.798,"flood_history":0.0},
    {"id":"SL219","name":"길음2동","gu":"성북구","city":"서울","lat":37.608,"lon":127.0272,"drainage_capacity":100.0,"impervious_ratio":0.946,"topo_depression":0.886,"flood_history":0.0},
    {"id":"SL220","name":"월곡1동","gu":"성북구","city":"서울","lat":37.6079,"lon":127.0364,"drainage_capacity":100.0,"impervious_ratio":0.811,"topo_depression":0.866,"flood_history":0.0},
    {"id":"SL221","name":"월곡2동","gu":"성북구","city":"서울","lat":37.6033,"lon":127.0452,"drainage_capacity":100.0,"impervious_ratio":0.457,"topo_depression":0.854,"flood_history":0.0},
    {"id":"SL222","name":"장위1동","gu":"성북구","city":"서울","lat":37.6149,"lon":127.0443,"drainage_capacity":100.0,"impervious_ratio":0.831,"topo_depression":0.836,"flood_history":0.0},
    {"id":"SL223","name":"장위2동","gu":"성북구","city":"서울","lat":37.6122,"lon":127.0517,"drainage_capacity":100.0,"impervious_ratio":0.688,"topo_depression":0.934,"flood_history":0.0},
    {"id":"SL224","name":"장위3동","gu":"성북구","city":"서울","lat":37.6182,"lon":127.0535,"drainage_capacity":100.0,"impervious_ratio":0.7,"topo_depression":0.958,"flood_history":0.0},
    {"id":"SL225","name":"성북동","gu":"성북구","city":"서울","lat":37.5959,"lon":126.9962,"drainage_capacity":100.0,"impervious_ratio":0.519,"topo_depression":0.601,"flood_history":0.0},
    {"id":"SL226","name":"삼선동","gu":"성북구","city":"서울","lat":37.5866,"lon":127.0118,"drainage_capacity":100.0,"impervious_ratio":0.739,"topo_depression":0.838,"flood_history":0.0},
    {"id":"SL227","name":"동선동","gu":"성북구","city":"서울","lat":37.5937,"lon":127.0184,"drainage_capacity":100.0,"impervious_ratio":0.739,"topo_depression":0.825,"flood_history":0.0},
    {"id":"SL228","name":"종암동","gu":"성북구","city":"서울","lat":37.5973,"lon":127.0334,"drainage_capacity":100.0,"impervious_ratio":0.674,"topo_depression":0.876,"flood_history":0.0},
    {"id":"SL229","name":"석관동","gu":"성북구","city":"서울","lat":37.6083,"lon":127.0613,"drainage_capacity":100.0,"impervious_ratio":0.648,"topo_depression":0.942,"flood_history":0.0},
    {"id":"SL230","name":"번1동","gu":"강북구","city":"서울","lat":37.6376,"lon":127.0305,"drainage_capacity":100.0,"impervious_ratio":0.933,"topo_depression":0.923,"flood_history":0.0},
    {"id":"SL231","name":"번2동","gu":"강북구","city":"서울","lat":37.6295,"lon":127.0348,"drainage_capacity":100.0,"impervious_ratio":0.398,"topo_depression":0.841,"flood_history":0.0},
    {"id":"SL232","name":"번3동","gu":"강북구","city":"서울","lat":37.6238,"lon":127.0423,"drainage_capacity":100.0,"impervious_ratio":0.336,"topo_depression":0.868,"flood_history":0.0},
    {"id":"SL233","name":"수유2동","gu":"강북구","city":"서울","lat":37.6454,"lon":127.0195,"drainage_capacity":100.0,"impervious_ratio":0.948,"topo_depression":0.897,"flood_history":0.0},
    {"id":"SL234","name":"수유3동","gu":"강북구","city":"서울","lat":37.6405,"lon":127.0235,"drainage_capacity":100.0,"impervious_ratio":0.933,"topo_depression":0.907,"flood_history":0.0},
    {"id":"SL235","name":"미아동","gu":"강북구","city":"서울","lat":37.6287,"lon":127.0263,"drainage_capacity":100.0,"impervious_ratio":0.757,"topo_depression":0.817,"flood_history":0.0},
    {"id":"SL236","name":"송천동","gu":"강북구","city":"서울","lat":37.6182,"lon":127.0249,"drainage_capacity":100.0,"impervious_ratio":0.88,"topo_depression":0.884,"flood_history":0.0},
    {"id":"SL237","name":"삼각산동","gu":"강북구","city":"서울","lat":37.6171,"lon":127.0168,"drainage_capacity":100.0,"impervious_ratio":0.814,"topo_depression":0.74,"flood_history":0.0},
    {"id":"SL238","name":"쌍문1동","gu":"도봉구","city":"서울","lat":37.653,"lon":127.0195,"drainage_capacity":100.0,"impervious_ratio":0.536,"topo_depression":0.82,"flood_history":0.0},
    {"id":"SL239","name":"쌍문2동","gu":"도봉구","city":"서울","lat":37.6571,"lon":127.037,"drainage_capacity":100.0,"impervious_ratio":0.937,"topo_depression":0.911,"flood_history":0.0},
    {"id":"SL240","name":"쌍문3동","gu":"도봉구","city":"서울","lat":37.6477,"lon":127.0306,"drainage_capacity":100.0,"impervious_ratio":0.855,"topo_depression":0.883,"flood_history":0.0},
    {"id":"SL241","name":"쌍문4동","gu":"도봉구","city":"서울","lat":37.6556,"lon":127.0304,"drainage_capacity":100.0,"impervious_ratio":0.681,"topo_depression":0.858,"flood_history":0.0},
    {"id":"SL242","name":"방학1동","gu":"도봉구","city":"서울","lat":37.665,"lon":127.0435,"drainage_capacity":100.0,"impervious_ratio":0.869,"topo_depression":0.936,"flood_history":0.0},
    {"id":"SL243","name":"방학2동","gu":"도봉구","city":"서울","lat":37.6691,"lon":127.0323,"drainage_capacity":100.0,"impervious_ratio":0.489,"topo_depression":0.848,"flood_history":0.0},
    {"id":"SL244","name":"방학3동","gu":"도봉구","city":"서울","lat":37.6628,"lon":127.0235,"drainage_capacity":100.0,"impervious_ratio":0.272,"topo_depression":0.772,"flood_history":0.0},
    {"id":"SL245","name":"창1동","gu":"도봉구","city":"서울","lat":37.6471,"lon":127.0436,"drainage_capacity":100.0,"impervious_ratio":0.572,"topo_depression":0.895,"flood_history":0.0},
    {"id":"SL246","name":"창2동","gu":"도봉구","city":"서울","lat":37.6426,"lon":127.0368,"drainage_capacity":100.0,"impervious_ratio":0.914,"topo_depression":0.892,"flood_history":0.0},
    {"id":"SL247","name":"창3동","gu":"도봉구","city":"서울","lat":37.6374,"lon":127.0416,"drainage_capacity":100.0,"impervious_ratio":0.564,"topo_depression":0.846,"flood_history":0.0},
    {"id":"SL248","name":"창4동","gu":"도봉구","city":"서울","lat":37.6526,"lon":127.0509,"drainage_capacity":100.0,"impervious_ratio":0.672,"topo_depression":0.949,"flood_history":0.0},
    {"id":"SL249","name":"창5동","gu":"도봉구","city":"서울","lat":37.6554,"lon":127.0428,"drainage_capacity":100.0,"impervious_ratio":0.929,"topo_depression":0.934,"flood_history":0.0},
    {"id":"SL250","name":"도봉1동","gu":"도봉구","city":"서울","lat":37.6851,"lon":127.0268,"drainage_capacity":100.0,"impervious_ratio":0.114,"topo_depression":0.273,"flood_history":0.0},
    {"id":"SL251","name":"도봉2동","gu":"도봉구","city":"서울","lat":37.6812,"lon":127.0478,"drainage_capacity":100.0,"impervious_ratio":0.681,"topo_depression":0.923,"flood_history":0.0},
    {"id":"SL252","name":"월계1동","gu":"노원구","city":"서울","lat":37.6218,"lon":127.0586,"drainage_capacity":100.0,"impervious_ratio":0.571,"topo_depression":0.923,"flood_history":0.0},
    {"id":"SL253","name":"월계2동","gu":"노원구","city":"서울","lat":37.6341,"lon":127.0512,"drainage_capacity":100.0,"impervious_ratio":0.337,"topo_depression":0.862,"flood_history":0.0},
    {"id":"SL254","name":"월계3동","gu":"노원구","city":"서울","lat":37.6247,"lon":127.0649,"drainage_capacity":100.0,"impervious_ratio":0.613,"topo_depression":0.968,"flood_history":0.0},
    {"id":"SL255","name":"공릉2동","gu":"노원구","city":"서울","lat":37.6316,"lon":127.0942,"drainage_capacity":100.0,"impervious_ratio":0.225,"topo_depression":0.83,"flood_history":0.0},
    {"id":"SL256","name":"하계1동","gu":"노원구","city":"서울","lat":37.6386,"lon":127.0748,"drainage_capacity":100.0,"impervious_ratio":0.539,"topo_depression":0.884,"flood_history":0.0},
    {"id":"SL257","name":"하계2동","gu":"노원구","city":"서울","lat":37.6348,"lon":127.0648,"drainage_capacity":100.0,"impervious_ratio":0.742,"topo_depression":0.956,"flood_history":0.0},
    {"id":"SL258","name":"중계본동","gu":"노원구","city":"서울","lat":37.6481,"lon":127.0858,"drainage_capacity":100.0,"impervious_ratio":0.344,"topo_depression":0.574,"flood_history":0.0},
    {"id":"SL259","name":"중계1동","gu":"노원구","city":"서울","lat":37.65,"lon":127.0735,"drainage_capacity":100.0,"impervious_ratio":0.803,"topo_depression":0.899,"flood_history":0.0},
    {"id":"SL260","name":"중계4동","gu":"노원구","city":"서울","lat":37.6588,"lon":127.0822,"drainage_capacity":100.0,"impervious_ratio":0.253,"topo_depression":0.469,"flood_history":0.0},
    {"id":"SL261","name":"상계5동","gu":"노원구","city":"서울","lat":37.6632,"lon":127.0696,"drainage_capacity":100.0,"impervious_ratio":0.932,"topo_depression":0.878,"flood_history":0.0},
    {"id":"SL262","name":"상계8동","gu":"노원구","city":"서울","lat":37.6663,"lon":127.0537,"drainage_capacity":100.0,"impervious_ratio":0.654,"topo_depression":0.936,"flood_history":0.0},
    {"id":"SL263","name":"상계9동","gu":"노원구","city":"서울","lat":37.6681,"lon":127.0625,"drainage_capacity":100.0,"impervious_ratio":0.547,"topo_depression":0.793,"flood_history":0.0},
    {"id":"SL264","name":"상계10동","gu":"노원구","city":"서울","lat":37.6596,"lon":127.0584,"drainage_capacity":100.0,"impervious_ratio":0.696,"topo_depression":0.931,"flood_history":0.0},
    {"id":"SL265","name":"상계6·7동","gu":"노원구","city":"서울","lat":37.6487,"lon":127.0601,"drainage_capacity":100.0,"impervious_ratio":0.637,"topo_depression":0.945,"flood_history":0.0},
    {"id":"SL266","name":"중계2·3동","gu":"노원구","city":"서울","lat":37.6433,"lon":127.0659,"drainage_capacity":100.0,"impervious_ratio":0.707,"topo_depression":0.942,"flood_history":0.0},
    {"id":"SL267","name":"공릉1동","gu":"노원구","city":"서울","lat":37.6241,"lon":127.0728,"drainage_capacity":100.0,"impervious_ratio":0.776,"topo_depression":0.957,"flood_history":0.0},
    {"id":"SL268","name":"녹번동","gu":"은평구","city":"서울","lat":37.6054,"lon":126.935,"drainage_capacity":100.0,"impervious_ratio":0.553,"topo_depression":0.712,"flood_history":0.0},
    {"id":"SL269","name":"구산동","gu":"은평구","city":"서울","lat":37.6111,"lon":126.9076,"drainage_capacity":100.0,"impervious_ratio":0.53,"topo_depression":0.821,"flood_history":0.0},
    {"id":"SL270","name":"대조동","gu":"은평구","city":"서울","lat":37.6123,"lon":126.9231,"drainage_capacity":100.0,"impervious_ratio":0.841,"topo_depression":0.923,"flood_history":0.0},
    {"id":"SL271","name":"응암2동","gu":"은평구","city":"서울","lat":37.5919,"lon":126.923,"drainage_capacity":100.0,"impervious_ratio":0.789,"topo_depression":0.735,"flood_history":0.0},
    {"id":"SL272","name":"신사1동","gu":"은평구","city":"서울","lat":37.599,"lon":126.9088,"drainage_capacity":100.0,"impervious_ratio":0.733,"topo_depression":0.871,"flood_history":0.0},
    {"id":"SL273","name":"신사2동","gu":"은평구","city":"서울","lat":37.5929,"lon":126.9063,"drainage_capacity":100.0,"impervious_ratio":0.468,"topo_depression":0.821,"flood_history":0.0},
    {"id":"SL274","name":"증산동","gu":"은평구","city":"서울","lat":37.5838,"lon":126.9058,"drainage_capacity":100.0,"impervious_ratio":0.726,"topo_depression":0.946,"flood_history":0.0},
    {"id":"SL275","name":"수색동","gu":"은평구","city":"서울","lat":37.5858,"lon":126.8949,"drainage_capacity":100.0,"impervious_ratio":0.539,"topo_depression":0.879,"flood_history":0.0},
    {"id":"SL276","name":"진관동","gu":"은평구","city":"서울","lat":37.6393,"lon":126.9405,"drainage_capacity":100.0,"impervious_ratio":0.203,"topo_depression":0.443,"flood_history":0.0},
    {"id":"SL277","name":"천연동","gu":"서대문구","city":"서울","lat":37.5712,"lon":126.9571,"drainage_capacity":100.0,"impervious_ratio":0.427,"topo_depression":0.748,"flood_history":0.0},
    {"id":"SL278","name":"홍제1동","gu":"서대문구","city":"서울","lat":37.5815,"lon":126.9452,"drainage_capacity":100.0,"impervious_ratio":0.412,"topo_depression":0.645,"flood_history":0.0},
    {"id":"SL279","name":"홍제3동","gu":"서대문구","city":"서울","lat":37.592,"lon":126.9512,"drainage_capacity":100.0,"impervious_ratio":0.508,"topo_depression":0.584,"flood_history":0.0},
    {"id":"SL280","name":"홍제2동","gu":"서대문구","city":"서울","lat":37.5845,"lon":126.9525,"drainage_capacity":100.0,"impervious_ratio":0.398,"topo_depression":0.541,"flood_history":0.0},
    {"id":"SL281","name":"홍은1동","gu":"서대문구","city":"서울","lat":37.6,"lon":126.947,"drainage_capacity":100.0,"impervious_ratio":0.386,"topo_depression":0.68,"flood_history":0.0},
    {"id":"SL282","name":"홍은2동","gu":"서대문구","city":"서울","lat":37.587,"lon":126.9322,"drainage_capacity":100.0,"impervious_ratio":0.47,"topo_depression":0.75,"flood_history":0.0},
    {"id":"SL283","name":"남가좌1동","gu":"서대문구","city":"서울","lat":37.5717,"lon":126.9162,"drainage_capacity":100.0,"impervious_ratio":0.836,"topo_depression":0.961,"flood_history":0.0},
    {"id":"SL284","name":"남가좌2동","gu":"서대문구","city":"서울","lat":37.5776,"lon":126.9213,"drainage_capacity":100.0,"impervious_ratio":0.847,"topo_depression":0.923,"flood_history":0.0},
    {"id":"SL285","name":"북가좌1동","gu":"서대문구","city":"서울","lat":37.5753,"lon":126.908,"drainage_capacity":100.0,"impervious_ratio":0.8,"topo_depression":0.952,"flood_history":0.0},
    {"id":"SL286","name":"충현동","gu":"서대문구","city":"서울","lat":37.5639,"lon":126.9581,"drainage_capacity":100.0,"impervious_ratio":0.727,"topo_depression":0.789,"flood_history":0.0},
    {"id":"SL287","name":"북아현동","gu":"서대문구","city":"서울","lat":37.5592,"lon":126.9555,"drainage_capacity":100.0,"impervious_ratio":0.927,"topo_depression":0.828,"flood_history":0.0},
    {"id":"SL288","name":"신촌동","gu":"서대문구","city":"서울","lat":37.5636,"lon":126.9411,"drainage_capacity":100.0,"impervious_ratio":0.456,"topo_depression":0.78,"flood_history":0.0},
    {"id":"SL289","name":"연희동","gu":"서대문구","city":"서울","lat":37.572,"lon":126.9327,"drainage_capacity":100.0,"impervious_ratio":0.598,"topo_depression":0.789,"flood_history":0.0},
    {"id":"SL290","name":"용강동","gu":"마포구","city":"서울","lat":37.5406,"lon":126.9413,"drainage_capacity":100.0,"impervious_ratio":0.653,"topo_depression":0.995,"flood_history":0.0},
    {"id":"SL291","name":"대흥동","gu":"마포구","city":"서울","lat":37.5521,"lon":126.9414,"drainage_capacity":100.0,"impervious_ratio":0.604,"topo_depression":0.886,"flood_history":0.0},
    {"id":"SL292","name":"염리동","gu":"마포구","city":"서울","lat":37.5498,"lon":126.9475,"drainage_capacity":100.0,"impervious_ratio":0.821,"topo_depression":0.873,"flood_history":0.0},
    {"id":"SL293","name":"신수동","gu":"마포구","city":"서울","lat":37.5436,"lon":126.9336,"drainage_capacity":100.0,"impervious_ratio":0.529,"topo_depression":0.988,"flood_history":0.0},
    {"id":"SL294","name":"서교동","gu":"마포구","city":"서울","lat":37.5548,"lon":126.9209,"drainage_capacity":100.0,"impervious_ratio":0.96,"topo_depression":0.974,"flood_history":0.0},
    {"id":"SL295","name":"합정동","gu":"마포구","city":"서울","lat":37.5469,"lon":126.9088,"drainage_capacity":100.0,"impervious_ratio":0.461,"topo_depression":0.987,"flood_history":0.0},
    {"id":"SL296","name":"망원1동","gu":"마포구","city":"서울","lat":37.5528,"lon":126.9002,"drainage_capacity":100.0,"impervious_ratio":0.507,"topo_depression":0.999,"flood_history":0.0},
    {"id":"SL297","name":"망원2동","gu":"마포구","city":"서울","lat":37.5571,"lon":126.8957,"drainage_capacity":100.0,"impervious_ratio":0.521,"topo_depression":0.999,"flood_history":0.0},
    {"id":"SL298","name":"연남동","gu":"마포구","city":"서울","lat":37.563,"lon":126.9215,"drainage_capacity":100.0,"impervious_ratio":0.831,"topo_depression":0.987,"flood_history":0.0},
    {"id":"SL299","name":"성산1동","gu":"마포구","city":"서울","lat":37.562,"lon":126.9118,"drainage_capacity":100.0,"impervious_ratio":0.785,"topo_depression":0.968,"flood_history":0.0},
    {"id":"SL300","name":"성산2동","gu":"마포구","city":"서울","lat":37.5681,"lon":126.902,"drainage_capacity":100.0,"impervious_ratio":0.652,"topo_depression":0.97,"flood_history":0.0},
    {"id":"SL301","name":"상암동","gu":"마포구","city":"서울","lat":37.5718,"lon":126.8809,"drainage_capacity":100.0,"impervious_ratio":0.296,"topo_depression":0.939,"flood_history":0.0},
    {"id":"SL302","name":"도화동","gu":"마포구","city":"서울","lat":37.537,"lon":126.9468,"drainage_capacity":100.0,"impervious_ratio":0.613,"topo_depression":0.949,"flood_history":0.0},
    {"id":"SL303","name":"서강동","gu":"마포구","city":"서울","lat":37.5459,"lon":126.9252,"drainage_capacity":100.0,"impervious_ratio":0.488,"topo_depression":0.963,"flood_history":0.0},
    {"id":"SL304","name":"공덕동","gu":"마포구","city":"서울","lat":37.5491,"lon":126.9578,"drainage_capacity":100.0,"impervious_ratio":0.85,"topo_depression":0.866,"flood_history":0.0},
    {"id":"SL305","name":"아현동","gu":"마포구","city":"서울","lat":37.5519,"lon":126.9528,"drainage_capacity":100.0,"impervious_ratio":0.878,"topo_depression":0.903,"flood_history":0.0},
    {"id":"SL306","name":"목1동","gu":"양천구","city":"서울","lat":37.5274,"lon":126.8751,"drainage_capacity":100.0,"impervious_ratio":0.661,"topo_depression":1.0,"flood_history":0.0},
    {"id":"SL307","name":"목2동","gu":"양천구","city":"서울","lat":37.5436,"lon":126.8741,"drainage_capacity":100.0,"impervious_ratio":0.711,"topo_depression":0.945,"flood_history":0.0},
    {"id":"SL308","name":"목3동","gu":"양천구","city":"서울","lat":37.5452,"lon":126.8654,"drainage_capacity":100.0,"impervious_ratio":0.967,"topo_depression":0.946,"flood_history":0.0},
    {"id":"SL309","name":"목4동","gu":"양천구","city":"서울","lat":37.5354,"lon":126.8669,"drainage_capacity":100.0,"impervious_ratio":0.957,"topo_depression":0.976,"flood_history":0.0},
    {"id":"SL310","name":"신월1동","gu":"양천구","city":"서울","lat":37.5313,"lon":126.8345,"drainage_capacity":100.0,"impervious_ratio":0.962,"topo_depression":0.989,"flood_history":0.0},
    {"id":"SL311","name":"신월2동","gu":"양천구","city":"서울","lat":37.5234,"lon":126.8463,"drainage_capacity":100.0,"impervious_ratio":0.844,"topo_depression":0.947,"flood_history":0.0},
    {"id":"SL312","name":"신월3동","gu":"양천구","city":"서울","lat":37.5324,"lon":126.8275,"drainage_capacity":100.0,"impervious_ratio":0.527,"topo_depression":0.936,"flood_history":0.0},
    {"id":"SL313","name":"신월4동","gu":"양천구","city":"서울","lat":37.5222,"lon":126.8398,"drainage_capacity":100.0,"impervious_ratio":0.927,"topo_depression":0.987,"flood_history":0.0},
    {"id":"SL314","name":"신월5동","gu":"양천구","city":"서울","lat":37.54,"lon":126.8299,"drainage_capacity":100.0,"impervious_ratio":0.873,"topo_depression":0.954,"flood_history":0.0},
    {"id":"SL315","name":"신월6동","gu":"양천구","city":"서울","lat":37.516,"lon":126.8421,"drainage_capacity":100.0,"impervious_ratio":0.724,"topo_depression":0.933,"flood_history":0.0},
    {"id":"SL316","name":"신월7동","gu":"양천구","city":"서울","lat":37.5207,"lon":126.8323,"drainage_capacity":100.0,"impervious_ratio":0.642,"topo_depression":0.893,"flood_history":0.0},
    {"id":"SL317","name":"신정1동","gu":"양천구","city":"서울","lat":37.5189,"lon":126.8596,"drainage_capacity":100.0,"impervious_ratio":0.912,"topo_depression":0.997,"flood_history":0.0},
    {"id":"SL318","name":"신정2동","gu":"양천구","city":"서울","lat":37.519,"lon":126.8752,"drainage_capacity":100.0,"impervious_ratio":0.709,"topo_depression":1.0,"flood_history":0.0},
    {"id":"SL319","name":"신정3동","gu":"양천구","city":"서울","lat":37.5118,"lon":126.8394,"drainage_capacity":100.0,"impervious_ratio":0.462,"topo_depression":0.877,"flood_history":0.0},
    {"id":"SL320","name":"신정6동","gu":"양천구","city":"서울","lat":37.5159,"lon":126.8696,"drainage_capacity":100.0,"impervious_ratio":0.766,"topo_depression":1.0,"flood_history":0.0},
    {"id":"SL321","name":"신정7동","gu":"양천구","city":"서울","lat":37.5101,"lon":126.8647,"drainage_capacity":100.0,"impervious_ratio":0.727,"topo_depression":0.966,"flood_history":0.0},
    {"id":"SL322","name":"목5동","gu":"양천구","city":"서울","lat":37.5363,"lon":126.881,"drainage_capacity":100.0,"impervious_ratio":0.617,"topo_depression":1.0,"flood_history":0.0},
    {"id":"SL323","name":"신정4동","gu":"양천구","city":"서울","lat":37.5254,"lon":126.8576,"drainage_capacity":100.0,"impervious_ratio":0.934,"topo_depression":0.984,"flood_history":0.0},
    {"id":"SL324","name":"염창동","gu":"강서구","city":"서울","lat":37.5532,"lon":126.8754,"drainage_capacity":100.0,"impervious_ratio":0.475,"topo_depression":0.984,"flood_history":0.0},
    {"id":"SL325","name":"등촌1동","gu":"강서구","city":"서울","lat":37.5559,"lon":126.8596,"drainage_capacity":100.0,"impervious_ratio":0.963,"topo_depression":0.992,"flood_history":0.0},
    {"id":"SL326","name":"등촌2동","gu":"강서구","city":"서울","lat":37.5457,"lon":126.86,"drainage_capacity":100.0,"impervious_ratio":0.542,"topo_depression":0.906,"flood_history":0.0},
    {"id":"SL327","name":"등촌3동","gu":"강서구","city":"서울","lat":37.5611,"lon":126.8463,"drainage_capacity":100.0,"impervious_ratio":0.789,"topo_depression":0.999,"flood_history":0.0},
    {"id":"SL328","name":"화곡본동","gu":"강서구","city":"서울","lat":37.5426,"lon":126.8482,"drainage_capacity":100.0,"impervious_ratio":0.719,"topo_depression":0.855,"flood_history":0.0},
    {"id":"SL329","name":"화곡2동","gu":"강서구","city":"서울","lat":37.5323,"lon":126.8544,"drainage_capacity":100.0,"impervious_ratio":0.907,"topo_depression":0.952,"flood_history":0.0},
    {"id":"SL330","name":"화곡3동","gu":"강서구","city":"서울","lat":37.5441,"lon":126.8343,"drainage_capacity":100.0,"impervious_ratio":0.969,"topo_depression":0.947,"flood_history":0.0},
    {"id":"SL331","name":"화곡4동","gu":"강서구","city":"서울","lat":37.5361,"lon":126.8586,"drainage_capacity":100.0,"impervious_ratio":0.651,"topo_depression":0.902,"flood_history":0.0},
    {"id":"SL332","name":"화곡6동","gu":"강서구","city":"서울","lat":37.5517,"lon":126.8512,"drainage_capacity":100.0,"impervious_ratio":0.689,"topo_depression":0.944,"flood_history":0.0},
    {"id":"SL333","name":"화곡8동","gu":"강서구","city":"서울","lat":37.5342,"lon":126.8486,"drainage_capacity":100.0,"impervious_ratio":0.957,"topo_depression":0.914,"flood_history":0.0},
    {"id":"SL334","name":"가양1동","gu":"강서구","city":"서울","lat":37.5731,"lon":126.8343,"drainage_capacity":100.0,"impervious_ratio":0.381,"topo_depression":0.995,"flood_history":0.0},
    {"id":"SL335","name":"가양2동","gu":"강서구","city":"서울","lat":37.5687,"lon":126.854,"drainage_capacity":100.0,"impervious_ratio":0.351,"topo_depression":0.996,"flood_history":0.0},
    {"id":"SL336","name":"가양3동","gu":"강서구","city":"서울","lat":37.5627,"lon":126.8623,"drainage_capacity":100.0,"impervious_ratio":0.404,"topo_depression":0.996,"flood_history":0.0},
    {"id":"SL337","name":"발산1동","gu":"강서구","city":"서울","lat":37.5504,"lon":126.8256,"drainage_capacity":100.0,"impervious_ratio":0.553,"topo_depression":0.966,"flood_history":0.0},
    {"id":"SL338","name":"공항동","gu":"강서구","city":"서울","lat":37.5565,"lon":126.795,"drainage_capacity":100.0,"impervious_ratio":0.541,"topo_depression":0.993,"flood_history":0.0},
    {"id":"SL339","name":"방화1동","gu":"강서구","city":"서울","lat":37.5686,"lon":126.8176,"drainage_capacity":100.0,"impervious_ratio":0.764,"topo_depression":0.995,"flood_history":0.0},
    {"id":"SL340","name":"방화3동","gu":"강서구","city":"서울","lat":37.5816,"lon":126.8155,"drainage_capacity":100.0,"impervious_ratio":0.318,"topo_depression":0.958,"flood_history":0.0},
    {"id":"SL341","name":"화곡1동","gu":"강서구","city":"서울","lat":37.5338,"lon":126.8409,"drainage_capacity":100.0,"impervious_ratio":0.946,"topo_depression":0.959,"flood_history":0.0},
    {"id":"SL342","name":"우장산동","gu":"강서구","city":"서울","lat":37.5506,"lon":126.841,"drainage_capacity":100.0,"impervious_ratio":0.771,"topo_depression":0.917,"flood_history":0.0},
    {"id":"SL343","name":"신도림동","gu":"구로구","city":"서울","lat":37.5097,"lon":126.8828,"drainage_capacity":100.0,"impervious_ratio":0.75,"topo_depression":0.998,"flood_history":0.0},
    {"id":"SL344","name":"구로1동","gu":"구로구","city":"서울","lat":37.493,"lon":126.8755,"drainage_capacity":100.0,"impervious_ratio":0.642,"topo_depression":0.997,"flood_history":0.0},
    {"id":"SL345","name":"고척1동","gu":"구로구","city":"서울","lat":37.5007,"lon":126.8634,"drainage_capacity":100.0,"impervious_ratio":0.723,"topo_depression":0.976,"flood_history":0.0},
    {"id":"SL346","name":"고척2동","gu":"구로구","city":"서울","lat":37.5059,"lon":126.8533,"drainage_capacity":100.0,"impervious_ratio":0.639,"topo_depression":0.932,"flood_history":0.0},
    {"id":"SL347","name":"오류1동","gu":"구로구","city":"서울","lat":37.497,"lon":126.8416,"drainage_capacity":100.0,"impervious_ratio":0.728,"topo_depression":0.922,"flood_history":0.0},
    {"id":"SL348","name":"항동","gu":"구로구","city":"서울","lat":37.481,"lon":126.8245,"drainage_capacity":100.0,"impervious_ratio":0.462,"topo_depression":0.862,"flood_history":0.0},
    {"id":"SL349","name":"수궁동","gu":"구로구","city":"서울","lat":37.4983,"lon":126.8261,"drainage_capacity":100.0,"impervious_ratio":0.457,"topo_depression":0.859,"flood_history":0.0},
    {"id":"SL350","name":"독산4동","gu":"금천구","city":"서울","lat":37.4692,"lon":126.9041,"drainage_capacity":100.0,"impervious_ratio":0.782,"topo_depression":0.847,"flood_history":0.0},
    {"id":"SL351","name":"시흥2동","gu":"금천구","city":"서울","lat":37.4506,"lon":126.9201,"drainage_capacity":100.0,"impervious_ratio":0.299,"topo_depression":0.336,"flood_history":0.0},
    {"id":"SL352","name":"시흥3동","gu":"금천구","city":"서울","lat":37.4403,"lon":126.9059,"drainage_capacity":100.0,"impervious_ratio":0.491,"topo_depression":0.786,"flood_history":0.0},
    {"id":"SL353","name":"여의동","gu":"영등포구","city":"서울","lat":37.5275,"lon":126.9276,"drainage_capacity":100.0,"impervious_ratio":0.371,"topo_depression":0.991,"flood_history":0.0},
    {"id":"SL354","name":"당산2동","gu":"영등포구","city":"서울","lat":37.533,"lon":126.9039,"drainage_capacity":100.0,"impervious_ratio":0.626,"topo_depression":0.993,"flood_history":0.0},
    {"id":"SL355","name":"양평2동","gu":"영등포구","city":"서울","lat":37.5406,"lon":126.8942,"drainage_capacity":100.0,"impervious_ratio":0.521,"topo_depression":0.996,"flood_history":0.0},
    {"id":"SL356","name":"청림동","gu":"관악구","city":"서울","lat":37.4894,"lon":126.9596,"drainage_capacity":100.0,"impervious_ratio":0.897,"topo_depression":0.712,"flood_history":0.0},
    {"id":"SL357","name":"난향동","gu":"관악구","city":"서울","lat":37.4616,"lon":126.9183,"drainage_capacity":100.0,"impervious_ratio":0.398,"topo_depression":0.574,"flood_history":0.0},
    {"id":"SL358","name":"대학동","gu":"관악구","city":"서울","lat":37.4535,"lon":126.9485,"drainage_capacity":100.0,"impervious_ratio":0.097,"topo_depression":0.14,"flood_history":0.0},
    {"id":"SL359","name":"성현동","gu":"관악구","city":"서울","lat":37.4895,"lon":126.9512,"drainage_capacity":100.0,"impervious_ratio":0.747,"topo_depression":0.709,"flood_history":0.0},
    {"id":"SL360","name":"잠원동","gu":"서초구","city":"서울","lat":37.5176,"lon":127.013,"drainage_capacity":100.0,"impervious_ratio":0.502,"topo_depression":0.975,"flood_history":0.0},
    {"id":"SL361","name":"반포본동","gu":"서초구","city":"서울","lat":37.5063,"lon":126.9865,"drainage_capacity":100.0,"impervious_ratio":0.144,"topo_depression":0.989,"flood_history":0.0},
    {"id":"SL362","name":"반포2동","gu":"서초구","city":"서울","lat":37.5064,"lon":126.9957,"drainage_capacity":100.0,"impervious_ratio":0.526,"topo_depression":0.985,"flood_history":0.0},
    {"id":"SL363","name":"반포3동","gu":"서초구","city":"서울","lat":37.5124,"lon":127.0036,"drainage_capacity":100.0,"impervious_ratio":0.466,"topo_depression":0.991,"flood_history":0.0},
    {"id":"SL364","name":"반포4동","gu":"서초구","city":"서울","lat":37.4996,"lon":127.0033,"drainage_capacity":100.0,"impervious_ratio":0.726,"topo_depression":0.916,"flood_history":0.0},
    {"id":"SL365","name":"방배3동","gu":"서초구","city":"서울","lat":37.4743,"lon":126.9979,"drainage_capacity":100.0,"impervious_ratio":0.304,"topo_depression":0.643,"flood_history":0.0},
    {"id":"SL366","name":"신사동","gu":"강남구","city":"서울","lat":37.5257,"lon":127.0214,"drainage_capacity":100.0,"impervious_ratio":0.557,"topo_depression":0.974,"flood_history":0.0},
    {"id":"SL367","name":"논현2동","gu":"강남구","city":"서울","lat":37.5152,"lon":127.0362,"drainage_capacity":100.0,"impervious_ratio":0.971,"topo_depression":0.843,"flood_history":0.0},
    {"id":"SL368","name":"삼성1동","gu":"강남구","city":"서울","lat":37.5154,"lon":127.0606,"drainage_capacity":100.0,"impervious_ratio":0.674,"topo_depression":0.94,"flood_history":0.0},
    {"id":"SL369","name":"삼성2동","gu":"강남구","city":"서울","lat":37.5118,"lon":127.0488,"drainage_capacity":100.0,"impervious_ratio":0.77,"topo_depression":0.9,"flood_history":0.0},
    {"id":"SL370","name":"대치1동","gu":"강남구","city":"서울","lat":37.4934,"lon":127.059,"drainage_capacity":100.0,"impervious_ratio":0.707,"topo_depression":0.975,"flood_history":0.0},
    {"id":"SL371","name":"대치4동","gu":"강남구","city":"서울","lat":37.5017,"lon":127.0549,"drainage_capacity":100.0,"impervious_ratio":0.977,"topo_depression":0.945,"flood_history":0.0},
    {"id":"SL372","name":"역삼2동","gu":"강남구","city":"서울","lat":37.4985,"lon":127.0449,"drainage_capacity":100.0,"impervious_ratio":0.899,"topo_depression":0.91,"flood_history":0.0},
    {"id":"SL373","name":"도곡1동","gu":"강남구","city":"서울","lat":37.489,"lon":127.041,"drainage_capacity":100.0,"impervious_ratio":0.593,"topo_depression":0.903,"flood_history":0.0},
    {"id":"SL374","name":"도곡2동","gu":"강남구","city":"서울","lat":37.4882,"lon":127.0497,"drainage_capacity":100.0,"impervious_ratio":0.717,"topo_depression":0.964,"flood_history":0.0},
    {"id":"SL375","name":"개포1동","gu":"강남구","city":"서울","lat":37.4793,"lon":127.0647,"drainage_capacity":100.0,"impervious_ratio":0.46,"topo_depression":0.777,"flood_history":0.0},
    {"id":"SL376","name":"일원본동","gu":"강남구","city":"서울","lat":37.4824,"lon":127.0847,"drainage_capacity":100.0,"impervious_ratio":0.284,"topo_depression":0.703,"flood_history":0.0},
    {"id":"SL377","name":"일원1동","gu":"강남구","city":"서울","lat":37.4934,"lon":127.0892,"drainage_capacity":100.0,"impervious_ratio":0.614,"topo_depression":0.965,"flood_history":0.0},
    {"id":"SL378","name":"일원2동","gu":"강남구","city":"서울","lat":37.4955,"lon":127.0793,"drainage_capacity":100.0,"impervious_ratio":0.562,"topo_depression":0.966,"flood_history":0.0},
    {"id":"SL379","name":"수서동","gu":"강남구","city":"서울","lat":37.4868,"lon":127.1006,"drainage_capacity":100.0,"impervious_ratio":0.401,"topo_depression":0.928,"flood_history":0.0},
    {"id":"SL380","name":"압구정동","gu":"강남구","city":"서울","lat":37.5303,"lon":127.0335,"drainage_capacity":100.0,"impervious_ratio":0.595,"topo_depression":0.964,"flood_history":0.0},
    {"id":"SL381","name":"청담동","gu":"강남구","city":"서울","lat":37.5245,"lon":127.0505,"drainage_capacity":100.0,"impervious_ratio":0.637,"topo_depression":0.934,"flood_history":0.0},
    {"id":"SL382","name":"대치2동","gu":"강남구","city":"서울","lat":37.5006,"lon":127.0664,"drainage_capacity":100.0,"impervious_ratio":0.725,"topo_depression":0.963,"flood_history":0.0},
    {"id":"SL383","name":"개포2동","gu":"강남구","city":"서울","lat":37.4865,"lon":127.0676,"drainage_capacity":100.0,"impervious_ratio":0.568,"topo_depression":0.915,"flood_history":0.0},
    {"id":"SL384","name":"풍납1동","gu":"송파구","city":"서울","lat":37.5382,"lon":127.1143,"drainage_capacity":100.0,"impervious_ratio":0.348,"topo_depression":0.982,"flood_history":0.0},
    {"id":"SL385","name":"풍납2동","gu":"송파구","city":"서울","lat":37.5299,"lon":127.1101,"drainage_capacity":100.0,"impervious_ratio":0.441,"topo_depression":0.982,"flood_history":0.0},
    {"id":"SL386","name":"거여1동","gu":"송파구","city":"서울","lat":37.4944,"lon":127.1417,"drainage_capacity":100.0,"impervious_ratio":0.623,"topo_depression":0.894,"flood_history":0.0},
    {"id":"SL387","name":"거여2동","gu":"송파구","city":"서울","lat":37.4924,"lon":127.1472,"drainage_capacity":100.0,"impervious_ratio":0.906,"topo_depression":0.874,"flood_history":0.0},
    {"id":"SL388","name":"마천2동","gu":"송파구","city":"서울","lat":37.5003,"lon":127.1515,"drainage_capacity":100.0,"impervious_ratio":0.667,"topo_depression":0.872,"flood_history":0.0},
    {"id":"SL389","name":"방이1동","gu":"송파구","city":"서울","lat":37.5098,"lon":127.1223,"drainage_capacity":100.0,"impervious_ratio":0.859,"topo_depression":0.936,"flood_history":0.0},
    {"id":"SL390","name":"오륜동","gu":"송파구","city":"서울","lat":37.5177,"lon":127.1285,"drainage_capacity":100.0,"impervious_ratio":0.499,"topo_depression":0.957,"flood_history":0.0},
    {"id":"SL391","name":"오금동","gu":"송파구","city":"서울","lat":37.504,"lon":127.1344,"drainage_capacity":100.0,"impervious_ratio":0.676,"topo_depression":0.927,"flood_history":0.0},
    {"id":"SL392","name":"송파2동","gu":"송파구","city":"서울","lat":37.5028,"lon":127.1168,"drainage_capacity":100.0,"impervious_ratio":0.704,"topo_depression":0.931,"flood_history":0.0},
    {"id":"SL393","name":"삼전동","gu":"송파구","city":"서울","lat":37.5017,"lon":127.0919,"drainage_capacity":100.0,"impervious_ratio":0.717,"topo_depression":0.983,"flood_history":0.0},
    {"id":"SL394","name":"가락본동","gu":"송파구","city":"서울","lat":37.4972,"lon":127.1216,"drainage_capacity":100.0,"impervious_ratio":0.822,"topo_depression":0.927,"flood_history":0.0},
    {"id":"SL395","name":"가락1동","gu":"송파구","city":"서울","lat":37.4953,"lon":127.1082,"drainage_capacity":100.0,"impervious_ratio":0.683,"topo_depression":0.981,"flood_history":0.0},
    {"id":"SL396","name":"가락2동","gu":"송파구","city":"서울","lat":37.4959,"lon":127.1306,"drainage_capacity":100.0,"impervious_ratio":0.797,"topo_depression":0.88,"flood_history":0.0},
    {"id":"SL397","name":"문정1동","gu":"송파구","city":"서울","lat":37.4882,"lon":127.1269,"drainage_capacity":100.0,"impervious_ratio":0.878,"topo_depression":0.923,"flood_history":0.0},
    {"id":"SL398","name":"문정2동","gu":"송파구","city":"서울","lat":37.4807,"lon":127.1191,"drainage_capacity":100.0,"impervious_ratio":0.633,"topo_depression":0.97,"flood_history":0.0},
    {"id":"SL399","name":"잠실본동","gu":"송파구","city":"서울","lat":37.5055,"lon":127.0823,"drainage_capacity":100.0,"impervious_ratio":0.741,"topo_depression":0.984,"flood_history":0.0},
    {"id":"SL400","name":"잠실4동","gu":"송파구","city":"서울","lat":37.5213,"lon":127.1082,"drainage_capacity":100.0,"impervious_ratio":0.52,"topo_depression":0.979,"flood_history":0.0},
    {"id":"SL401","name":"잠실6동","gu":"송파구","city":"서울","lat":37.5191,"lon":127.1,"drainage_capacity":100.0,"impervious_ratio":0.462,"topo_depression":0.985,"flood_history":0.0},
    {"id":"SL402","name":"잠실7동","gu":"송파구","city":"서울","lat":37.5075,"lon":127.0741,"drainage_capacity":100.0,"impervious_ratio":0.5,"topo_depression":0.975,"flood_history":0.0},
    {"id":"SL403","name":"잠실2동","gu":"송파구","city":"서울","lat":37.5177,"lon":127.0788,"drainage_capacity":100.0,"impervious_ratio":0.332,"topo_depression":0.983,"flood_history":0.0},
    {"id":"SL404","name":"잠실3동","gu":"송파구","city":"서울","lat":37.5136,"lon":127.0943,"drainage_capacity":100.0,"impervious_ratio":0.658,"topo_depression":0.981,"flood_history":0.0},
    {"id":"SL405","name":"장지동","gu":"송파구","city":"서울","lat":37.4828,"lon":127.1316,"drainage_capacity":100.0,"impervious_ratio":0.675,"topo_depression":0.92,"flood_history":0.0},
    {"id":"SL406","name":"위례동","gu":"송파구","city":"서울","lat":37.4817,"lon":127.1412,"drainage_capacity":100.0,"impervious_ratio":0.483,"topo_depression":0.89,"flood_history":0.0},
    {"id":"SL407","name":"강일동","gu":"강동구","city":"서울","lat":37.5639,"lon":127.174,"drainage_capacity":100.0,"impervious_ratio":0.545,"topo_depression":0.945,"flood_history":0.0},
    {"id":"SL408","name":"상일동","gu":"강동구","city":"서울","lat":37.5507,"lon":127.1648,"drainage_capacity":100.0,"impervious_ratio":0.559,"topo_depression":0.899,"flood_history":0.0},
    {"id":"SL409","name":"명일1동","gu":"강동구","city":"서울","lat":37.5504,"lon":127.1459,"drainage_capacity":100.0,"impervious_ratio":0.859,"topo_depression":0.917,"flood_history":0.0},
    {"id":"SL410","name":"명일2동","gu":"강동구","city":"서울","lat":37.5483,"lon":127.1542,"drainage_capacity":100.0,"impervious_ratio":0.513,"topo_depression":0.884,"flood_history":0.0},
    {"id":"SL411","name":"고덕1동","gu":"강동구","city":"서울","lat":37.5633,"lon":127.1503,"drainage_capacity":100.0,"impervious_ratio":0.452,"topo_depression":0.893,"flood_history":0.0},
    {"id":"SL412","name":"고덕2동","gu":"강동구","city":"서울","lat":37.5659,"lon":127.1616,"drainage_capacity":100.0,"impervious_ratio":0.408,"topo_depression":0.941,"flood_history":0.0},
    {"id":"SL413","name":"암사2동","gu":"강동구","city":"서울","lat":37.5574,"lon":127.1232,"drainage_capacity":100.0,"impervious_ratio":0.238,"topo_depression":0.985,"flood_history":0.0},
    {"id":"SL414","name":"암사3동","gu":"강동구","city":"서울","lat":37.5615,"lon":127.1385,"drainage_capacity":100.0,"impervious_ratio":0.455,"topo_depression":0.903,"flood_history":0.0},
    {"id":"SL415","name":"천호1동","gu":"강동구","city":"서울","lat":37.5463,"lon":127.1386,"drainage_capacity":100.0,"impervious_ratio":0.895,"topo_depression":0.933,"flood_history":0.0},
    {"id":"SL416","name":"천호3동","gu":"강동구","city":"서울","lat":37.5397,"lon":127.1332,"drainage_capacity":100.0,"impervious_ratio":0.922,"topo_depression":0.948,"flood_history":0.0},
    {"id":"SL417","name":"성내1동","gu":"강동구","city":"서울","lat":37.5288,"lon":127.1255,"drainage_capacity":100.0,"impervious_ratio":0.889,"topo_depression":0.981,"flood_history":0.0},
    {"id":"SL418","name":"성내2동","gu":"강동구","city":"서울","lat":37.5344,"lon":127.1277,"drainage_capacity":100.0,"impervious_ratio":0.961,"topo_depression":0.966,"flood_history":0.0},
    {"id":"SL419","name":"성내3동","gu":"강동구","city":"서울","lat":37.5284,"lon":127.1338,"drainage_capacity":100.0,"impervious_ratio":0.974,"topo_depression":0.967,"flood_history":0.0},
    {"id":"SL420","name":"둔촌1동","gu":"강동구","city":"서울","lat":37.5231,"lon":127.1404,"drainage_capacity":100.0,"impervious_ratio":0.286,"topo_depression":0.913,"flood_history":0.0},
    {"id":"SL421","name":"둔촌2동","gu":"강동구","city":"서울","lat":37.5315,"lon":127.1474,"drainage_capacity":100.0,"impervious_ratio":0.567,"topo_depression":0.857,"flood_history":0.0},
    {"id":"SL422","name":"암사1동","gu":"강동구","city":"서울","lat":37.5519,"lon":127.1346,"drainage_capacity":100.0,"impervious_ratio":0.989,"topo_depression":0.933,"flood_history":0.0},
    {"id":"SL423","name":"천호2동","gu":"강동구","city":"서울","lat":37.5447,"lon":127.1223,"drainage_capacity":100.0,"impervious_ratio":0.571,"topo_depression":0.973,"flood_history":0.0},
    {"id":"SL424","name":"길동","gu":"강동구","city":"서울","lat":37.5397,"lon":127.1459,"drainage_capacity":100.0,"impervious_ratio":0.719,"topo_depression":0.921,"flood_history":0.0},
    {"id":"SL425","name":"오류2동","gu":"구로구","city":"서울","lat":37.4853,"lon":126.8384,"drainage_capacity":100.0,"impervious_ratio":0.504,"topo_depression":0.905,"flood_history":0.0},
    {"id":"IC044","name":"연안동","gu":"중구","city":"인천","lat":37.4518,"lon":126.6088,"drainage_capacity":90.0,"impervious_ratio":0.801,"topo_depression":0.991,"flood_history":0.0},
    {"id":"IC045","name":"신포동","gu":"중구","city":"인천","lat":37.4673,"lon":126.6232,"drainage_capacity":90.0,"impervious_ratio":0.856,"topo_depression":0.977,"flood_history":0.0},
    {"id":"IC046","name":"신흥동","gu":"중구","city":"인천","lat":37.4441,"lon":126.627,"drainage_capacity":90.0,"impervious_ratio":0.746,"topo_depression":0.991,"flood_history":0.0},
    {"id":"IC047","name":"도원동","gu":"중구","city":"인천","lat":37.4672,"lon":126.6398,"drainage_capacity":90.0,"impervious_ratio":0.731,"topo_depression":0.931,"flood_history":0.0},
    {"id":"IC048","name":"율목동","gu":"중구","city":"인천","lat":37.4701,"lon":126.635,"drainage_capacity":90.0,"impervious_ratio":0.8,"topo_depression":0.951,"flood_history":0.0},
    {"id":"IC049","name":"동인천동","gu":"중구","city":"인천","lat":37.4753,"lon":126.6288,"drainage_capacity":90.0,"impervious_ratio":0.74,"topo_depression":0.933,"flood_history":0.0},
    {"id":"IC050","name":"북성동","gu":"중구","city":"인천","lat":37.4759,"lon":126.6069,"drainage_capacity":90.0,"impervious_ratio":0.643,"topo_depression":0.969,"flood_history":0.0},
    {"id":"IC051","name":"송월동","gu":"중구","city":"인천","lat":37.4793,"lon":126.622,"drainage_capacity":90.0,"impervious_ratio":0.963,"topo_depression":0.937,"flood_history":0.0},
    {"id":"IC052","name":"영종동","gu":"중구","city":"인천","lat":37.5036,"lon":126.529,"drainage_capacity":90.0,"impervious_ratio":0.306,"topo_depression":0.905,"flood_history":0.0},
    {"id":"IC053","name":"용유동","gu":"중구","city":"인천","lat":37.4229,"lon":126.406,"drainage_capacity":90.0,"impervious_ratio":0.195,"topo_depression":0.857,"flood_history":0.0},
    {"id":"IC054","name":"운서동","gu":"중구","city":"인천","lat":37.4702,"lon":126.452,"drainage_capacity":90.0,"impervious_ratio":0.332,"topo_depression":0.981,"flood_history":0.0},
    {"id":"IC055","name":"만석동","gu":"동구","city":"인천","lat":37.4864,"lon":126.6202,"drainage_capacity":90.0,"impervious_ratio":0.933,"topo_depression":0.984,"flood_history":0.0},
    {"id":"IC056","name":"화수1·화평동","gu":"동구","city":"인천","lat":37.4805,"lon":126.6299,"drainage_capacity":90.0,"impervious_ratio":0.941,"topo_depression":0.961,"flood_history":0.0},
    {"id":"IC057","name":"화수2동","gu":"동구","city":"인천","lat":37.485,"lon":126.6311,"drainage_capacity":90.0,"impervious_ratio":0.92,"topo_depression":0.986,"flood_history":0.0},
    {"id":"IC058","name":"송현1·2동","gu":"동구","city":"인천","lat":37.4779,"lon":126.6358,"drainage_capacity":90.0,"impervious_ratio":0.927,"topo_depression":0.953,"flood_history":0.0},
    {"id":"IC059","name":"송림1동","gu":"동구","city":"인천","lat":37.4752,"lon":126.6388,"drainage_capacity":90.0,"impervious_ratio":0.667,"topo_depression":0.953,"flood_history":0.0},
    {"id":"IC060","name":"금창동","gu":"동구","city":"인천","lat":37.4716,"lon":126.6407,"drainage_capacity":90.0,"impervious_ratio":0.73,"topo_depression":0.946,"flood_history":0.0},
    {"id":"IC061","name":"숭의4동","gu":"미추홀구","city":"인천","lat":37.4624,"lon":126.6571,"drainage_capacity":90.0,"impervious_ratio":0.663,"topo_depression":0.89,"flood_history":0.0},
    {"id":"IC062","name":"용현3동","gu":"미추홀구","city":"인천","lat":37.4554,"lon":126.6527,"drainage_capacity":90.0,"impervious_ratio":0.946,"topo_depression":0.915,"flood_history":0.0},
    {"id":"IC063","name":"용현5동","gu":"미추홀구","city":"인천","lat":37.449,"lon":126.639,"drainage_capacity":90.0,"impervious_ratio":0.58,"topo_depression":0.989,"flood_history":0.0},
    {"id":"IC064","name":"학익2동","gu":"미추홀구","city":"인천","lat":37.4434,"lon":126.6703,"drainage_capacity":90.0,"impervious_ratio":0.745,"topo_depression":0.912,"flood_history":0.0},
    {"id":"IC065","name":"주안1동","gu":"미추홀구","city":"인천","lat":37.462,"lon":126.6806,"drainage_capacity":90.0,"impervious_ratio":0.938,"topo_depression":0.952,"flood_history":0.0},
    {"id":"IC066","name":"주안2동","gu":"미추홀구","city":"인천","lat":37.4553,"lon":126.672,"drainage_capacity":90.0,"impervious_ratio":0.824,"topo_depression":0.923,"flood_history":0.0},
    {"id":"IC067","name":"주안3동","gu":"미추홀구","city":"인천","lat":37.4484,"lon":126.6716,"drainage_capacity":90.0,"impervious_ratio":0.909,"topo_depression":0.943,"flood_history":0.0},
    {"id":"IC068","name":"주안4동","gu":"미추홀구","city":"인천","lat":37.4544,"lon":126.6871,"drainage_capacity":90.0,"impervious_ratio":0.842,"topo_depression":0.961,"flood_history":0.0},
    {"id":"IC069","name":"주안6동","gu":"미추홀구","city":"인천","lat":37.461,"lon":126.6908,"drainage_capacity":90.0,"impervious_ratio":0.899,"topo_depression":0.948,"flood_history":0.0},
    {"id":"IC070","name":"주안7동","gu":"미추홀구","city":"인천","lat":37.4473,"lon":126.6778,"drainage_capacity":90.0,"impervious_ratio":0.918,"topo_depression":0.937,"flood_history":0.0},
    {"id":"IC071","name":"주안8동","gu":"미추홀구","city":"인천","lat":37.4476,"lon":126.6853,"drainage_capacity":90.0,"impervious_ratio":0.818,"topo_depression":0.893,"flood_history":0.0},
    {"id":"IC072","name":"관교동","gu":"미추홀구","city":"인천","lat":37.4427,"lon":126.694,"drainage_capacity":90.0,"impervious_ratio":0.568,"topo_depression":0.925,"flood_history":0.0},
    {"id":"IC073","name":"문학동","gu":"미추홀구","city":"인천","lat":37.4365,"lon":126.6853,"drainage_capacity":90.0,"impervious_ratio":0.526,"topo_depression":0.804,"flood_history":0.0},
    {"id":"IC074","name":"용현1·4동","gu":"미추홀구","city":"인천","lat":37.4518,"lon":126.6589,"drainage_capacity":90.0,"impervious_ratio":0.674,"topo_depression":0.92,"flood_history":0.0},
    {"id":"IC075","name":"송도4동","gu":"연수구","city":"인천","lat":37.3917,"lon":126.6225,"drainage_capacity":90.0,"impervious_ratio":0.21,"topo_depression":0.993,"flood_history":0.0},
    {"id":"IC076","name":"구월1동","gu":"남동구","city":"인천","lat":37.4459,"lon":126.7093,"drainage_capacity":90.0,"impervious_ratio":0.813,"topo_depression":0.944,"flood_history":0.0},
    {"id":"IC077","name":"구월2동","gu":"남동구","city":"인천","lat":37.4564,"lon":126.7155,"drainage_capacity":90.0,"impervious_ratio":0.9,"topo_depression":0.892,"flood_history":0.0},
    {"id":"IC078","name":"구월3동","gu":"남동구","city":"인천","lat":37.4498,"lon":126.6975,"drainage_capacity":90.0,"impervious_ratio":0.857,"topo_depression":0.954,"flood_history":0.0},
    {"id":"IC079","name":"구월4동","gu":"남동구","city":"인천","lat":37.4485,"lon":126.7227,"drainage_capacity":90.0,"impervious_ratio":0.787,"topo_depression":0.918,"flood_history":0.0},
    {"id":"IC080","name":"간석3동","gu":"남동구","city":"인천","lat":37.4688,"lon":126.7153,"drainage_capacity":90.0,"impervious_ratio":0.57,"topo_depression":0.755,"flood_history":0.0},
    {"id":"IC081","name":"만수1동","gu":"남동구","city":"인천","lat":37.4509,"lon":126.734,"drainage_capacity":90.0,"impervious_ratio":0.783,"topo_depression":0.942,"flood_history":0.0},
    {"id":"IC082","name":"만수2동","gu":"남동구","city":"인천","lat":37.4651,"lon":126.7359,"drainage_capacity":90.0,"impervious_ratio":0.522,"topo_depression":0.72,"flood_history":0.0},
    {"id":"IC083","name":"만수3동","gu":"남동구","city":"인천","lat":37.4658,"lon":126.7267,"drainage_capacity":90.0,"impervious_ratio":0.376,"topo_depression":0.634,"flood_history":0.0},
    {"id":"IC084","name":"만수4동","gu":"남동구","city":"인천","lat":37.4568,"lon":126.7378,"drainage_capacity":90.0,"impervious_ratio":0.631,"topo_depression":0.837,"flood_history":0.0},
    {"id":"IC085","name":"만수5동","gu":"남동구","city":"인천","lat":37.4561,"lon":126.7264,"drainage_capacity":90.0,"impervious_ratio":0.922,"topo_depression":0.917,"flood_history":0.0},
    {"id":"IC086","name":"부평1동","gu":"부평구","city":"인천","lat":37.4963,"lon":126.7203,"drainage_capacity":90.0,"impervious_ratio":0.879,"topo_depression":0.95,"flood_history":0.0},
    {"id":"IC087","name":"부평2동","gu":"부평구","city":"인천","lat":37.4792,"lon":126.7212,"drainage_capacity":90.0,"impervious_ratio":0.181,"topo_depression":0.693,"flood_history":0.0},
    {"id":"IC088","name":"부평3동","gu":"부평구","city":"인천","lat":37.4844,"lon":126.7091,"drainage_capacity":90.0,"impervious_ratio":0.629,"topo_depression":0.874,"flood_history":0.0},
    {"id":"IC089","name":"부평4동","gu":"부평구","city":"인천","lat":37.5014,"lon":126.7261,"drainage_capacity":90.0,"impervious_ratio":0.862,"topo_depression":0.967,"flood_history":0.0},
    {"id":"IC090","name":"부평5동","gu":"부평구","city":"인천","lat":37.4955,"lon":126.7305,"drainage_capacity":90.0,"impervious_ratio":0.959,"topo_depression":0.961,"flood_history":0.0},
    {"id":"IC091","name":"부평6동","gu":"부평구","city":"인천","lat":37.4848,"lon":126.7271,"drainage_capacity":90.0,"impervious_ratio":0.631,"topo_depression":0.841,"flood_history":0.0},
    {"id":"IC092","name":"산곡1동","gu":"부평구","city":"인천","lat":37.5047,"lon":126.6957,"drainage_capacity":90.0,"impervious_ratio":0.229,"topo_depression":0.805,"flood_history":0.0},
    {"id":"IC093","name":"산곡2동","gu":"부평구","city":"인천","lat":37.5035,"lon":126.7053,"drainage_capacity":90.0,"impervious_ratio":0.817,"topo_depression":0.941,"flood_history":0.0},
    {"id":"IC094","name":"산곡3동","gu":"부평구","city":"인천","lat":37.4929,"lon":126.7069,"drainage_capacity":90.0,"impervious_ratio":0.448,"topo_depression":0.897,"flood_history":0.0},
    {"id":"IC095","name":"산곡4동","gu":"부평구","city":"인천","lat":37.5021,"lon":126.7121,"drainage_capacity":90.0,"impervious_ratio":0.776,"topo_depression":0.954,"flood_history":0.0},
    {"id":"IC096","name":"청천1동","gu":"부평구","city":"인천","lat":37.5185,"lon":126.6947,"drainage_capacity":90.0,"impervious_ratio":0.555,"topo_depression":0.826,"flood_history":0.0},
    {"id":"IC097","name":"청천2동","gu":"부평구","city":"인천","lat":37.5152,"lon":126.7133,"drainage_capacity":90.0,"impervious_ratio":0.664,"topo_depression":0.956,"flood_history":0.0},
    {"id":"IC098","name":"갈산1동","gu":"부평구","city":"인천","lat":37.5185,"lon":126.7267,"drainage_capacity":90.0,"impervious_ratio":0.681,"topo_depression":0.951,"flood_history":0.0},
    {"id":"IC099","name":"갈산2동","gu":"부평구","city":"인천","lat":37.5105,"lon":126.7267,"drainage_capacity":90.0,"impervious_ratio":0.642,"topo_depression":0.97,"flood_history":0.0},
    {"id":"IC100","name":"삼산1동","gu":"부평구","city":"인천","lat":37.5204,"lon":126.747,"drainage_capacity":90.0,"impervious_ratio":0.845,"topo_depression":0.984,"flood_history":0.0},
    {"id":"IC101","name":"부개1동","gu":"부평구","city":"인천","lat":37.4841,"lon":126.736,"drainage_capacity":90.0,"impervious_ratio":0.67,"topo_depression":0.885,"flood_history":0.0},
    {"id":"IC102","name":"부개2동","gu":"부평구","city":"인천","lat":37.4931,"lon":126.7379,"drainage_capacity":90.0,"impervious_ratio":0.798,"topo_depression":0.955,"flood_history":0.0},
    {"id":"IC103","name":"부개3동","gu":"부평구","city":"인천","lat":37.5023,"lon":126.7383,"drainage_capacity":90.0,"impervious_ratio":0.769,"topo_depression":0.967,"flood_history":0.0},
    {"id":"IC104","name":"일신동","gu":"부평구","city":"인천","lat":37.4752,"lon":126.7484,"drainage_capacity":90.0,"impervious_ratio":0.222,"topo_depression":0.799,"flood_history":0.0},
    {"id":"IC105","name":"십정1동","gu":"부평구","city":"인천","lat":37.4782,"lon":126.6949,"drainage_capacity":90.0,"impervious_ratio":0.664,"topo_depression":0.919,"flood_history":0.0},
    {"id":"IC106","name":"삼산2동","gu":"부평구","city":"인천","lat":37.5125,"lon":126.7387,"drainage_capacity":90.0,"impervious_ratio":0.679,"topo_depression":0.973,"flood_history":0.0},
    {"id":"IC107","name":"효성1동","gu":"계양구","city":"인천","lat":37.5341,"lon":126.7081,"drainage_capacity":90.0,"impervious_ratio":0.397,"topo_depression":0.741,"flood_history":0.0},
    {"id":"IC108","name":"효성2동","gu":"계양구","city":"인천","lat":37.53,"lon":126.698,"drainage_capacity":90.0,"impervious_ratio":0.401,"topo_depression":0.708,"flood_history":0.0},
    {"id":"IC109","name":"계산1동","gu":"계양구","city":"인천","lat":37.5408,"lon":126.7177,"drainage_capacity":90.0,"impervious_ratio":0.508,"topo_depression":0.802,"flood_history":0.0},
    {"id":"IC110","name":"계산2동","gu":"계양구","city":"인천","lat":37.5479,"lon":126.7198,"drainage_capacity":90.0,"impervious_ratio":0.318,"topo_depression":0.566,"flood_history":0.0},
    {"id":"IC111","name":"계산3동","gu":"계양구","city":"인천","lat":37.5395,"lon":126.7317,"drainage_capacity":90.0,"impervious_ratio":0.871,"topo_depression":0.936,"flood_history":0.0},
    {"id":"IC112","name":"작전1동","gu":"계양구","city":"인천","lat":37.5294,"lon":126.7299,"drainage_capacity":90.0,"impervious_ratio":0.808,"topo_depression":0.958,"flood_history":0.0},
    {"id":"IC113","name":"작전2동","gu":"계양구","city":"인천","lat":37.5309,"lon":126.7226,"drainage_capacity":90.0,"impervious_ratio":0.816,"topo_depression":0.93,"flood_history":0.0},
    {"id":"IC114","name":"계양2동","gu":"계양구","city":"인천","lat":37.5485,"lon":126.7411,"drainage_capacity":90.0,"impervious_ratio":0.606,"topo_depression":0.898,"flood_history":0.0},
    {"id":"IC115","name":"계산4동","gu":"계양구","city":"인천","lat":37.5386,"lon":126.7399,"drainage_capacity":90.0,"impervious_ratio":0.772,"topo_depression":0.973,"flood_history":0.0},
    {"id":"IC116","name":"검암경서동","gu":"서구","city":"인천","lat":37.5687,"lon":126.6357,"drainage_capacity":90.0,"impervious_ratio":0.43,"topo_depression":0.96,"flood_history":0.0},
    {"id":"IC117","name":"연희동","gu":"서구","city":"인천","lat":37.5478,"lon":126.6823,"drainage_capacity":90.0,"impervious_ratio":0.377,"topo_depression":0.769,"flood_history":0.0},
    {"id":"IC118","name":"가정1동","gu":"서구","city":"인천","lat":37.5285,"lon":126.671,"drainage_capacity":90.0,"impervious_ratio":0.55,"topo_depression":0.935,"flood_history":0.0},
    {"id":"IC119","name":"가정2동","gu":"서구","city":"인천","lat":37.5287,"lon":126.6814,"drainage_capacity":90.0,"impervious_ratio":0.343,"topo_depression":0.719,"flood_history":0.0},
    {"id":"IC120","name":"가정3동","gu":"서구","city":"인천","lat":37.5177,"lon":126.6813,"drainage_capacity":90.0,"impervious_ratio":0.493,"topo_depression":0.781,"flood_history":0.0},
    {"id":"IC121","name":"석남1동","gu":"서구","city":"인천","lat":37.5102,"lon":126.6687,"drainage_capacity":90.0,"impervious_ratio":0.795,"topo_depression":0.951,"flood_history":0.0},
    {"id":"IC122","name":"석남2동","gu":"서구","city":"인천","lat":37.5031,"lon":126.6582,"drainage_capacity":90.0,"impervious_ratio":0.775,"topo_depression":0.982,"flood_history":0.0},
    {"id":"IC123","name":"석남3동","gu":"서구","city":"인천","lat":37.5063,"lon":126.6815,"drainage_capacity":90.0,"impervious_ratio":0.371,"topo_depression":0.735,"flood_history":0.0},
    {"id":"IC124","name":"가좌2동","gu":"서구","city":"인천","lat":37.4951,"lon":126.686,"drainage_capacity":90.0,"impervious_ratio":0.634,"topo_depression":0.84,"flood_history":0.0},
    {"id":"IC125","name":"가좌4동","gu":"서구","city":"인천","lat":37.4861,"lon":126.6885,"drainage_capacity":90.0,"impervious_ratio":0.508,"topo_depression":0.903,"flood_history":0.0},
    {"id":"IC126","name":"마전동","gu":"서구","city":"인천","lat":37.589,"lon":126.6788,"drainage_capacity":90.0,"impervious_ratio":0.433,"topo_depression":0.887,"flood_history":0.0},
    {"id":"IC127","name":"신현원창동","gu":"서구","city":"인천","lat":37.5108,"lon":126.6372,"drainage_capacity":90.0,"impervious_ratio":0.498,"topo_depression":0.981,"flood_history":0.0},
    {"id":"IC128","name":"청라1동","gu":"서구","city":"인천","lat":37.533,"lon":126.6562,"drainage_capacity":90.0,"impervious_ratio":0.575,"topo_depression":0.998,"flood_history":0.0},
    {"id":"IC129","name":"청라2동","gu":"서구","city":"인천","lat":37.5337,"lon":126.6408,"drainage_capacity":90.0,"impervious_ratio":0.331,"topo_depression":0.998,"flood_history":0.0},
    {"id":"IC130","name":"검단동","gu":"서구","city":"인천","lat":37.6122,"lon":126.6527,"drainage_capacity":90.0,"impervious_ratio":0.421,"topo_depression":0.878,"flood_history":0.0},
    {"id":"IC131","name":"오류왕길동","gu":"서구","city":"인천","lat":37.5906,"lon":126.6317,"drainage_capacity":90.0,"impervious_ratio":0.639,"topo_depression":0.97,"flood_history":0.0},
    {"id":"IC132","name":"강화읍","gu":"강화군","city":"인천","lat":37.7527,"lon":126.4897,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.857,"flood_history":0.0},
    {"id":"IC133","name":"선원면","gu":"강화군","city":"인천","lat":37.7166,"lon":126.4886,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.852,"flood_history":0.0},
    {"id":"IC134","name":"불은면","gu":"강화군","city":"인천","lat":37.6833,"lon":126.4855,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.827,"flood_history":0.0},
    {"id":"IC135","name":"길상면","gu":"강화군","city":"인천","lat":37.6223,"lon":126.5011,"drainage_capacity":90.0,"impervious_ratio":0.376,"topo_depression":0.862,"flood_history":0.0},
    {"id":"IC136","name":"화도면","gu":"강화군","city":"인천","lat":37.6191,"lon":126.4231,"drainage_capacity":90.0,"impervious_ratio":0.305,"topo_depression":0.747,"flood_history":0.0},
    {"id":"IC137","name":"양도면","gu":"강화군","city":"인천","lat":37.6715,"lon":126.4297,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.723,"flood_history":0.0},
    {"id":"IC138","name":"내가면","gu":"강화군","city":"인천","lat":37.7221,"lon":126.3888,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.686,"flood_history":0.0},
    {"id":"IC139","name":"하점면","gu":"강화군","city":"인천","lat":37.7624,"lon":126.4006,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.751,"flood_history":0.0},
    {"id":"IC140","name":"양사면","gu":"강화군","city":"인천","lat":37.8031,"lon":126.4016,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.791,"flood_history":0.0},
    {"id":"IC141","name":"송해면","gu":"강화군","city":"인천","lat":37.7798,"lon":126.4601,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.891,"flood_history":0.0},
    {"id":"IC142","name":"교동면","gu":"강화군","city":"인천","lat":37.7869,"lon":126.2654,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.938,"flood_history":0.0},
    {"id":"IC143","name":"삼산면","gu":"강화군","city":"인천","lat":37.6981,"lon":126.3197,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.823,"flood_history":0.0},
    {"id":"IC144","name":"서도면","gu":"강화군","city":"인천","lat":37.6609,"lon":126.2097,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.924,"flood_history":0.0},
    {"id":"IC145","name":"북도면","gu":"옹진군","city":"인천","lat":37.533,"lon":126.3987,"drainage_capacity":90.0,"impervious_ratio":0.297,"topo_depression":0.886,"flood_history":0.0},
    {"id":"IC146","name":"연평면","gu":"옹진군","city":"인천","lat":37.6632,"lon":125.6967,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.849,"flood_history":0.0},
    {"id":"IC147","name":"백령면","gu":"옹진군","city":"인천","lat":37.9532,"lon":124.6743,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.865,"flood_history":0.0},
    {"id":"IC148","name":"대청면","gu":"옹진군","city":"인천","lat":37.8129,"lon":124.711,"drainage_capacity":90.0,"impervious_ratio":0.65,"topo_depression":0.683,"flood_history":0.0},
    {"id":"IC149","name":"덕적면","gu":"옹진군","city":"인천","lat":37.1986,"lon":126.0909,"drainage_capacity":90.0,"impervious_ratio":0.086,"topo_depression":0.728,"flood_history":0.0},
    {"id":"IC150","name":"자월면","gu":"옹진군","city":"인천","lat":37.1898,"lon":126.2535,"drainage_capacity":90.0,"impervious_ratio":0.113,"topo_depression":0.781,"flood_history":0.0},
    {"id":"IC151","name":"영흥면","gu":"옹진군","city":"인천","lat":37.2551,"lon":126.4665,"drainage_capacity":90.0,"impervious_ratio":0.243,"topo_depression":0.903,"flood_history":0.0},
    {"id":"IC152","name":"청라3동","gu":"서구","city":"인천","lat":37.5334,"lon":126.6182,"drainage_capacity":90.0,"impervious_ratio":0.279,"topo_depression":0.992,"flood_history":0.0},
    {"id":"IC153","name":"영종1동","gu":"중구","city":"인천","lat":37.4926,"lon":126.5652,"drainage_capacity":90.0,"impervious_ratio":0.386,"topo_depression":0.975,"flood_history":0.0},
    {"id":"IC154","name":"송도2동","gu":"연수구","city":"인천","lat":37.4004,"lon":126.6398,"drainage_capacity":90.0,"impervious_ratio":0.489,"topo_depression":0.992,"flood_history":0.0},
    {"id":"IC155","name":"당하동","gu":"서구","city":"인천","lat":37.5963,"lon":126.6736,"drainage_capacity":90.0,"impervious_ratio":0.543,"topo_depression":0.882,"flood_history":0.0}
]


def _make_polygon(lat: float, lon: float, radius_deg: float = 0.02, n: int = 16) -> list:
    """원형 근사 폴리곤 (실제 경계 없을 때 폴백)."""
    rng = random.Random(hash(f"{lat:.3f}{lon:.3f}"))
    coords = []
    for i in range(n):
        angle = 2 * math.pi * i / n
        r = radius_deg * (0.85 + rng.uniform(-0.12, 0.12))
        coords.append([lon + r * math.cos(angle), lat + r * math.sin(angle)])
    coords.append(coords[0])
    return coords


def _current_regional_rainfall() -> Dict[str, float]:
    """현재 10분 구간 기준 지역별 강수량 생성 (더미)."""
    t_bucket = int(time.time() / 600)
    result = {}
    cities = list({d["city"] for d in DISTRICTS})
    for city in cities:
        rng = random.Random(hash((t_bucket, city)))
        roll = rng.random()
        if roll < 0.60:
            rain = rng.uniform(0.0, 5.0)
        elif roll < 0.82:
            rain = rng.uniform(5.0, 15.0)
        elif roll < 0.93:
            rain = rng.uniform(15.0, 35.0)
        else:
            rain = rng.uniform(35.0, 70.0)
        result[city] = round(rain, 1)
    return result


def _forecast_rainfall(meta: Dict, current_rain: float) -> Dict:
    """현재 강수량 기반 1h/3h 예보 더미 생성."""
    rng = random.Random(hash((int(time.time() / 600), meta["id"], "fc")))
    trend_1h = current_rain * rng.uniform(0.8, 1.3)
    trend_3h = trend_1h * rng.uniform(0.85, 1.15)
    return {
        "1h": {"rainfall": round(max(trend_1h, 0.0), 1)},
        "3h": {"rainfall": round(max(trend_3h, 0.0), 1)},
    }


def _nearest_station_bonus(lat: float, lon: float, stations: List[Dict]) -> float:
    """가장 가까운 신뢰 수위 관측소의 수위 보정값 반환."""
    from risk_engine import water_level_bonus
    best_bonus, best_dist = 0.0, float("inf")
    for s in stations:
        if not s.get("use_for_risk", True):
            continue
        if s.get("_source") == "missing":
            continue
        dist = math.hypot(s["lat"] - lat, s["lon"] - lon)
        if dist < best_dist:
            best_dist = dist
            best_bonus = water_level_bonus(s["water_level"], s["alert_level"])
    return best_bonus


def build_urban_risk_data(
    kma_rain: Dict = None,
    kma_by_city: Dict = None,
    kma_grid_data: Dict = None,
    hrfco_stations: List[Dict] = None,
) -> Tuple[List[Dict], Dict]:
    """
    전체 지구 위험도 계산 → (enriched_list, current GeoJSON) 반환.
    kma_grid_data:   {(nx, ny): {"current": float, "1h": float, "3h": float}}  격자별 KMA 실황 (우선)
    hrfco_stations:  HRFCO 수위 관측소 목록 → 가장 가까운 관측소 수위로 위험도 보정
    kma_by_city:     {"서울": {...}, "인천": {...}}  도시별 KMA 실황 (하위호환)
    kma_rain:        단일 dict (하위호환)
    """
    # 격자 기반 per-district KMA 데이터 미리 계산
    district_kma: Dict[str, Dict] = {}
    if kma_grid_data:
        from clients.kma import latlon_to_grid as _lg
        for m in DISTRICTS:
            key = _lg(m["lat"], m["lon"])
            val = kma_grid_data.get(key)
            if val is not None:
                district_kma[m["id"]] = val
    elif kma_by_city:
        # 도시 단위 폴백
        for m in DISTRICTS:
            city = m.get("city", "서울")
            val  = kma_by_city.get(city)
            if val:
                district_kma[m["id"]] = val
    elif kma_rain and kma_rain.get("source") == "kma":
        for m in DISTRICTS:
            district_kma[m["id"]] = kma_rain

    dummy_rain = _current_regional_rainfall() if not district_kma else {}

    enriched = []

    for meta in DISTRICTS:
        rng = random.Random(hash((int(time.time() / 600), meta["id"])))
        city = meta.get("city", "서울")
        kma  = district_kma.get(meta["id"])

        if kma:
            base = kma["current"]
            rainfall_1h = round(max(base * rng.uniform(0.85, 1.15), 0.0), 1)
        else:
            city_rain = dummy_rain.get(city, 10.0)
            rainfall_1h = round(city_rain * rng.uniform(0.8, 1.2), 1)

        rule_score = compute_urban_flood_risk(
            rainfall_1h        = rainfall_1h,
            drainage_capacity  = meta["drainage_capacity"],
            impervious_ratio   = meta["impervious_ratio"],
            topo_depression    = meta["topo_depression"],
            flood_history      = meta["flood_history"],
        )
        # 수위 보정: 가까운 HRFCO 관측소 수위 반영 (최대 +0.10)
        wl_bonus = _nearest_station_bonus(meta["lat"], meta["lon"], hrfco_stations or [])
        final_score = min(round(rule_score + wl_bonus, 4), 1.0)
        grade_info = score_to_grade(final_score, rainfall_1h)
        reason     = generate_urban_reason(meta, rainfall_1h, grade_info["grade"])

        if kma:
            rng2 = random.Random(hash((int(time.time() / 600), meta["id"], "fc")))
            forecast = {
                "1h": {"rainfall": round(max(kma["1h"] * rng2.uniform(0.85, 1.15), 0.0), 1)},
                "3h": {"rainfall": round(max(kma["3h"] * rng2.uniform(0.85, 1.15), 0.0), 1)},
            }
        else:
            forecast = _forecast_rainfall(meta, rainfall_1h)

        for h_key in ("1h", "3h"):
            r_fc = forecast[h_key]["rainfall"]
            fc_score = compute_urban_flood_risk(
                rainfall_1h        = r_fc,
                drainage_capacity  = meta["drainage_capacity"],
                impervious_ratio   = meta["impervious_ratio"],
                topo_depression    = meta["topo_depression"],
                flood_history      = meta["flood_history"],
            )
            fc_grade = score_to_grade(fc_score, r_fc)
            forecast[h_key].update({
                "rule_score": fc_score,
                "risk_score": fc_score,
                "grade":      fc_grade["grade"],
                "color":      fc_grade["color"],
            })

        d = {
            **meta,
            "rainfall_1h":       rainfall_1h,
            "rain_overload_pct": round(rainfall_1h / max(meta["drainage_capacity"], 1) * 100, 1),
            "f_rainfall":        round(min(rainfall_1h / max(meta["drainage_capacity"], 1), 1.0), 4),
            "f_hand":            round(meta["topo_depression"], 4),
            "f_imperv":          round(meta["impervious_ratio"], 4),
            "f_history":         round(meta["flood_history"], 4),
            "rule_score":        rule_score,
            "wl_bonus":          wl_bonus,
            "ml_score":          None,
            "risk_score":        final_score,
            "grade":             grade_info["grade"],
            "color":             grade_info["color"],
            "reason":            reason,
            "forecast":          forecast,
            "_kma_real":         kma is not None,
        }
        enriched.append(d)

    geojson = build_geojson_for_horizon(enriched, "current")
    return enriched, geojson


def apply_ml_scores(enriched: List[Dict], ml_scores: Dict[str, Dict[str, float]]) -> List[Dict]:
    """ML 스코어를 enriched 목록에 블렌딩."""
    from predictor import blend
    for d in enriched:
        did = d["id"]
        if did not in ml_scores:
            continue
        ml = ml_scores[did]
        d["ml_score"]   = ml.get("current", 0.5)
        d["risk_score"] = blend(d["rule_score"], ml.get("current", 0.5))
        gi = score_to_grade(d["risk_score"])
        d["grade"] = gi["grade"]
        d["color"] = gi["color"]
        for h in ("1h", "3h"):
            if h in d.get("forecast", {}):
                rs = d["forecast"][h]["rule_score"]
                ms = ml.get(h, 0.5)
                blended = blend(rs, ms)
                gi_fc = score_to_grade(blended)
                d["forecast"][h]["risk_score"] = blended
                d["forecast"][h]["grade"]      = gi_fc["grade"]
                d["forecast"][h]["color"]      = gi_fc["color"]
    return enriched


def build_geojson_for_horizon(enriched: List[Dict], horizon: str) -> Dict:
    """enriched 목록 → GeoJSON FeatureCollection."""
    features = []
    for d in enriched:
        did = d["id"]
        boundary = _BOUNDARIES.get(did)

        if boundary and boundary.get("geometry"):
            geometry = boundary["geometry"]
        else:
            coords = _make_polygon(d["lat"], d["lon"])
            geometry = {"type": "Polygon", "coordinates": [coords]}

        if horizon == "current":
            risk_score = d["risk_score"]
            grade      = d["grade"]
            color      = d["color"]
        else:
            fc = d.get("forecast", {}).get(horizon, {})
            risk_score = fc.get("risk_score", d["risk_score"])
            grade      = fc.get("grade", d["grade"])
            color      = fc.get("color", d["color"])

        features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": {
                "id":               did,
                "name":             d["name"],
                "gu":               d.get("gu", ""),
                "city":             d.get("city", ""),
                "grade":            grade,
                "risk_score":       risk_score,
                "color":            color,
                "opacity":          _opacity(grade),
                "rainfall_1h":      d.get("rainfall_1h", 0),
                "rain_overload_pct": d.get("rain_overload_pct", 0),
                "drainage_capacity": d["drainage_capacity"],
                "reason":           d.get("reason", ""),
                "horizon":          horizon,
            },
        })
    return {"type": "FeatureCollection", "features": features}


def find_nearest(lat: float, lon: float) -> Dict:
    """위경도 → 가장 가까운 지구 반환 (캐시된 enriched 데이터에서)."""
    best, best_dist = None, float("inf")
    for d in DISTRICTS:
        dist = math.hypot(d["lat"] - lat, d["lon"] - lon)
        if dist < best_dist:
            best_dist, best = dist, d
    return best, best_dist * 111  # km


def _opacity(grade: str) -> float:
    return {"안전": 0.42, "주의": 0.58, "경보": 0.72, "위험": 0.88}.get(grade, 0.5)