"""
测试报告生成器
生成 JSON 结构化报告 + HTML 可视化报告
"""
import json
from datetime import datetime, timezone

REPORT_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>接口自动化测试报告</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #333; background: #f5f7fa; line-height: 1.6; }
        .container { max-width: 1000px; margin: 0 auto; padding: 24px; }

        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; padding: 32px; border-radius: 12px; margin-bottom: 24px; }
        .header h1 { font-size: 24px; margin-bottom: 8px; }
        .header .meta { font-size: 14px; opacity: 0.85; margin-top: 12px; }
        .header .meta span { margin-right: 24px; }

        .summary { display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }
        .summary-card { background: #fff; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .summary-card .num { font-size: 32px; font-weight: 700; }
        .summary-card .label { font-size: 13px; color: #888; margin-top: 4px; }
        .summary-card.total .num { color: #4a90d9; }
        .summary-card.passed .num { color: #52c41a; }
        .summary-card.failed .num { color: #f5222d; }
        .summary-card.error .num { color: #faad14; }
        .summary-card.rate .num { color: #667eea; font-size: 28px; }

        .section { background: #fff; border-radius: 10px; padding: 24px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }
        .section h2 { font-size: 18px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #f0f0f0; }

        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 14px; text-align: left; border-bottom: 1px solid #f0f0f0; font-size: 14px; }
        th { background: #fafafa; font-weight: 600; color: #555; }
        tr:hover { background: #f9f9ff; }

        .badge { display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }
        .badge-pass { background: #f6ffed; color: #52c41a; border: 1px solid #b7eb8f; }
        .badge-fail { background: #fff2f0; color: #f5222d; border: 1px solid #ffa39e; }
        .badge-error { background: #fffbe6; color: #d48806; border: 1px solid #ffe58f; }
        .badge-normal { background: #e6f7ff; color: #1890ff; border: 1px solid #91d5ff; }
        .badge-abnormal { background: #fff7e6; color: #fa8c16; border: 1px solid #ffd591; }
        .badge-boundary { background: #f9f0ff; color: #722ed1; border: 1px solid #d3adf7; }

        .method { font-weight: 700; font-size: 12px; padding: 2px 6px; border-radius: 4px; }
        .method-get { background: #e6f7ff; color: #1890ff; }
        .method-post { background: #f6ffed; color: #52c41a; }
        .method-put { background: #fff7e6; color: #fa8c16; }
        .method-delete { background: #fff2f0; color: #f5222d; }
        .method-patch { background: #f9f0ff; color: #722ed1; }

        .time-cell { color: #888; font-size: 13px; }
        .path-cell { font-family: monospace; font-size: 13px; word-break: break-all; }
        .issues-list { margin: 0; padding-left: 16px; font-size: 13px; color: #888; }

        .footer { text-align: center; padding: 24px; color: #aaa; font-size: 13px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>接口自动化测试报告</h1>
            <div class="meta">
                <span>任务ID: {{ task_id }}</span>
                <span>生成时间: {{ created_at }}</span>
            </div>
        </div>

        <div class="summary">
            <div class="summary-card total">
                <div class="num">{{ total }}</div>
                <div class="label">总计</div>
            </div>
            <div class="summary-card passed">
                <div class="num">{{ passed }}</div>
                <div class="label">通过</div>
            </div>
            <div class="summary-card failed">
                <div class="num">{{ failed }}</div>
                <div class="label">失败</div>
            </div>
            <div class="summary-card rate">
                <div class="num">{{ pass_rate }}%</div>
                <div class="label">通过率</div>
            </div>
        </div>

        <div class="section">
            <h2>测试结果详情</h2>
            <table>
                <thead>
                    <tr>
                        <th>用例标题</th>
                        <th>方法</th>
                        <th>路径</th>
                        <th>类型</th>
                        <th>预期状态码</th>
                        <th>实际状态码</th>
                        <th>耗时</th>
                        <th>结果</th>
                    </tr>
                </thead>
                <tbody>
                    {{#results}}
                    <tr>
                        <td>{{ title }}</td>
                        <td><span class="method method-{{ method_lower }}">{{ method }}</span></td>
                        <td class="path-cell">{{ path }}</td>
                        <td><span class="badge badge-{{ case_type_lower }}">{{ case_type }}</span></td>
                        <td>{{ expected_status }}</td>
                        <td>{{ response_status }}</td>
                        <td class="time-cell">{{ response_time_ms }}ms</td>
                        <td><span class="badge badge-{{ status_class }}">{{ status }}</span></td>
                    </tr>
                    {{/results}}
                </tbody>
            </table>
        </div>

        {{#failed_items}}
        <div class="section">
            <h2>失败用例详情</h2>
            {{#items}}
            <div style="margin-bottom: 20px; padding: 16px; background: #fff2f0; border-radius: 8px; border-left: 4px solid #f5222d;">
                <strong>{{ title }}</strong>
                <span class="badge badge-fail" style="margin-left: 8px;">失败</span>
                <p style="margin-top: 8px; font-size: 14px;">{{ ai_reason }}</p>
                {{#issues_list}}
                <ul class="issues-list" style="margin-top: 8px;">
                    {{#issues}}
                    <li>{{ . }}</li>
                    {{/issues}}
                </ul>
                {{/issues_list}}
            </div>
            {{/items}}
        </div>
        {{/failed_items}}

        <div class="footer">
            AI接口自动化测试Agent &copy; {{ year }}
        </div>
    </div>
</body>
</html>"""


class ReportGenerator:
    """报告生成器"""

    def generate(
        self,
        task_id: str,
        execution_id: str,
        results: list[dict],
    ) -> dict:
        """生成报告数据（JSON 摘要 + HTML 全文）"""
        total = len(results)
        passed = sum(1 for r in results if r.get("status") == "PASS")
        failed = sum(1 for r in results if r.get("status") == "FAIL")
        errors = total - passed - failed
        pass_rate = round(passed / total * 100, 1) if total > 0 else 0

        summary = {
            "task_id": task_id,
            "execution_id": execution_id,
            "total_cases": total,
            "passed": passed,
            "failed": failed,
            "error": errors,
            "pass_rate": pass_rate,
            "results": results,
        }

        html = self._render_html(task_id, results, total, passed, failed, errors, pass_rate)

        return {
            "task_id": task_id,
            "execution_id": execution_id,
            "total_cases": total,
            "passed": passed,
            "failed": failed,
            "error": errors,
            "pass_rate": pass_rate,
            "summary": json.dumps(summary, ensure_ascii=False),
            "html_content": html,
        }

    def _render_html(
        self,
        task_id: str,
        results: list[dict],
        total: int,
        passed: int,
        failed: int,
        errors: int,
        pass_rate: float,
    ) -> str:
        """使用简单模板替换生成 HTML（避免引入 Jinja2 依赖）"""
        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        # 渲染结果行
        result_rows = []
        for r in results:
            case = r.get("test_case", {})
            ai_val = r.get("ai_validation", {}) or {}
            status = r.get("status", "PENDING")

            status_class = {"PASS": "pass", "FAIL": "fail", "ERROR": "error"}.get(status, "error")
            case_type = case.get("case_type", "NORMAL")

            result_rows.append(self._subst(
                "<tr>"
                "<td>{{ title }}</td>"
                "<td><span class=\"method method-{{ method_lower }}\">{{ method }}</span></td>"
                "<td class=\"path-cell\">{{ path }}</td>"
                "<td><span class=\"badge badge-{{ case_type_lower }}\">{{ case_type }}</span></td>"
                "<td>{{ expected_status }}</td>"
                "<td>{{ response_status }}</td>"
                "<td class=\"time-cell\">{{ response_time_ms }}ms</td>"
                "<td><span class=\"badge badge-{{ status_class }}\">{{ status }}</span></td>"
                "</tr>",
                {
                    "title": case.get("title", ""),
                    "method": r.get("method", ""),
                    "method_lower": r.get("method", "").lower(),
                    "path": r.get("path", ""),
                    "case_type": case_type,
                    "case_type_lower": case_type.lower(),
                    "expected_status": str(case.get("expected_status", "")),
                    "response_status": str(r.get("response_status", "")),
                    "response_time_ms": str(r.get("response_time_ms", 0)),
                    "status": status,
                    "status_class": status_class,
                },
            ))

        # 失败用例详情
        failed_items = [r for r in results if r.get("status") == "FAIL"]
        failed_section = ""
        if failed_items:
            items_html = []
            for r in failed_items:
                case = r.get("test_case", {})
                ai_val = r.get("ai_validation", {}) or {}
                issues = ai_val.get("issues", [])
                issues_list = ""
                if issues:
                    issue_items = "".join(f"<li>{i}</li>" for i in issues)
                    issues_list = f'<ul class="issues-list" style="margin-top: 8px;">{issue_items}</ul>'
                items_html.append(self._subst(
                    '<div style="margin-bottom: 20px; padding: 16px; background: #fff2f0; border-radius: 8px; border-left: 4px solid #f5222d;">'
                    '<strong>{{ title }}</strong>'
                    '<span class="badge badge-fail" style="margin-left: 8px;">失败</span>'
                    '<p style="margin-top: 8px; font-size: 14px;">{{ ai_reason }}</p>'
                    '{{ issues_list }}'
                    '</div>',
                    {
                        "title": case.get("title", ""),
                        "ai_reason": ai_val.get("reason", ""),
                        "issues_list": issues_list,
                    },
                ))
            failed_section = self._subst(
                '<div class="section"><h2>失败用例详情</h2>{{ items }}</div>',
                {"items": "".join(items_html)},
            )

        # 组装完整 HTML
        html = REPORT_HTML_TEMPLATE
        html = html.replace("{{ task_id }}", task_id)
        html = html.replace("{{ created_at }}", now_str)
        html = html.replace("{{ total }}", str(total))
        html = html.replace("{{ passed }}", str(passed))
        html = html.replace("{{ failed }}", str(failed))
        html = html.replace("{{ pass_rate }}", str(pass_rate))
        html = html.replace("{{ year }}", str(datetime.now(timezone.utc).year))

        # 替换结果行
        html = html.replace("{{#results}}", "")
        html = html.replace("{{/results}}", "")
        # 在实际模板中，我们需要精确替换
        # 采用更可靠的方式：构建整个 HTML
        result_table = "".join(result_rows)

        return self._build_html(
            task_id, now_str, total, passed, failed, pass_rate, result_table, failed_section
        )

    def _subst(self, template: str, values: dict) -> str:
        """简单模板替换"""
        result = template
        for key, val in values.items():
            result = result.replace(f"{{{{ {key} }}}}", val)
        return result

    def _build_html(
        self,
        task_id: str,
        created_at: str,
        total: int,
        passed: int,
        failed: int,
        pass_rate: float,
        result_rows: str,
        failed_section: str,
    ) -> str:
        """构建完整的 HTML 报告"""
        year = datetime.now(timezone.utc).year

        return f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>接口自动化测试报告</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; color: #333; background: #f5f7fa; line-height: 1.6; }}
        .container {{ max-width: 1000px; margin: 0 auto; padding: 24px; }}
        .header {{ background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: #fff; padding: 32px; border-radius: 12px; margin-bottom: 24px; }}
        .header h1 {{ font-size: 24px; margin-bottom: 8px; }}
        .header .meta {{ font-size: 14px; opacity: 0.85; margin-top: 12px; }}
        .header .meta span {{ margin-right: 24px; }}
        .summary {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
        .summary-card {{ background: #fff; border-radius: 10px; padding: 20px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
        .summary-card .num {{ font-size: 32px; font-weight: 700; }}
        .summary-card .label {{ font-size: 13px; color: #888; margin-top: 4px; }}
        .summary-card.total .num {{ color: #4a90d9; }}
        .summary-card.passed .num {{ color: #52c41a; }}
        .summary-card.failed .num {{ color: #f5222d; }}
        .summary-card.rate .num {{ color: #667eea; font-size: 28px; }}
        .section {{ background: #fff; border-radius: 10px; padding: 24px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }}
        .section h2 {{ font-size: 18px; margin-bottom: 16px; padding-bottom: 8px; border-bottom: 2px solid #f0f0f0; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 10px 14px; text-align: left; border-bottom: 1px solid #f0f0f0; font-size: 14px; }}
        th {{ background: #fafafa; font-weight: 600; color: #555; }}
        tr:hover {{ background: #f9f9ff; }}
        .badge {{ display: inline-block; padding: 2px 10px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
        .badge-pass {{ background: #f6ffed; color: #52c41a; border: 1px solid #b7eb8f; }}
        .badge-fail {{ background: #fff2f0; color: #f5222d; border: 1px solid #ffa39e; }}
        .badge-error {{ background: #fffbe6; color: #d48806; border: 1px solid #ffe58f; }}
        .badge-normal {{ background: #e6f7ff; color: #1890ff; border: 1px solid #91d5ff; }}
        .badge-abnormal {{ background: #fff7e6; color: #fa8c16; border: 1px solid #ffd591; }}
        .badge-boundary {{ background: #f9f0ff; color: #722ed1; border: 1px solid #d3adf7; }}
        .method {{ font-weight: 700; font-size: 12px; padding: 2px 6px; border-radius: 4px; }}
        .method-get {{ background: #e6f7ff; color: #1890ff; }}
        .method-post {{ background: #f6ffed; color: #52c41a; }}
        .method-put {{ background: #fff7e6; color: #fa8c16; }}
        .method-delete {{ background: #fff2f0; color: #f5222d; }}
        .method-patch {{ background: #f9f0ff; color: #722ed1; }}
        .time-cell {{ color: #888; font-size: 13px; }}
        .path-cell {{ font-family: monospace; font-size: 13px; word-break: break-all; }}
        .footer {{ text-align: center; padding: 24px; color: #aaa; font-size: 13px; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>接口自动化测试报告</h1>
            <div class="meta">
                <span>任务ID: {task_id}</span>
                <span>生成时间: {created_at}</span>
            </div>
        </div>
        <div class="summary">
            <div class="summary-card total">
                <div class="num">{total}</div>
                <div class="label">总计</div>
            </div>
            <div class="summary-card passed">
                <div class="num">{passed}</div>
                <div class="label">通过</div>
            </div>
            <div class="summary-card failed">
                <div class="num">{failed}</div>
                <div class="label">失败</div>
            </div>
            <div class="summary-card rate">
                <div class="num">{pass_rate}%</div>
                <div class="label">通过率</div>
            </div>
        </div>
        <div class="section">
            <h2>测试结果详情</h2>
            <table>
                <thead>
                    <tr>
                        <th>用例标题</th>
                        <th>方法</th>
                        <th>路径</th>
                        <th>类型</th>
                        <th>预期状态码</th>
                        <th>实际状态码</th>
                        <th>耗时</th>
                        <th>结果</th>
                    </tr>
                </thead>
                <tbody>
                    {result_rows}
                </tbody>
            </table>
        </div>
        {failed_section}
        <div class="footer">
            AI接口自动化测试Agent &copy; {year}
        </div>
    </div>
</body>
</html>"""
