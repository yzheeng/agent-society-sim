"""Web 观察台入口 —— 与 run.py(CLI 观察台)并列的另一种外壳。

跑:`uv run python run_web.py`,然后浏览器开 http://127.0.0.1:8000
模拟启动后默认【暂停】,在网页上按"步进 / 自动"推进 —— 不会一启动就烧 token。
"""
from __future__ import annotations

import uvicorn


def main() -> None:
    # reload=False:模块级会构造 world / Conductor,热重载会重复构造,这里不需要。
    uvicorn.run("ui.web.server:app", host="127.0.0.1", port=8000, reload=False)


if __name__ == "__main__":
    main()
