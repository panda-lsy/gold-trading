#!/usr/bin/env python3
"""
独立 K 线采集进程。
用于从 API 进程中解耦价格记录职责。
"""
import argparse
import logging
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / 'src'
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from jijin_trader import find_working_proxy
from kline_service import KlineService

logger = logging.getLogger(__name__)


def record_once(service: KlineService):
    ok_count = 0
    for bank in ('zheshang', 'minsheng'):
        try:
            ok = service.record_price(bank)
            if ok:
                ok_count += 1
            else:
                logger.warning('K线采集失败(%s): no data', bank)
        except Exception as exc:
            logger.warning('K线采集失败(%s): %s', bank, exc)
    return ok_count


def main():
    parser = argparse.ArgumentParser(description='K线采集独立进程')
    parser.add_argument('--interval', type=int, default=30, help='采集周期（秒）')
    parser.add_argument('--once', action='store_true', help='只采集一次')
    args = parser.parse_args()

    if args.interval < 5:
        raise ValueError('interval must be >= 5 seconds')

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s %(levelname)s %(name)s - %(message)s'
    )

    proxy = find_working_proxy()
    service = KlineService(proxy=proxy)

    logger.info('K线采集进程启动，interval=%ss, proxy=%s', args.interval, proxy or 'direct')

    if args.once:
        ok_count = record_once(service)
        logger.info('单次采集完成，成功银行数=%s', ok_count)
        return

    while True:
        ok_count = record_once(service)
        logger.info('本轮采集完成，成功银行数=%s', ok_count)
        time.sleep(args.interval)


if __name__ == '__main__':
    main()
