from .models import PlanCityDayResponse


def render_action_card(plan: PlanCityDayResponse) -> str:
    route_lines = []
    for index, stop in enumerate(plan.route, start=1):
        route_lines.append(
            f"{index}. {stop.arrival} 到达 {stop.name}，停留 {stop.stay_minutes} 分钟。{stop.note}"
        )

    leg_lines = []
    for leg in plan.legs:
        leg_lines.append(
            f"- {leg.from_place} -> {leg.to_place}: {leg.transport}，"
            f"{round(leg.distance_m / 1000, 1)} km，约 {leg.duration_min} 分钟"
        )

    food = plan.food_recommendations[0] if plan.food_recommendations else None
    food_line = (
        f"{food.name}（靠近 {food.near_stop}，人均约 {food.avg_price_cny} 元）：{food.reason}"
        if food
        else "本轮没有合适餐厅，建议现场按预算就近选择。"
    )
    warnings = "\n".join(f"- {warning}" for warning in plan.feasibility.warnings) or "- 暂无明显风险。"

    return f"""## 今日行动卡

**路线**
{chr(10).join(route_lines)}

**交通与顺路判断**
{chr(10).join(leg_lines)}

**餐饮推荐**
{food_line}

**预算**
- 预计总花费：{plan.budget_ledger.planned_total} 元
- 剩余预算：{plan.budget_ledger.remaining} 元
- 风险等级：{plan.budget_ledger.risk}

**多人冲突调和**
{plan.conflict_resolution}

**时间可行性**
- 状态：{plan.feasibility.status}
{warnings}

**地图图示**
![路线地图]({plan.static_map_url})

**PlanB触发条件**
- 下雨、临时闭馆、体力下降、预算超支、想新增地点时，告诉我变化，我会保留已完成行程并重排后续。
"""

