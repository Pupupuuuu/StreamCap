import os
import sys
import json
import asyncio
import subprocess
from typing import Dict, List, Optional, Union
from pydantic import BaseModel, HttpUrl, Field
import uvicorn
from fastapi import FastAPI, HTTPException, BackgroundTasks, Query, Body, status
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import glob

# 创建FastAPI应用
app = FastAPI(
    title="StreamCap API",
    description="直播流录制服务API",
    version="1.0.0"
)

# 添加CORS中间件，允许所有来源访问API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 数据模型
class RecordRequest(BaseModel):
    url: HttpUrl = Field(..., description="直播URL")
    mode: str = Field("monitor", description="运行模式: record(直接录制) 或 monitor(监控直播并自动录制)")
    output_dir: Optional[str] = Field("downloads", description="输出目录路径")
    format: Optional[str] = Field("mp4", description="录制格式: mp4, flv, ts")
    quality: Optional[str] = Field("原画", description="录制画质: 原画, 高清, 标清, 流畅")
    segment: Optional[bool] = Field(True, description="是否启用分段录制")
    segment_time: Optional[int] = Field(1800, description="分段时长(秒)")
    proxy: Optional[str] = Field(None, description="代理地址, 例如: http://127.0.0.1:7890")
    cookies_file: Optional[str] = Field(None, description="Cookies文件路径(JSON格式)")
    force_https: Optional[bool] = Field(False, description="强制使用HTTPS录制")
    include_title: Optional[bool] = Field(True, description="文件名是否包含直播标题")
    platform_folder: Optional[bool] = Field(True, description="是否按平台创建文件夹")
    author_folder: Optional[bool] = Field(True, description="是否按主播创建文件夹")
    time_folder: Optional[bool] = Field(True, description="是否按日期创建文件夹")
    title_folder: Optional[bool] = Field(False, description="是否按标题创建文件夹")
    interval: Optional[int] = Field(60, description="检查直播状态的间隔时间(秒)")
    script: Optional[str] = Field(None, description="录制完成后运行的自定义脚本")

class StopRequest(BaseModel):
    id: Optional[int] = Field(None, description="录制ID")
    url: Optional[str] = Field(None, description="直播URL (部分匹配)")
    all: Optional[bool] = Field(False, description="是否停止所有录制")

class RecordStatusResponse(BaseModel):
    id: int
    pid: int
    is_recording: bool
    is_monitoring: bool
    url: str
    timestamp: float

class RecordListResponse(BaseModel):
    recordings: List[RecordStatusResponse] = []

class ApiResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Union[Dict, List, RecordListResponse]] = None

# 运行状态跟踪
running_processes = {}

# 帮助函数
def build_start_command(record_request: RecordRequest) -> List[str]:
    """构建start.py的命令行参数"""
    cmd = [sys.executable, "start.py", str(record_request.url)]
    
    # 添加参数
    if record_request.mode:
        cmd.extend(["-m", record_request.mode])
    
    if record_request.output_dir:
        cmd.extend(["-o", record_request.output_dir])
        
    if record_request.format:
        cmd.extend(["-f", record_request.format])
        
    if record_request.quality:
        cmd.extend(["-q", record_request.quality])
    
    # 布尔参数
    if record_request.segment is False:
        cmd.append("--no-segment")
        
    if record_request.segment_time:
        cmd.extend(["--segment-time", str(record_request.segment_time)])
        
    if record_request.proxy:
        cmd.extend(["-p", record_request.proxy])
        
    if record_request.cookies_file:
        cmd.extend(["-c", record_request.cookies_file])
        
    if record_request.force_https:
        cmd.append("--force-https")
        
    # 文件夹和文件名设置
    if record_request.include_title is False:
        cmd.append("--no-include-title")
        
    if record_request.platform_folder is False:
        cmd.append("--no-platform-folder")
        
    if record_request.author_folder is False:
        cmd.append("--no-author-folder")
        
    if record_request.time_folder is False:
        cmd.append("--no-time-folder")
        
    if record_request.title_folder:
        cmd.append("--title-folder")
        
    if record_request.interval:
        cmd.extend(["-i", str(record_request.interval)])
        
    if record_request.script:
        cmd.extend(["--script", record_request.script])
    
    return cmd

def list_running_recordings() -> List[dict]:
    """列出所有正在运行的录制进程"""
    # 查找所有的状态文件
    temp_dir = tempfile.gettempdir()
    status_file_pattern = os.path.join(temp_dir, "streamcap_*.status")
    status_files = glob.glob(status_file_pattern)
    
    recordings = []
    for idx, status_file in enumerate(status_files, 1):
        try:
            with open(status_file, 'r') as f:
                status_data = json.load(f)
            
            pid = status_data.get('pid')
            is_recording = status_data.get('is_recording', False)
            is_monitoring = status_data.get('is_monitoring', False)
            monitor_url = status_data.get('monitor_url', 'Unknown')
            timestamp = status_data.get('timestamp', 0)
            
            # 只展示正在录制或监控的进程
            if is_recording or is_monitoring:
                recording_info = {
                    'id': idx,
                    'pid': pid,
                    'file_path': status_file,
                    'is_recording': is_recording,
                    'is_monitoring': is_monitoring,
                    'url': monitor_url,
                    'timestamp': timestamp
                }
                recordings.append(recording_info)
        except Exception as e:
            print(f"读取状态文件 {status_file} 时出错: {str(e)}")
    
    return recordings

def send_stop_request(recordings, record_id=None, url=None, stop_all=False):
    """发送停止请求"""
    success = False
    
    if not recordings:
        return False, "没有找到正在运行的录制进程"
    
    if record_id:
        # 检查ID是否有效
        if record_id < 1 or record_id > len(recordings):
            return False, f"无效的录制ID: {record_id}，有效范围: 1-{len(recordings)}"
        
        # 获取对应的录制信息
        recording = recordings[record_id - 1]
        status_file = recording['file_path']
        
        try:
            # 读取状态
            with open(status_file, 'r') as f:
                status_data = json.load(f)
            
            # 设置停止标志
            status_data['stop_requested'] = True
            
            # 写回状态文件
            with open(status_file, 'w') as f:
                json.dump(status_data, f)
            
            return True, f"已发送停止信号到进程 {recording['pid']}, URL: {recording['url']}"
        except Exception as e:
            return False, f"停止录制时出错: {str(e)}"
    
    elif url:
        # 查找匹配URL的录制
        matching_recordings = [r for r in recordings if url in r['url']]
        
        if not matching_recordings:
            return False, f"没有找到URL包含 '{url}' 的录制进程"
        
        success_messages = []
        for recording in matching_recordings:
            status_file = recording['file_path']
            
            try:
                # 读取状态
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                
                # 设置停止标志
                status_data['stop_requested'] = True
                
                # 写回状态文件
                with open(status_file, 'w') as f:
                    json.dump(status_data, f)
                
                success_messages.append(f"已发送停止信号到进程 {recording['pid']}, URL: {recording['url']}")
                success = True
            except Exception as e:
                success_messages.append(f"停止录制时出错: {str(e)}")
        
        return success, "; ".join(success_messages)
    
    elif stop_all:
        success_messages = []
        for recording in recordings:
            status_file = recording['file_path']
            
            try:
                # 读取状态
                with open(status_file, 'r') as f:
                    status_data = json.load(f)
                
                # 设置停止标志
                status_data['stop_requested'] = True
                
                # 写回状态文件
                with open(status_file, 'w') as f:
                    json.dump(status_data, f)
                
                success_messages.append(f"已发送停止信号到进程 {recording['pid']}, URL: {recording['url']}")
                success = True
            except Exception as e:
                success_messages.append(f"停止录制时出错: {str(e)}")
        
        return success, "; ".join(success_messages)
    
    return False, "必须指定id、url或all参数之一"

async def start_recording_task(cmd: List[str]):
    """在后台启动录制任务"""
    try:
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            stdin=asyncio.subprocess.PIPE
        )
        
        # 记录进程
        running_processes[process.pid] = {
            "cmd": cmd,
            "process": process,
            "start_time": asyncio.get_event_loop().time()
        }
        
        # 不等待进程完成，让它在后台运行
        return process.pid
    except Exception as e:
        raise Exception(f"启动录制进程失败: {str(e)}")

# API端点
@app.get("/", response_model=ApiResponse)
async def root():
    """API根端点，返回基本信息"""
    return {
        "success": True,
        "message": "StreamCap API 服务正在运行",
        "data": {
            "version": app.version,
            "description": app.description
        }
    }

@app.post("/record", response_model=ApiResponse)
async def start_record(record_request: RecordRequest, background_tasks: BackgroundTasks):
    """开始录制或监控直播"""
    try:
        cmd = build_start_command(record_request)
        
        # 异步启动录制进程
        process_pid = await start_recording_task(cmd)
        
        return {
            "success": True,
            "message": f"已成功启动{'录制' if record_request.mode == 'record' else '监控'}: {record_request.url}",
            "data": {
                "pid": process_pid,
                "command": " ".join(cmd)
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"启动录制失败: {str(e)}"
        )

@app.get("/status", response_model=ApiResponse)
async def get_status():
    """获取所有录制状态"""
    try:
        recordings = list_running_recordings()
        
        result = RecordListResponse(recordings=[
            RecordStatusResponse(
                id=r['id'],
                pid=r['pid'],
                is_recording=r['is_recording'],
                is_monitoring=r['is_monitoring'],
                url=r['url'],
                timestamp=r['timestamp']
            )
            for r in recordings
        ])
        
        return {
            "success": True,
            "message": f"找到 {len(recordings)} 个正在运行的录制进程",
            "data": result
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取状态失败: {str(e)}"
        )

@app.post("/stop", response_model=ApiResponse)
async def stop_record(stop_request: StopRequest):
    """停止录制或监控"""
    try:
        recordings = list_running_recordings()
        
        success, message = send_stop_request(
            recordings, 
            record_id=stop_request.id, 
            url=stop_request.url, 
            stop_all=stop_request.all
        )
        
        if success:
            return {
                "success": True,
                "message": message
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=message
            )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"停止录制失败: {str(e)}"
        )

# 启动服务器
if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="StreamCap API 服务")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="服务器主机地址")
    parser.add_argument("--port", type=int, default=8000, help="服务器端口")
    parser.add_argument("--reload", action="store_true", help="是否启用热重载")
    
    args = parser.parse_args()
    
    print(f"启动 StreamCap API 服务 - http://{args.host}:{args.port}")
    uvicorn.run(
        "api_server:app", 
        host=args.host, 
        port=args.port, 
        reload=args.reload
    ) 