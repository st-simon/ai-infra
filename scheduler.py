"""
定时调度器 — 每天自动运行新闻简报
用法: python scheduler.py
会在后台持续运行，每天 07:00 BJT 生成简报
"""
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
import subprocess
import logging
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s %(message)s',
                    datefmt='%Y-%m-%d %H:%M')

def run_briefing():
    logging.info("定时任务触发：开始生成简报...")
    result = subprocess.run(
        ["python", "agents/news_briefing/agent.py"],
        cwd=PROJECT_ROOT,
        capture_output=True, text=True
    )
    if result.returncode == 0:
        logging.info("简报生成成功")
    else:
        logging.error(f"简报生成失败:\n{result.stderr}")

if __name__ == "__main__":
    scheduler = BlockingScheduler(timezone="Asia/Shanghai")
    # 每天北京时间 07:00 运行
    scheduler.add_job(
        run_briefing,
        CronTrigger(hour=7, minute=0),
        id="daily_briefing"
    )
    logging.info("调度器启动，每天 07:00 BJT 自动生成简报")
    logging.info("按 Ctrl+C 停止")
    # 启动时立即运行一次
    run_briefing()
    scheduler.start()
