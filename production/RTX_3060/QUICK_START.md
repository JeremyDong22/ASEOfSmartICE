# 快速启动指南

## 🚀 超简单 3 步部署

### 步骤 1: 配置
```bash
python3 main.py
```
**做什么：**
- 交互式配置摄像头
- 画 ROI 区域
- 测试连接
- 配置完成后自动提示下一步

---

### 步骤 2: 安装 Systemd（首次，只做一次）
```bash
sudo bash scripts/deployment/install_systemd.sh
```
**做什么：**
- 自动安装系统服务
- 设置开机自启
- 配置自动重启

---

### 步骤 3: 启动服务
```bash
sudo systemctl start ase_surveillance
```
**做什么：**
- 启动监控服务
- 自动录制视频
- 自动处理分析

---

## 📋 日常管理命令

```bash
# 检查状态
sudo systemctl status ase_surveillance

# 停止服务
sudo systemctl stop ase_surveillance

# 重启服务
sudo systemctl restart ase_surveillance

# 查看实时日志
sudo journalctl -u ase_surveillance -f
```

---

## 🔄 重新配置

如果需要修改摄像头、ROI 等：

```bash
# 1. 停止服务
sudo systemctl stop ase_surveillance

# 2. 重新配置
python3 main.py

# 3. 重启服务
sudo systemctl start ase_surveillance
```

---

## ✅ 就这么简单！

**首次部署：**
1. `python3 main.py` → 配置
2. `sudo bash scripts/deployment/install_systemd.sh` → 安装
3. `sudo systemctl start ase_surveillance` → 启动

**以后：**
- `sudo systemctl restart ase_surveillance` → 重启

---

**版本:** 4.0.0
**更新:** 2025-11-16
