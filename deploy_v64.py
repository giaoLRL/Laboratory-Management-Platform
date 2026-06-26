import paramiko
import os
import sys

host = "8.163.127.7"
port = 22
username = "root"
password = "Giao666666"

local_base = r"C:\Users\PC\Documents\实验室\netbox-main\netbox"
remote_base = "/opt/lab-manager/netbox-main/netbox"

files = [
    (os.path.join(local_base, "lab_manager", "static", "lab_manager", "terminal_pixel.css"),
     os.path.join(remote_base, "lab_manager", "static", "lab_manager", "terminal_pixel.css")),
    (os.path.join(local_base, "lab_manager", "static", "lab_manager", "lab_manager.css"),
     os.path.join(remote_base, "lab_manager", "static", "lab_manager", "lab_manager.css")),
    (os.path.join(local_base, "lab_manager", "templates", "lab_manager", "agent_console.html"),
     os.path.join(remote_base, "lab_manager", "templates", "lab_manager", "agent_console.html")),
    (os.path.join(local_base, "templates", "base", "layout.html"),
     os.path.join(remote_base, "templates", "base", "layout.html")),
]

ssh = paramiko.SSHClient()
ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
print(f"Connecting to {host}:{port}...")
ssh.connect(host, port=port, username=username, password=password, timeout=30)
print("Connected.")

sftp = ssh.open_sftp()

for local_path, remote_path in files:
    if not os.path.exists(local_path):
        print(f"SKIP (not found): {local_path}")
        continue
    print(f"Uploading: {os.path.basename(local_path)} -> {remote_path}")
    sftp.put(local_path, remote_path)

sftp.close()
print("All files uploaded.")

# Run collectstatic and restart
print("Running collectstatic...")
stdin, stdout, stderr = ssh.exec_command(
    "cd /opt/lab-manager/netbox-main/netbox && "
    "source ../venv/bin/activate && "
    "python manage.py collectstatic --noinput 2>&1",
    timeout=60
)
out = stdout.read().decode()
err = stderr.read().decode()
print("STDOUT:", out[:500])
if err:
    print("STDERR:", err[:500])

print("Restarting lab-manager service...")
stdin, stdout, stderr = ssh.exec_command("systemctl restart lab-manager 2>&1", timeout=30)
out = stdout.read().decode()
err = stderr.read().decode()
if out:
    print("STDOUT:", out)
if err:
    print("STDERR:", err)

# Verify service status
stdin, stdout, stderr = ssh.exec_command("systemctl is-active lab-manager && echo '---' && systemctl status lab-manager --no-pager -l | head -5", timeout=15)
out = stdout.read().decode()
print("Service status:", out.strip())

ssh.close()
print("Deployment complete.")
