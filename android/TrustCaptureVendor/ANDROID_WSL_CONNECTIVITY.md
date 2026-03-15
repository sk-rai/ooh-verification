# Android Emulator ↔ WSL Backend Connectivity Setup

## Problem
Android Emulator runs on Windows. The backend runs inside WSL2.
`10.0.2.2` (emulator's alias for host machine) maps to Windows localhost,
but WSL2 has its own network interface — so Windows localhost ≠ WSL localhost.

## Solution: Port Forwarding from Windows to WSL

### Step 1: Get WSL IP Address
Open Windows Command Prompt or PowerShell:
```
wsl hostname -I
```
Example output: `192.168.68.83`

**Note:** This IP can change on reboot. Re-run this command if connectivity breaks after restart.

### Step 2: Set Up Port Forwarding (Run as Administrator)
Right-click Start → Terminal (Admin) or PowerShell (Admin):
```powershell
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=<WSL_IP>
```
Replace `<WSL_IP>` with the IP from Step 1.

Example:
```powershell
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=192.168.68.83
```

### Step 3: Add Firewall Rule (Run as Administrator, one-time)
```powershell
netsh advfirewall firewall add rule name="Allow Port 8000" dir=in action=allow protocol=TCP localport=8000
```

### Step 4: Start Backend with 0.0.0.0 Binding
In WSL terminal:
```bash
cd ~/projects/trustcapture/backend
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
The `--host 0.0.0.0` is critical — without it, uvicorn only listens on 127.0.0.1 and rejects external connections.

### Step 5: Verify
From Windows CMD:
```
curl http://localhost:8000/
```
Expected: `{"message":"TrustCapture API","version":"1.0.0",...}`

From Android Emulator browser:
```
http://10.0.2.2:8000/api/docs
```
Expected: Swagger UI loads

## Troubleshooting

### Connection times out after reboot
WSL IP changed. Re-run Steps 1 and 2.

### Remove old port forwarding rule
```powershell
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0
```

### View current port forwarding rules
```powershell
netsh interface portproxy show all
```

### Quick Reset Script (run as Admin after each reboot)
```powershell
$wslIp = (wsl hostname -I).Trim()
netsh interface portproxy delete v4tov4 listenport=8000 listenaddress=0.0.0.0
netsh interface portproxy add v4tov4 listenport=8000 listenaddress=0.0.0.0 connectport=8000 connectaddress=$wslIp
Write-Host "Port forwarding set to WSL IP: $wslIp"
```
