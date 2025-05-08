# StreamCap API 服务

StreamCap API 是一个基于 FastAPI 的 RESTful API 服务，用于控制直播流录制程序。它提供了启动录制、监控直播、查看状态和停止录制等功能。

## 功能特点

- 支持通过 API 启动和停止直播录制
- 支持两种模式：直接录制(record)和监控直播(monitor)
- 提供完整的状态查询接口
- 支持多种录制参数自定义
- 支持按 ID 或 URL 停止特定录制任务
- 支持一键停止所有录制任务

## 系统要求

- Python 3.8 或更高版本
- FFmpeg（用于录制功能）
- 相关 Python 依赖包（见 requirements.txt）

## 安装

### Windows

运行安装脚本:

```
setup.bat
```

### Linux/Mac

运行安装脚本:

```
chmod +x setup.sh
./setup.sh
```

## 启动服务

### Windows

运行启动脚本:

```
start_server.bat
```

或直接运行:

```
python api_server.py --host 0.0.0.0 --port 8000
```

### Linux/Mac

运行启动脚本:

```
chmod +x start_server.sh
./start_server.sh
```

或直接运行:

```
python3 api_server.py --host 0.0.0.0 --port 8000
```

启动后，API 服务将在 http://localhost:8000 上运行，你可以访问 http://localhost:8000/docs 查看交互式 API 文档。

## API 使用说明

### 1. 启动录制或监控

**POST /record**

```json
{
  "url": "https://live.douyin.com/123456789",
  "mode": "monitor",
  "output_dir": "recordings",
  "format": "mp4",
  "quality": "原画",
  "segment": true,
  "segment_time": 1800,
  "interval": 30
}
```

主要参数说明:
- `url`: 直播地址
- `mode`: 模式，`record`(直接录制) 或 `monitor`(监控直播并自动录制)
- `output_dir`: 输出目录
- `format`: 格式，支持 `mp4`、`flv`、`ts`
- `quality`: 画质，支持 `原画`、`高清`、`标清`、`流畅`
- `segment`: 是否分段录制
- `segment_time`: 分段时长(秒)
- `interval`: 监控模式下的检查间隔(秒)

### 2. 查询录制状态

**GET /status**

返回所有正在运行的录制任务列表。

### 3. 停止录制

**POST /stop**

```json
{
  "id": 1,
  "url": null,
  "all": false
}
```

参数说明:
- `id`: 录制任务ID (从状态查询获取)
- `url`: 直播URL (部分匹配即可)
- `all`: 是否停止所有录制任务

三个参数选择其一使用：
- 按ID停止: 设置 `id` 参数
- 按URL停止: 设置 `url` 参数
- 停止所有: 设置 `all: true`

## 测试 API

使用提供的测试脚本测试 API 功能:

### Windows

```
test_api.bat [直播URL] [模式] [等待时间]
```

### Linux/Mac

```
chmod +x test_api.sh
./test_api.sh [直播URL] [模式] [等待时间]
```

参数说明:
- `直播URL`: 直播地址，默认为 `https://live.douyin.com/895511283289`
- `模式`: `record` 或 `monitor`，默认为 `monitor`
- `等待时间`: 测试运行时间(秒)，默认为 30秒

## 测试案例

以下是几个使用cURL命令测试API的示例：

### 测试案例1: 检查API服务状态

```bash
curl -X GET http://localhost:8000/
```

预期响应:
```json
{
  "success": true,
  "message": "StreamCap API 服务正在运行",
  "data": {
    "version": "1.0.0",
    "description": "直播流录制服务API"
  }
}
```

### 测试案例2: 启动录制抖音直播

```bash
curl -X POST http://localhost:8000/record \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/895511283289",
    "mode": "record",
    "output_dir": "recordings",
    "format": "mp4",
    "quality": "原画",
    "segment": true,
    "segment_time": 1800
  }'
```

预期响应:
```json
{
  "success": true,
  "message": "已成功启动录制: https://live.douyin.com/895511283289",
  "data": {
    "pid": 12345,
    "command": "python start.py https://live.douyin.com/895511283289 -m record -o recordings -f mp4 -q 原画 --segment-time 1800"
  }
}
```

### 测试案例3: 启动监控抖音直播

```bash
curl -X POST http://localhost:8000/record \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/895511283289",
    "mode": "monitor",
    "output_dir": "recordings",
    "format": "mp4",
    "interval": 30
  }'
```

预期响应:
```json
{
  "success": true,
  "message": "已成功启动监控: https://live.douyin.com/895511283289",
  "data": {
    "pid": 12346,
    "command": "python start.py https://live.douyin.com/895511283289 -m monitor -o recordings -f mp4 -i 30"
  }
}
```

### 测试案例4: 查询录制状态

```bash
curl -X GET http://localhost:8000/status
```

预期响应:
```json
{
  "success": true,
  "message": "找到 2 个正在运行的录制进程",
  "data": {
    "recordings": [
      {
        "id": 1,
        "pid": 12345,
        "is_recording": true,
        "is_monitoring": false,
        "url": "https://live.douyin.com/895511283289",
        "timestamp": 1684123456.789
      },
      {
        "id": 2,
        "pid": 12346,
        "is_recording": false,
        "is_monitoring": true,
        "url": "https://live.douyin.com/895511283289",
        "timestamp": 1684123456.789
      }
    ]
  }
}
```

### 测试案例5: 按ID停止录制

```bash
curl -X POST http://localhost:8000/stop \
  -H "Content-Type: application/json" \
  -d '{
    "id": 1
  }'
```

预期响应:
```json
{
  "success": true,
  "message": "已发送停止信号到进程 12345, URL: https://live.douyin.com/895511283289"
}
```

### 测试案例6: 按URL停止录制

```bash
curl -X POST http://localhost:8000/stop \
  -H "Content-Type: application/json" \
  -d '{
    "url": "895511283289"
  }'
```

预期响应:
```json
{
  "success": true,
  "message": "已发送停止信号到进程 12346, URL: https://live.douyin.com/895511283289"
}
```

### 测试案例7: 停止所有录制

```bash
curl -X POST http://localhost:8000/stop \
  -H "Content-Type: application/json" \
  -d '{
    "all": true
  }'
```

预期响应:
```json
{
  "success": true,
  "message": "已发送停止信号到进程 12345, URL: https://live.douyin.com/895511283289; 已发送停止信号到进程 12346, URL: https://live.douyin.com/895511283289"
}
```

## 集成到其他应用

如果您需要将StreamCap API集成到其他应用中，以下是使用Python的requests库进行集成的示例代码:

```python
import requests
import json

API_BASE_URL = "http://localhost:8000"

def start_recording(live_url, mode="record"):
    """启动录制或监控"""
    endpoint = f"{API_BASE_URL}/record"
    data = {
        "url": live_url,
        "mode": mode,
        "output_dir": "recordings",
        "format": "mp4",
        "quality": "原画",
        "segment": True
    }
    
    response = requests.post(endpoint, json=data)
    if response.status_code == 200:
        result = response.json()
        print(f"录制任务已启动，进程ID: {result['data']['pid']}")
        return result
    else:
        print(f"启动失败: {response.text}")
        return None

def check_status():
    """获取所有录制状态"""
    endpoint = f"{API_BASE_URL}/status"
    response = requests.get(endpoint)
    if response.status_code == 200:
        result = response.json()
        recordings = result["data"]["recordings"]
        print(f"当前有 {len(recordings)} 个录制任务运行中")
        for rec in recordings:
            status = "录制中" if rec["is_recording"] else "监控中"
            print(f"ID: {rec['id']}, PID: {rec['pid']}, 状态: {status}, URL: {rec['url']}")
        return recordings
    else:
        print(f"获取状态失败: {response.text}")
        return []

def stop_recording_by_url(url):
    """停止指定URL的录制任务"""
    endpoint = f"{API_BASE_URL}/stop"
    data = {"url": url}
    
    response = requests.post(endpoint, json=data)
    if response.status_code == 200:
        result = response.json()
        print(result["message"])
        return True
    else:
        print(f"停止失败: {response.text}")
        return False

# 使用示例
if __name__ == "__main__":
    # 启动录制
    start_recording("https://live.douyin.com/895511283289")
    
    # 检查状态
    recordings = check_status()
    
    # 如果有录制任务，停止它
    if recordings:
        stop_recording_by_url("895511283289")
```

## 开发和扩展

API 服务基于 FastAPI 开发，你可以根据需要进行以下扩展:

1. 添加新的 API 端点
2. 增强录制参数
3. 添加用户验证和授权
4. 添加持久化存储和数据库支持
5. 添加前端界面

## 常见问题

1. **服务启动失败**: 检查端口是否被占用，可以通过 `--port` 参数指定其他端口
2. **录制无法开始**: 检查 FFmpeg 是否正确安装，以及网络连接是否正常
3. **无法停止录制**: 检查进程状态，可能需要手动终止进程

## 许可

本项目采用 MIT 许可证。 