from typing import Any, Dict, List

from .models import TripReviewRequest, TripReviewResponse


def review_trip(request: TripReviewRequest) -> TripReviewResponse:
    profile: Dict[str, Any] = dict(request.previous_profile)
    likes = set(profile.get("likes", []))
    for place in request.liked_places:
        if "外滩" in place or "夜景" in request.trip_summary:
            likes.add("夜景")
        if "博物馆" in place:
            likes.add("博物馆")
    profile["likes"] = sorted(likes)

    pain_text = " ".join(request.pain_points + [request.trip_summary])
    if "走太多" in pain_text or "步行太多" in pain_text or "太累" in pain_text:
        profile["pace"] = "low_energy"
    else:
        profile.setdefault("pace", "balanced")

    remaining = request.budget_total_cny - request.actual_spend_cny
    if remaining >= 0:
        budget_learning = f"本次剩余 {remaining} 元，下次可保留 10%-20% 机动预算。"
    else:
        budget_learning = f"本次超支 {abs(remaining)} 元，下次需要提前锁定交通和餐饮上限。"

    optimizations: List[str] = []
    if profile.get("pace") == "low_energy":
        optimizations.append("下一次默认减少连续步行路段，午后加入固定休息点。")
    if "夜景" in likes:
        optimizations.append("保留傍晚到夜间的地标拍照窗口，白天减少同质化街区。")
    if remaining > request.budget_total_cny * 0.1:
        optimizations.append("预算有余量，可以给特色餐厅或打车留一个升级选项。")

    return TripReviewResponse(
        updated_profile=profile,
        next_trip_optimizations=optimizations,
        budget_learning=budget_learning,
        memory_write_suggestion={
            "travel_style_profile": profile,
            "last_trip_review": {
                "liked_places": request.liked_places,
                "pain_points": request.pain_points,
                "actual_spend_cny": request.actual_spend_cny,
                "budget_total_cny": request.budget_total_cny,
            },
        },
    )

