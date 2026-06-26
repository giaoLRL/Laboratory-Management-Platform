#!/usr/bin/env python3
"""Deploy v6.0 pixel-art upgrade to lab-manager server."""
import os
import paramiko

HOST = "8.163.127.7"
USER = "root"
PASS = "Giao666666"
PORT = 22
BASE = r"C:\Users\PC\Documents\实验室\netbox-main"
REMOTE_STATIC = "/opt/lab-manager/netbox/lab_manager/static/lab_manager"
REMOTE_TEMPLATES = "/opt/lab-manager/netbox/lab_manager/templates/lab_manager"
REMOTE_BASE_TEMPLATES = "/opt/lab-manager/netbox/templates/base"

files = [
    # CSS (v6.0: animations, particles, pixel icons, border-sweep, duplicate cleanup)
    ("netbox/lab_manager/static/lab_manager/terminal_pixel.css", REMOTE_STATIC),
    ("netbox/lab_manager/static/lab_manager/lab_manager.css", REMOTE_STATIC),
    # Base template (v6.0: tp-particles + tp-vignette DOM, v=14)
    ("netbox/templates/base/layout.html", REMOTE_BASE_TEMPLATES),
    # Templates
    ("netbox/lab_manager/templates/lab_manager/home.html", REMOTE_TEMPLATES),
    ("netbox/lab_manager/templates/lab_manager/agent_console.html", REMOTE_TEMPLATES),
    ("netbox/lab_manager/templates/lab_manager/notification_list.html", REMOTE_TEMPLATES),
    ("netbox/lab_manager/templates/lab_manager/checkin_form.html", REMOTE_TEMPLATES),
    ("netbox/lab_manager/templates/lab_manager/task.html", REMOTE_TEMPLATES),
    ("netbox/lab_manager/templates/lab_manager/task_edit.html", REMOTE_TEMPLATES),
    ("netbox/lab_manager/templates/lab_manager/task_edit_member.html", REMOTE_TEMPLATES),
    ("netbox/lab_manager/templates/lab_manager/task_upload.html", REMOTE_TEMPLATES),
    ("netbox/lab_manager/templates/lab_manager/checkin_detail.html", REMOTE_TEMPLATES),
    ("netbox/lab_manager/templates/lab_manager/hardware.html", REMOTE_TEMPLATES),
    ("netbox/lab_manager/templates/lab_manager/member_detail.html", REMOTE_TEMPLATES),
    ("netbox/lab_manager/templates/lab_manager/member_list.html", REMOTE_TEMPLATES),
    ("netbox/lab_manager/templates/lab_manager/member_open_record_list.html", REMOTE_TEMPLATES),
    ("netbox/lab_manager/templates/lab_manager/member_open_record_detail.html", REMOTE_TEMPLATES),
]

print("Connecting to server...")
ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
ssh.connect(HOST, PORT, USER, PASS, look_for_keys=False, allow_agent=False)
sftp = ssh.open_sftp()

for local, remote_dir in files:
    full_local = os.path.join(BASE, local)
    fname = os.path.basename(local)
    full_remote = remote_dir.rstrip('/') + '/' + fname
    print(f"  Uploading: {fname} → {full_remote}")
    sftp.put(full_local, full_remote)

sftp.close()

print("\nRunning: collectstatic --noinput")
stdin, stdout, stderr = ssh.exec_command(
    "cd /opt/lab-manager/netbox && /opt/lab-manager/venv/bin/python manage.py collectstatic --noinput 2>&1"
)
print(stdout.read().decode())
err = stderr.read().decode()
if err:
    print("STDERR:", err)

print("Restarting lab-manager service...")
stdin, stdout, stderr = ssh.exec_command("systemctl restart lab-manager 2>&1")
out = stdout.read().decode()
err = stderr.read().decode()
if out: print(out)
if err: print(err)

print("Checking service status...")
stdin, stdout, stderr = ssh.exec_command("systemctl status lab-manager --no-pager 2>&1 | head -12")
print(stdout.read().decode())

ssh.close()
print("\n=== Deploy v6.0 Complete ===")
print("Hard refresh (Ctrl+Shift+R) to see pixel-art animations!")
