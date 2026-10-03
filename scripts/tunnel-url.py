#!/usr/bin/env python3
import re
import subprocess
import time
from pathlib import Path

root = Path(__file__).resolve().parent.parent
for _ in range(30):
    logs = subprocess.run(['docker', 'compose', '--profile', 'public', 'logs', '--no-color', 'tunnel'],
                          cwd=root, text=True, capture_output=True, check=True).stdout
    urls = re.findall(r'https://[a-z0-9-]+\.trycloudflare\.com', logs)
    if urls:
        url = urls[-1]
        env = root / '.env'
        lines = env.read_text().splitlines()
        lines = [line for line in lines if not line.startswith('SITE_URL=')]
        lines.append('SITE_URL=' + url)
        env.write_text('\n'.join(lines) + '\n')
        (root / '.runtime/public-url.txt').write_text(url + '\n')
        subprocess.run(['docker', 'compose', 'up', '-d', '--no-deps', 'backend'], cwd=root, check=True)
        print('客户测试链接：' + url)
        break
    time.sleep(2)
else:
    raise SystemExit('隧道未返回地址。请检查 docker compose --profile public logs tunnel。')
