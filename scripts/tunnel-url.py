#!/usr/bin/env python3
import re
import argparse
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
parser = argparse.ArgumentParser()
parser.add_argument('--paid', action='store_true')
paid = parser.parse_args().paid
compose = ['docker', 'compose']
if paid:
    compose += ['-p', 'paid-quiz-paid', '--env-file', '.runtime/paid.env', '-f', 'docker-compose.yml', '-f', 'docker-compose.paid.yml']
env = root / ('.runtime/paid.env' if paid else '.env')
url_file = root / ('.runtime/paid-public-url.txt' if paid else '.runtime/public-url.txt')
for _ in range(30):
    logs = subprocess.run(compose + ['--profile', 'public', 'logs', '--no-color', 'tunnel'],
                          cwd=root, text=True, capture_output=True, check=True).stdout
    urls = re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com', logs)
    if urls:
        url = urls[-1]
        lines = env.read_text().splitlines()
        previous = next((line[9:] for line in lines if line.startswith('SITE_URL=')), '')
        lines = [line for line in lines if not line.startswith('SITE_URL=')]
        lines.append('SITE_URL=' + url)
        env.write_text('\n'.join(lines) + '\n')
        url_file.write_text(url + '\n')
        url_file.chmod(0o600)
        if previous != url:
            subprocess.run(compose + ['up', '-d', '--no-deps', '--wait', 'backend'], cwd=root, check=True)
        print(('完整收费版链接：' if paid else '客户测试链接：') + url)
        break
    time.sleep(2)
else:
    raise SystemExit('隧道未返回地址。请检查 docker compose --profile public logs tunnel。')
