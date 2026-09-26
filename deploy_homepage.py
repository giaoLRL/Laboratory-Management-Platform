"""官网静态同步（P0）：备份 → 上传 → sha256 校验 → 线上冒烟
用法：python deploy_homepage.py [文件名...]  （相对 lab-platform/homepage/，默认 index.html + assets/site.css + assets/site.js）
"""
import paramiko
import hashlib
import os
import sys
import time

HOST, PORT, USER, PWD = "8.134.143.82", 22, "root", "Giao666666"
LIVE = "/opt/lab/homepage"
LOCAL = os.path.join(r"c:\Users\PC\Documents\实验室", "lab-platform", "homepage")
STAMP = time.strftime("%Y%m%d-%H%M%S")

FILES = sys.argv[1:] or ["index.html", "assets/site.css", "assets/site.js"]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, port=PORT, username=USER, password=PWD, timeout=30)


def run(cmd, t=180):
    _, o, e = ssh.exec_command(cmd, timeout=t)
    return (o.read().decode(errors="replace") + e.read().decode(errors="replace")).strip()


def sha(b):
    return hashlib.sha256(b).hexdigest()


print("=== 1) 备份现网官网 ===")
print(" ", run(f"mkdir -p /opt/lab/backup/homepage-{STAMP} && cp -a {LIVE}/index.html {LIVE}/assets /opt/lab/backup/homepage-{STAMP}/ && du -sh /opt/lab/backup/homepage-{STAMP}"))

print("\n=== 2) 上传 + 校验 ===")
sftp = ssh.open_sftp()
for rel in FILES:
    local_path = os.path.join(LOCAL, rel.replace("/", os.sep))
    data = open(local_path, "rb").read()
    remote = f"{LIVE}/{rel}"
    sftp.put(local_path, remote)
    with sftp.open(remote, "rb") as f:
        got = f.read()
    ok = sha(data) == sha(got)
    sftp.chmod(remote, 0o644)
    print(f"  {'MATCH  ' if ok else 'MISMATCH'} {rel} ({len(data)} 字节)")
    assert ok, rel
sftp.close()
run(f"chmod 755 {LIVE} {LIVE}/assets")

print("\n=== 3) 线上冒烟 ===")
print("  index.html:", run("curl -sk -o /dev/null -w '%{http_code}' https://wuyuan.me/"))
print("  site.css  :", run("curl -sk -o /dev/null -w '%{http_code}' https://wuyuan.me/assets/site.css?v=2"))
print("  site.js   :", run("curl -sk -o /dev/null -w '%{http_code}' https://wuyuan.me/assets/site.js?v=2"))
print("  关键规则  :", run("grep -c 'hp-focus-x\\|hp-ar' /opt/lab/homepage/assets/site.css"))
print("  竖版 Hero :", run("grep -c 'hp-portrait' /opt/lab/homepage/assets/site.css /opt/lab/homepage/assets/site.js"))
print("  页面引用  :", run("grep -o 'site\\.[a-z]*?v=[0-9]*' /opt/lab/homepage/index.html | tr '\\n' ' '"))
print("  抽离后大小:", run(f"wc -c < {LIVE}/index.html"), "字节")
print(f"\nDONE（备份 /opt/lab/backup/homepage-{STAMP}）")