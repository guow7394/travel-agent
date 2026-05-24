# Coze 工作流配置

## 1. 建档与需求收集

触发：用户首次规划、信息不足、或说“帮我规划一天”。

步骤：

1. 读取 `travel_style_profile`、`traveler_preferences`、`planning_mode`。
2. 提取本轮输入里的城市、日期、时间窗、预算、人数、起终点、候选地点。
3. 如果缺关键字段，返回追问。
4. 把新偏好合并到 `traveler_preferences`。
5. 输出可传给 `路线规划` 工作流的结构化参数。

## 2. 路线规划

触发：信息齐全后。

步骤：

1. 调用插件工具 `planCityDay`。
2. 保存返回的 `budget_ledger` 到记忆字段。
3. 如果返回 `mocked=true`，在回复中说明当前使用演示兜底路线。
4. 输出 `action_card_markdown`。

## 3. PlanB 重规划

触发：用户说下雨、太累、改变预算、临时加点/删点、闭馆、想提前结束等。

步骤：

1. 从最近一次计划里拿 `current_plan`。
2. 询问或提取已完成地点 `completed_places`。
3. 调用插件工具 `planB`。
4. 更新 `budget_ledger`。
5. 输出新版行动卡，并明确“哪些保留、哪些调整、为什么”。

## 4. 旅行复盘

触发：用户说“结束了”“复盘一下”“下次优化”。

步骤：

1. 收集实际花费、喜欢的地点、不喜欢/累的点、遗憾。
2. 调用插件工具 `tripReview`。
3. 将返回的 `memory_write_suggestion.travel_style_profile` 写入 `travel_style_profile`。
4. 将 `memory_write_suggestion.last_trip_review` 写入 `last_trip_review`。
5. 输出下次优化建议。

