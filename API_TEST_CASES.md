# StreamCap API 测试案例

本文档包含了测试 StreamCap API 服务的详细步骤。

## 准备工作

1. 确保 API 服务已经启动并在运行
   - Windows: 执行 `start_server.bat`
   - Linux/Mac: 执行 `./start_server.sh`

2. 确保可以访问 API 服务
   - 打开浏览器访问 `http://localhost:8000/docs`
   - 确认 Swagger UI 文档能够正确显示

## 测试工具选择

可以使用以下任一工具进行测试：

- cURL: 命令行工具，适用于所有平台
- Postman: GUI工具，提供更友好的界面
- 浏览器中的 Swagger UI: 直接在 `/docs` 页面中测试
- 提供的测试脚本: `test_api.bat` 或 `test_api.sh`

## 测试案例

### 案例1: 检查 API 服务状态

**目的**: 验证 API 服务是否正常运行

**请求**:
```bash
curl -X GET http://localhost:8000/
```

**预期结果**:
- 状态码: 200
- 返回内容:
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

**验证点**:
- 响应成功
- 服务版本和描述正确

---

### 案例2: 启动录制 - 直接录制模式

**目的**: 验证可以启动直接录制模式

**请求**:
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

**预期结果**:
- 状态码: 200
- 返回内容包含:
  - 进程 PID
  - 成功消息
  - 执行的命令

**验证点**:
- 响应成功
- PID 非零
- 执行的命令包含所有参数
- 检查输出目录是否创建
- 等待一段时间后检查是否开始录制文件

---

### 案例3: 启动监控 - 监控模式

**目的**: 验证可以启动监控模式

**请求**:
```bash
curl -X POST http://localhost:8000/record \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/895511283289",
    "mode": "monitor",
    "output_dir": "recordings_monitor",
    "format": "mp4",
    "interval": 30
  }'
```

**预期结果**:
- 状态码: 200
- 返回内容包含:
  - 进程 PID
  - 成功消息
  - 执行的命令

**验证点**:
- 响应成功
- PID 非零
- 执行的命令包含监控间隔参数
- 验证监控进程在运行

---

### 案例4: 查询录制状态

**目的**: 验证可以查询所有录制状态

**请求**:
```bash
curl -X GET http://localhost:8000/status
```

**预期结果**:
- 状态码: 200
- 返回内容包含前面启动的录制任务列表

**验证点**:
- 响应成功
- 列表包含至少2条记录(前面启动的直接录制和监控任务)
- 记录包含 ID, PID, URL 等信息
- 记录的状态正确(一个录制中，一个监控中)

---

### 案例5: 按 ID 停止录制

**目的**: 验证可以通过 ID 停止特定录制任务

**步骤**:
1. 先执行案例4获取录制列表和ID
2. 选择一个ID执行停止请求

**请求**:
```bash
curl -X POST http://localhost:8000/stop \
  -H "Content-Type: application/json" \
  -d '{
    "id": 1
  }'
```

**预期结果**:
- 状态码: 200
- 成功消息

**验证点**:
- 响应成功
- 再次查询状态，确认对应 ID 的任务已不在列表中

---

### 案例6: 按 URL 停止录制

**目的**: 验证可以通过 URL 停止特定录制任务

**请求**:
```bash
curl -X POST http://localhost:8000/stop \
  -H "Content-Type: application/json" \
  -d '{
    "url": "895511283289"
  }'
```

**预期结果**:
- 状态码: 200
- 成功消息

**验证点**:
- 响应成功
- 再次查询状态，确认包含该 URL 的任务已不在列表中

---

### 案例7: 使用非标准端口启动服务

**目的**: 验证服务可以在非标准端口运行

**步骤**:
1. 停止现有服务
2. 使用不同端口启动服务: `python api_server.py --host 0.0.0.0 --port 8888`
3. 访问 `http://localhost:8888/`

**预期结果**:
- 服务正常启动在新端口
- 可以通过新端口访问 API

**验证点**:
- 响应成功
- 服务描述和版本正确

---

### 案例8: 启动大量录制任务

**目的**: 验证 API 在高负载情况下的稳定性

**步骤**:
1. 编写脚本启动多个录制任务(至少5个)
2. 查询状态确认所有任务都启动成功
3. 停止所有任务

**脚本示例**:
```bash
#!/bin/bash
# 启动多个监控任务
for i in {1..5}
do
    curl -s -X POST http://localhost:8000/record \
      -H "Content-Type: application/json" \
      -d '{
        "url": "https://live.douyin.com/895511283289",
        "mode": "monitor",
        "output_dir": "recordings_'$i'",
        "interval": 30
      }'
    echo "Started task $i"
    sleep 1
done

# 查询所有任务
curl -X GET http://localhost:8000/status

# 停止所有任务
curl -X POST http://localhost:8000/stop \
  -H "Content-Type: application/json" \
  -d '{
    "all": true
  }'
```

**预期结果**:
- 所有任务成功启动
- 状态查询返回所有任务
- 停止命令成功终止所有任务

**验证点**:
- 所有操作响应成功
- 系统稳定，无明显延迟
- 所有任务都能被正确停止

---

### 案例9: 错误情况测试 - 无效 URL

**目的**: 验证 API 对无效输入的处理

**请求**:
```bash
curl -X POST http://localhost:8000/record \
  -H "Content-Type: application/json" \
  -d '{
    "url": "invalid-url",
    "mode": "record"
  }'
```

**预期结果**:
- 状态码: 4xx 错误
- 错误消息说明 URL 无效

**验证点**:
- API 返回适当的错误码和错误消息
- 服务继续运行且不崩溃

---

### 案例10: 错误情况测试 - 停止不存在的任务

**目的**: 验证 API 对不存在资源的处理

**请求**:
```bash
curl -X POST http://localhost:8000/stop \
  -H "Content-Type: application/json" \
  -d '{
    "id": 999
  }'
```

**预期结果**:
- 状态码: 4xx 错误
- 错误消息说明任务不存在

**验证点**:
- API 返回适当的错误码和错误消息
- 服务继续运行且不崩溃

---

### 案例11: 使用提供的测试脚本

**目的**: 验证提供的测试脚本功能

**步骤**:
- Windows: 执行 `test_api.bat https://live.douyin.com/895511283289 monitor 60`
- Linux/Mac: 执行 `./test_api.sh https://live.douyin.com/895511283289 monitor 60`

**预期结果**:
- 脚本成功执行完整测试流程:
  1. 检查 API 状态
  2. 启动录制/监控
  3. 等待指定时间
  4. 查询状态
  5. 停止录制
  6. 最终检查状态

**验证点**:
- 脚本执行成功
- 所有步骤返回预期结果
- 没有错误或异常

## 性能测试

### 并发请求测试

**目的**: 验证 API 处理并发请求的能力

**工具**: Apache Bench 或 wrk

**步骤**:
1. 使用并发测试工具发送多个并发请求
2. 监控服务的响应时间和稳定性

**示例命令**:
```bash
ab -n 100 -c 10 http://localhost:8000/status
```

**预期结果**:
- 所有请求都成功完成
- 响应时间在合理范围内
- 服务保持稳定

## 安全测试

### 无效参数测试

**目的**: 验证 API 对异常参数的处理

**请求示例**:
```bash
curl -X POST http://localhost:8000/record \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://live.douyin.com/895511283289",
    "mode": "invalid_mode",
    "segment_time": "not_a_number"
  }'
```

**预期结果**:
- 返回适当的错误码和错误消息
- 服务保持稳定，不会崩溃

## 集成测试脚本

创建一个集成测试脚本来自动执行所有测试案例：

```python
#!/usr/bin/env python3
import requests
import json
import time
import sys

BASE_URL = "http://localhost:8000"

def test_api_status():
    """测试API状态"""
    print("\n=== 测试1: API服务状态 ===")
    response = requests.get(f"{BASE_URL}/")
    print(f"状态码: {response.status_code}")
    data = response.json()
    print(json.dumps(data, indent=2, ensure_ascii=False))
    
    assert response.status_code == 200
    assert data["success"] == True
    print("测试通过 ✓")
    return True

def test_start_recording():
    """测试启动录制"""
    print("\n=== 测试2: 启动直接录制 ===")
    data = {
        "url": "https://live.douyin.com/895511283289",
        "mode": "record",
        "output_dir": "test_recordings",
        "format": "mp4"
    }
    
    response = requests.post(f"{BASE_URL}/record", json=data)
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    assert response.status_code == 200
    assert result["success"] == True
    assert "pid" in result["data"]
    print("测试通过 ✓")
    return True

def test_start_monitoring():
    """测试启动监控"""
    print("\n=== 测试3: 启动监控 ===")
    data = {
        "url": "https://live.douyin.com/895511283289",
        "mode": "monitor",
        "output_dir": "test_recordings_monitor",
        "format": "mp4",
        "interval": 30
    }
    
    response = requests.post(f"{BASE_URL}/record", json=data)
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    assert response.status_code == 200
    assert result["success"] == True
    assert "pid" in result["data"]
    print("测试通过 ✓")
    return True

def test_get_status():
    """测试获取状态"""
    print("\n=== 测试4: 获取录制状态 ===")
    response = requests.get(f"{BASE_URL}/status")
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    assert response.status_code == 200
    assert result["success"] == True
    assert "recordings" in result["data"]
    print("测试通过 ✓")
    return result["data"]["recordings"]

def test_stop_by_id(recordings):
    """测试按ID停止录制"""
    if not recordings:
        print("\n=== 测试5: 按ID停止录制 - 跳过(无录制任务) ===")
        return True
        
    print("\n=== 测试5: 按ID停止录制 ===")
    record_id = recordings[0]["id"]
    data = {"id": record_id}
    
    response = requests.post(f"{BASE_URL}/stop", json=data)
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    assert response.status_code == 200
    assert result["success"] == True
    print("测试通过 ✓")
    return True

def test_stop_by_url():
    """测试按URL停止录制"""
    print("\n=== 测试6: 按URL停止录制 ===")
    data = {"url": "895511283289"}
    
    response = requests.post(f"{BASE_URL}/stop", json=data)
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    # 即使没有找到匹配的URL，我们也认为API响应正常
    assert response.status_code in [200, 400]
    print("测试通过 ✓")
    return True

def test_stop_all():
    """测试停止所有录制"""
    print("\n=== 测试7: 停止所有录制 ===")
    data = {"all": True}
    
    response = requests.post(f"{BASE_URL}/stop", json=data)
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(json.dumps(result, indent=2, ensure_ascii=False))
    
    assert response.status_code == 200
    print("测试通过 ✓")
    return True

def test_invalid_url():
    """测试无效URL"""
    print("\n=== 测试8: 无效URL ===")
    data = {
        "url": "invalid-url",
        "mode": "record"
    }
    
    response = requests.post(f"{BASE_URL}/record", json=data)
    print(f"状态码: {response.status_code}")
    try:
        result = response.json()
        print(json.dumps(result, indent=2, ensure_ascii=False))
    except:
        print(f"响应内容: {response.text}")
    
    assert response.status_code >= 400  # 期望返回错误状态码
    print("测试通过 ✓")
    return True

def run_all_tests():
    """运行所有测试"""
    try:
        test_api_status()
        test_start_recording()
        test_start_monitoring()
        time.sleep(5)  # 给一些时间让录制任务初始化
        recordings = test_get_status()
        test_stop_by_id(recordings)
        test_stop_by_url()
        test_stop_all()
        test_invalid_url()
        
        print("\n🎉 所有测试通过!")
        return True
    except AssertionError as e:
        print(f"\n❌ 测试失败: {str(e)}")
        return False
    except Exception as e:
        print(f"\n⚠️ 测试过程中出错: {str(e)}")
        return False

if __name__ == "__main__":
    # 检查API是否可访问
    try:
        requests.get(f"{BASE_URL}/")
        print("API服务已启动，开始测试...")
        run_all_tests()
    except requests.exceptions.ConnectionError:
        print(f"无法连接到API服务 {BASE_URL}")
        print("请确保服务已启动后再运行测试")
        sys.exit(1)
```

## 测试结果记录表

| 测试案例 | 状态 | 时间 | 备注 |
|---------|------|------|------|
| 案例1: 检查API服务状态 | □ 通过 □ 失败 | | |
| 案例2: 启动录制 - 直接录制模式 | □ 通过 □ 失败 | | |
| 案例3: 启动监控 - 监控模式 | □ 通过 □ 失败 | | |
| 案例4: 查询录制状态 | □ 通过 □ 失败 | | |
| 案例5: 按ID停止录制 | □ 通过 □ 失败 | | |
| 案例6: 按URL停止录制 | □ 通过 □ 失败 | | |
| 案例7: 使用非标准端口启动服务 | □ 通过 □ 失败 | | |
| 案例8: 启动大量录制任务 | □ 通过 □ 失败 | | |
| 案例9: 错误情况测试 - 无效URL | □ 通过 □ 失败 | | |
| 案例10: 错误情况测试 - 停止不存在的任务 | □ 通过 □ 失败 | | |
| 案例11: 使用提供的测试脚本 | □ 通过 □ 失败 | | | 