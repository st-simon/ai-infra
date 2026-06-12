"""
前台调度器 — 每天自动运行新闻简报
用法: python scheduler.py --no-run-now

macOS 日常自动运行优先使用 docs/SCHEDULING.md 中的 launchd 方案。
本文件保留为开发/手动前台运行的备用方式。
"""
import argparse
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import subprocess
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
PYTHON_BIN = PROJECT_ROOT / ".venv" / "bin" / "python"

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M')

def run_briefing():
    logging.info("定时任务触发：开始生成简报...")
    result = subprocess.run(
        [str(PYTHON_BIN), "agents/news_briefing/agent.py"],
        cwd=PROJECT_ROOT,
        capture_output=True, text=True
    )
    if result.returncode == 0:
        logging.info("简报生成成功")
    else:
        logging.error(f"简报生成失败:\n{result.stderr}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Run the news briefing foreground scheduler.")
    parser.add_argument("--run-now", action="store_true", help="Generate one briefing immediately.")
    parser.add_argument("--no-run-now", action="store_true", help="Start scheduler without immediate run.")
    args = parser.parse_args()

    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    # 每天北京时间 07:00 运行
    scheduler.add_job(
        run_briefing,
        CronTrigger(hour=7, minute=0),
        id="daily_briefing"
    )
    logging.info("调度器启动，每天 07:00 BJT 自动生成简报")
    logging.info("按 Ctrl+C 停止")
    if args.run_now and not args.no_run_now:
        run_briefing()
    scheduler.start()
