"""
Daily Scheduler
Runs lead generation automatically every day at a set time.

Usage:
  python scheduler.py              # Start scheduler (runs daily at 08:00)
  python scheduler.py --time 09:30 # Run daily at 09:30
  python scheduler.py --now        # Run immediately then schedule

Install as a background process:
  pythonw scheduler.py             # Run without console window (Windows)
"""
import argparse
import logging
import sys
import time
from datetime import datetime

import schedule

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def run_daily_job():
    logger.info("═" * 50)
    logger.info(f"🚀 Starting daily lead generation run — {datetime.now().strftime('%Y-%m-%d %H:%M')}")
    logger.info("═" * 50)
    try:
        from main import run
        leads = run()
        logger.info(f"✅ Done — {len(leads)} leads found and saved.")
    except Exception as e:
        logger.error(f"❌ Daily run failed: {e}", exc_info=True)


def main():
    parser = argparse.ArgumentParser(description="AstiScale Lead Generation Scheduler")
    parser.add_argument("--time", default="08:00", help="Daily run time HH:MM (default: 08:00)")
    parser.add_argument("--now", action="store_true", help="Run immediately and then schedule")
    args = parser.parse_args()

    run_time = args.time

    if args.now:
        logger.info("Running immediately...")
        run_daily_job()

    logger.info(f"⏰ Scheduler started — will run daily at {run_time}")
    schedule.every().day.at(run_time).do(run_daily_job)

    while True:
        schedule.run_pending()
        time.sleep(60)


if __name__ == "__main__":
    main()
