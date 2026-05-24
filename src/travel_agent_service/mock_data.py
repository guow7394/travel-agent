from typing import Dict, List

from .models import FoodRecommendation, Location, Place


SHANGHAI_PLACES: Dict[str, Place] = {
    "人民广场": Place(
        name="人民广场",
        location=Location(longitude=121.473701, latitude=31.230416),
        category="hub",
        default_stay_minutes=0,
        tags=["交通枢纽"],
    ),
    "上海博物馆": Place(
        name="上海博物馆",
        location=Location(longitude=121.475333, latitude=31.228315),
        ticket_cny=0,
        default_stay_minutes=90,
        indoor_score=1.0,
        tags=["博物馆", "室内", "历史"],
    ),
    "豫园": Place(
        name="豫园",
        location=Location(longitude=121.492809, latitude=31.227228),
        ticket_cny=40,
        default_stay_minutes=75,
        indoor_score=0.4,
        tags=["古典园林", "拍照", "小吃"],
    ),
    "外滩": Place(
        name="外滩",
        location=Location(longitude=121.490317, latitude=31.239248),
        ticket_cny=0,
        default_stay_minutes=60,
        indoor_score=0.2,
        tags=["夜景", "拍照", "地标"],
    ),
    "武康路": Place(
        name="武康路",
        location=Location(longitude=121.438384, latitude=31.211501),
        ticket_cny=0,
        default_stay_minutes=60,
        indoor_score=0.2,
        tags=["街区", "拍照", "咖啡"],
    ),
    "新天地": Place(
        name="新天地",
        location=Location(longitude=121.475182, latitude=31.219694),
        ticket_cny=0,
        default_stay_minutes=60,
        indoor_score=0.5,
        tags=["街区", "餐饮", "休闲"],
    ),
    "田子坊": Place(
        name="田子坊",
        location=Location(longitude=121.467062, latitude=31.209113),
        ticket_cny=0,
        default_stay_minutes=60,
        indoor_score=0.3,
        tags=["街区", "文创", "小店"],
    ),
}


SHANGHAI_FOOD: List[FoodRecommendation] = [
    FoodRecommendation(
        name="大壶春",
        near_stop="人民广场",
        avg_price_cny=45,
        location=Location(longitude=121.478017, latitude=31.229091),
        reason="预算友好，生煎适合快速补给。",
    ),
    FoodRecommendation(
        name="老盛昌汤包馆",
        near_stop="豫园",
        avg_price_cny=35,
        location=Location(longitude=121.491612, latitude=31.227815),
        reason="靠近豫园，低预算模式下性价比高。",
    ),
    FoodRecommendation(
        name="上海姥姥",
        near_stop="外滩",
        avg_price_cny=95,
        location=Location(longitude=121.489514, latitude=31.237623),
        reason="靠近外滩，适合想吃本帮菜但不想绕路。",
    ),
    FoodRecommendation(
        name="老吉士",
        near_stop="外滩",
        avg_price_cny=150,
        location=Location(longitude=121.484623, latitude=31.236658),
        reason="预算宽松时可选的经典本帮菜。",
    ),
]

