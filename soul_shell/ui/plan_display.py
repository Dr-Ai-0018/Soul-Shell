RISK_ICONS = {"low": "✓", "medium": "!", "high": "⚠", "unknown": "?"}


def print_plan(plan: dict) -> None:
    """打印 Managed Mode 的 JSON 执行计划"""
    goal = plan.get("goal", "未指定")
    steps = plan.get("steps", [])
    print(f"\n目标：{goal}\n")
    for step in steps:
        risk = step.get("risk", "unknown")
        icon = RISK_ICONS.get(risk, "?")
        print(f"  [{icon}] Step {step.get('id', '?')}: {step.get('desc', '')}")
        print(f"      {step.get('cmd', '')}")
    print()
