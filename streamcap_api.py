import asyncio
import os
import time
from datetime import datetime
import subprocess
import streamget
from typing import Optional

# 定义StreamData类，用于存储直播流信息
class StreamData:
    def __init__(self):
        self.platform = "抖音直播"
        self.platform_key = "douyin"
        self.title = ""
        self.anchor_name = ""
        self.record_url = ""
        self.is_live = False

# 直播流录制类
class StreamCapAPI:
    def __init__(self, live_url: str, output_dir: str = "downloads"):
        self.live_url = live_url
        self.output_dir = output_dir
        self.proxy = None
        self.cookies = None
        self.record_quality = "原画"  # 默认使用原画质量
        self.save_format = "mp4"
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 初始化直播流对象
        self.live_stream = streamget.DouyinLiveStream(proxy_addr=self.proxy, cookies=self.cookies)
    
    def _clean_filename(self, filename: str) -> str:
        """清理文件名，移除不允许的字符"""
        # 移除特殊字符
        for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
            filename = filename.replace(char, '')
        return filename
    
    def _get_filename(self, stream_info: StreamData) -> str:
        """生成录制文件名"""
        # 清理主播名和标题
        stream_info.title = self._clean_filename(stream_info.title)
        stream_info.anchor_name = self._clean_filename(stream_info.anchor_name)
        
        # 添加时间戳
        now = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
        
        # 组合文件名
        components = []
        if stream_info.anchor_name:
            components.append(stream_info.anchor_name)
        if stream_info.title:
            truncated_title = stream_info.title[:30]  # 限制标题长度
            components.append(truncated_title)
        components.append(now)
        
        filename = "_".join(components)
        return filename.replace(" ", "_")
    
    def _get_save_path(self, filename: str) -> str:
        """获取保存路径"""
        save_file_path = os.path.join(self.output_dir, filename + "." + self.save_format)
        return save_file_path.replace("\\", "/")
    
    async def fetch_stream(self) -> Optional[StreamData]:
        """获取直播流信息"""
        try:
            print(f"正在获取直播流信息: {self.live_url}")
            
            if "v.douyin.com" in self.live_url:
                json_data = await self.live_stream.fetch_app_stream_data(url=self.live_url)
            else:
                json_data = await self.live_stream.fetch_web_stream_data(url=self.live_url)
                
            stream_info = await self.live_stream.fetch_stream_url(json_data, self.record_quality)
            
            if stream_info and stream_info.is_live:
                print(f"主播: {stream_info.anchor_name}, 标题: {stream_info.title}")
                print(f"直播状态: {'在线' if stream_info.is_live else '离线'}")
                return stream_info
            else:
                print("直播未开始或获取流信息失败")
                return None
                
        except Exception as e:
            print(f"获取直播流信息失败: {str(e)}")
            return None
    
    async def start_recording(self, stream_info: StreamData):
        """开始录制直播"""
        try:
            # 生成文件名和保存路径
            filename = self._get_filename(stream_info)
            save_path = self._get_save_path(filename)
            print(f"录制文件将保存至: {save_path}")
            
            # 构建ffmpeg命令
            ffmpeg_command = [
                "ffmpeg",
                "-y",
                "-i", stream_info.record_url,
                "-c", "copy",
                "-bsf:a", "aac_adtstoasc",
                save_path
            ]
            
            print("开始录制直播...")
            print(f"录制URL: {stream_info.record_url}")
            
            # 启动ffmpeg进程
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # 等待进程完成
            print("录制进行中，按Ctrl+C停止...")
            try:
                await process.wait()
                print("录制已完成")
            except asyncio.CancelledError:
                # 手动终止进程
                if process.stdin:
                    process.stdin.write(b"q")
                    await process.stdin.drain()
                process.terminate()
                await process.wait()
                print("录制已手动停止")
            
            return save_path
            
        except Exception as e:
            print(f"录制过程中发生错误: {str(e)}")
            return None

async def main():
    # 抖音直播地址
    live_url = "https://live.douyin.com/47815359446"
    
    # 输出目录
    output_dir = os.path.join(os.getcwd(), "downloads")
    
    # 创建StreamCapAPI对象
    stream_cap = StreamCapAPI(live_url, output_dir)
    
    # 获取直播流信息
    stream_info = await stream_cap.fetch_stream()
    
    if stream_info and stream_info.is_live:
        # 开始录制
        await stream_cap.start_recording(stream_info)
    else:
        print("直播未开始或获取直播流失败，无法录制")

if __name__ == "__main__":
    asyncio.run(main()) 