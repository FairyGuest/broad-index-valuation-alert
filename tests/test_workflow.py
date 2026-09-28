"""workflow 文件结构校验。

背景:曾因 YAML 键缩进错位(workflow_dispatch.inputs 被挤入 env 嵌套)导致
GitHub 解析后 "No jobs were run",定时任务全部静默失败。此测试在本地
拦截同类结构错误:YAML 本身合法但语义错位的文件,safe_load 不会报错,
必须靠结构断言捕捉。
"""
import pathlib

import yaml

WORKFLOWS = pathlib.Path(__file__).parent.parent / ".github" / "workflows"


def _load(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def test_monitor_workflow_structure():
    wf = _load("monitor.yml")
    # YAML 1.1 会把裸 on 键解析为布尔 True
    on_key = "on" if "on" in wf else True
    assert set(wf) == {"name", on_key, "env", "permissions", "concurrency", "jobs"}, \
        f"出现意外顶层键(可能是缩进错位):{set(wf)!r}"
    on = wf[on_key]
    assert isinstance(on, dict) and "schedule" in on and "workflow_dispatch" in on
    assert on["schedule"], "schedule 不能为空"
    # inputs 必须挂在 workflow_dispatch 下,而不是别处
    assert "inputs" in on["workflow_dispatch"], "workflow_dispatch 的 inputs 丢失"
    # env 必须是扁平的字符串映射
    for key, value in wf["env"].items():
        assert isinstance(value, str), f"env.{key} 的值必须是标量,当前:{value!r}"
    assert wf["jobs"], "jobs 不能为空"


def test_test_workflow_structure():
    wf = _load("test.yml")
    assert wf.get("jobs"), "test.yml jobs 不能为空"
