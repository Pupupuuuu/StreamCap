import asyncio
import os
import time
import json
from datetime import datetime
import sys
import streamget
from typing import Optional, Dict, Any, List, Union
import re

# 全局变量，用于控制程序退出
exit_requested = False

# 视频质量枚举
class VideoQuality:
    OD = "原画"
    HD = "高清"
    SD = "标清"
    LD = "流畅"

# FFmpeg命令构建器基类
class FFmpegCommandBuilder:
    DEFAULT_CONFIG = {
        "rw_timeout": "15000000",
        "analyzeduration": "20000000",
        "probesize": "10000000",
        "bufsize": "8000k",
        "max_muxing_queue_size": "1024",
    }

    OVERSEAS_CONFIG = {
        "rw_timeout": "50000000",
        "analyzeduration": "40000000",
        "probesize": "20000000",
        "bufsize": "15000k",
        "max_muxing_queue_size": "2048",
    }

    FFMPEG_USER_AGENT = (
        "Mozilla/5.0 (Linux; Android 11; SAMSUNG SM-G973U) AppleWebKit/537.36 (KHTML, like Gecko) "
        "SamsungBrowser/14.2 Chrome/87.0.4280.141 Mobile Safari/537.36"
    )

    def __init__(
        self,
        record_url: str,
        is_overseas: bool = False,
        segment_record: bool = False,
        segment_time: str = None,
        full_path: str = None,
        headers: str = None,
        proxy: str = None,
    ):
        self.record_url = record_url
        self.is_overseas = is_overseas
        self.segment_record = segment_record
        self.segment_time = segment_time
        self.full_path = full_path or ""
        self.proxy = proxy or ""
        self.headers = headers or ""

    def _get_basic_ffmpeg_command(self) -> List[str]:
        """
        构建基本的FFmpeg命令。与原项目保持完全一致
        """
        config = self.OVERSEAS_CONFIG if self.is_overseas else self.DEFAULT_CONFIG
        command = [
            "ffmpeg",
            "-y",
            "-v", "verbose",
            "-rw_timeout", config["rw_timeout"],
            "-loglevel", "error",
            "-hide_banner",
            "-user_agent", self.FFMPEG_USER_AGENT,
            "-protocol_whitelist", "rtmp,crypto,file,http,https,tcp,tls,udp,rtp,httpproxy",
            "-thread_queue_size", "1024",
            "-analyzeduration", config["analyzeduration"],
            "-probesize", config["probesize"],
            "-fflags", "+discardcorrupt",
            "-re",
            "-i", self.record_url,
            "-bufsize", config["bufsize"],
            "-sn",
            "-dn",
            "-reconnect_delay_max", "60",
            "-reconnect_streamed",
            "-reconnect_at_eof",
            "-max_muxing_queue_size", config["max_muxing_queue_size"],
            "-correct_ts_overflow", "1",
            "-avoid_negative_ts", "1",
        ]

        if self.headers:
            command.insert(11, "-headers")
            command.insert(12, self.headers)

        if self.proxy:
            command.insert(1, "-http_proxy")
            command.insert(2, self.proxy)

        return command

# MP4命令构建器
class MP4CommandBuilder(FFmpegCommandBuilder):
    def build_command(self) -> List[str]:
        command = self._get_basic_ffmpeg_command()
        if self.segment_record:
            additional_commands = [
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0",
                "-f", "segment",
                "-segment_time", str(self.segment_time),
                "-segment_format", "mp4",
                "-reset_timestamps", "1",
                "-movflags", "+frag_keyframe+empty_moov",
                "-flags", "global_header",
                self.full_path,
            ]
        else:
            additional_commands = [
                "-map", "0",
                "-c:v", "copy",
                "-c:a", "copy",
                "-f", "mp4",
                self.full_path,
            ]

        command.extend(additional_commands)
        return command

# FLV命令构建器
class FLVCommandBuilder(FFmpegCommandBuilder):
    def build_command(self) -> List[str]:
        command = self._get_basic_ffmpeg_command()
        additional_commands = [
            "-map", "0",
            "-c:v", "copy",
            "-c:a", "copy",
            "-bsf:a", "aac_adtstoasc",
            "-flvflags", "no_duration_filesize",
            "-f", "flv",
            self.full_path,
        ]
        command.extend(additional_commands)
        return command

# TS命令构建器
class TSCommandBuilder(FFmpegCommandBuilder):
    def build_command(self) -> List[str]:
        command = self._get_basic_ffmpeg_command()
        if self.segment_record:
            additional_commands = [
                "-c:v", "copy",
                "-c:a", "copy",
                "-map", "0",
                "-f", "segment",
                "-segment_time", str(self.segment_time),
                "-segment_format", "mpegts",
                "-mpegts_flags", "+resend_headers",
                "-reset_timestamps", "1",
                self.full_path,
            ]
        else:
            additional_commands = [
                "-map", "0",
                "-c:v", "copy",
                "-c:a", "copy",
                "-f", "mpegts",
                "-mpegts_flags", "+resend_headers",
                self.full_path,
            ]

        command.extend(additional_commands)
        return command

# 创建命令构建器
def create_builder(format_type: str, **kwargs) -> FFmpegCommandBuilder:
    format_to_class = {
        "mp4": MP4CommandBuilder,
        "flv": FLVCommandBuilder,
        "ts": TSCommandBuilder,
    }
    builder_class = format_to_class.get(format_type.lower())
    if not builder_class:
        raise ValueError(f"不支持的格式: {format_type}")
    return builder_class(**kwargs)

# 直播流录制类
class StreamCapAPI:
    def __init__(
        self, 
        output_dir: str = "downloads",
        proxy: str = None,
        cookies: Dict[str, str] = None,
        record_quality: str = VideoQuality.OD,
        save_format: str = "mp4",
        segment_record: bool = False,
        segment_time: int = 1800,
        filename_includes_title: bool = True,
        folder_name_platform: bool = True,
        folder_name_author: bool = True,
        folder_name_time: bool = True,
        folder_name_title: bool = False,
        force_https_recording: bool = False,
        custom_script_command: str = None
    ):
        self.output_dir = output_dir
        self.proxy = proxy
        self.cookies = cookies
        self.record_quality = record_quality
        self.save_format = save_format.lower() if save_format else "mp4"
        self.segment_record = segment_record
        self.segment_time = str(segment_time) if segment_time else "1800"
        
        # 文件名和文件夹配置
        self.filename_includes_title = filename_includes_title
        self.folder_name_platform = folder_name_platform
        self.folder_name_author = folder_name_author
        self.folder_name_time = folder_name_time
        self.folder_name_title = folder_name_title
        self.force_https_recording = force_https_recording
        self.custom_script_command = custom_script_command
        
        # 录制状态
        self.is_recording = False
        self.ffmpeg_process = None
        self.recording_dir = None
        
        # 监控状态
        self.is_monitoring = False
        self.monitor_task = None
        self.monitor_interval = 60  # 默认监控间隔为60秒
        self.monitor_url = None
        
        # 状态文件
        self.status_file_path = None
        self.status_check_task = None
        self._setup_status_file()
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
    
    def _setup_status_file(self):
        """创建状态文件，用于进程间通信"""
        import tempfile
        import os
        import json
        
        # 创建临时状态文件
        temp_dir = tempfile.gettempdir()
        import uuid
        unique_id = str(uuid.uuid4())[:8]
        self.status_file_path = os.path.join(temp_dir, f"streamcap_{unique_id}.status")
        
        # 写入初始状态
        self._update_status_file()
        
        # 我们不能在__init__中创建异步任务，因为此时没有运行的事件循环
        # 这个任务将在start_recording和start_monitoring方法中启动
        self.status_check_task = None
    
    def _update_status_file(self):
        """更新状态文件信息"""
        if not self.status_file_path:
            return
            
        import json
        import os
        
        # 准备状态数据
        status_data = {
            'pid': os.getpid(),
            'is_recording': self.is_recording,
            'is_monitoring': self.is_monitoring,
            'monitor_url': self.monitor_url,
            'stop_requested': False,
            'timestamp': time.time()
        }
        
        # 写入状态文件
        try:
            with open(self.status_file_path, 'w') as f:
                json.dump(status_data, f)
        except Exception as e:
            print(f"更新状态文件时出错: {str(e)}")
    
    async def _check_status_file(self):
        """检查状态文件中的停止请求"""
        import json
        import asyncio
        
        while True:
            try:
                # 如果文件不存在，可能已经被删除
                if not os.path.exists(self.status_file_path):
                    self._update_status_file()
                
                # 读取状态文件
                with open(self.status_file_path, 'r') as f:
                    status_data = json.load(f)
                
                # 检查是否有停止请求
                if status_data.get('stop_requested', False):
                    print("接收到外部停止请求")
                    
                    # 停止录制
                    if self.is_recording:
                        await self.stop_recording()
                        
                    # 停止监控
                    if self.is_monitoring:
                        await self.stop_monitoring()
                    
                    # 清除状态文件
                    try:
                        if os.path.exists(self.status_file_path):
                            os.remove(self.status_file_path)
                            print("已删除状态文件")
                    except Exception as e:
                        print(f"删除状态文件时出错: {str(e)}")
                    
                    # 退出程序
                    print("准备退出程序...")
                    # 使用非零退出码以便可以区分正常退出和被外部请求终止
                    # 我们不能在这里直接调用sys.exit()，因为这是在异步上下文中
                    # 而是设置一个标志，让主循环检测到后退出
                    global exit_requested
                    exit_requested = True
                    return  # 终止状态检查循环
                    
            except Exception as e:
                # 忽略错误，确保循环不会中断
                pass
            
            # 更新状态文件
            self._update_status_file()
            
            # 每秒检查一次
            await asyncio.sleep(1)
    
    def clean_name(self, name: str, default: str = None) -> str:
        """清理名称，移除不允许的字符"""
        if name and name.strip():
            rstr = r"[\/\\\:\*\？?\"\<\>\|&#.。,， ~！· ]"
            cleaned_name = name.strip().replace("（", "(").replace("）", ")")
            cleaned_name = re.sub(rstr, "_", cleaned_name)
            # 如果需要，去除emoji
            cleaned_name = cleaned_name.replace("__", "_").strip("_")
            return cleaned_name or default
        return default or ""
    
    def _clean_and_truncate_title(self, title: str) -> str:
        """清理并截断标题"""
        if not title:
            return None
        cleaned_title = title[:30].replace("，", ",").replace(" ", "")
        return cleaned_title
    
    def _get_filename(self, stream_info) -> str:
        """生成录制文件名"""
        live_title = None
        stream_info.title = self.clean_name(stream_info.title, None)
        
        if self.filename_includes_title and stream_info.title:
            stream_info.title = self._clean_and_truncate_title(stream_info.title)
            live_title = stream_info.title
        
        stream_info.anchor_name = self.clean_name(stream_info.anchor_name, "直播间")
        
        now = time.strftime("%Y-%m-%d_%H-%M-%S", time.localtime())
        full_filename = "_".join([i for i in (stream_info.anchor_name, live_title, now) if i])
        return full_filename
    
    def _get_output_dir(self, stream_info) -> str:
        """获取输出目录路径"""
        if self.recording_dir:
            return self.recording_dir
        
        now = datetime.today().strftime("%Y%m%d")
        # 确保使用绝对路径
        if not os.path.isabs(self.output_dir):
            self.output_dir = os.path.abspath(self.output_dir)
            
        output_dir = self.output_dir.rstrip("/").rstrip("\\")
        
        # 清理平台名称
        platform_name = self.clean_name(stream_info.platform, "other")
        
        if self.folder_name_platform:
            output_dir = os.path.join(output_dir, platform_name)
            
        if self.folder_name_author:
            # 使用清理过的主播名称
            anchor_name = self._clean_and_truncate_title(stream_info.anchor_name) or "broadcaster"
            output_dir = os.path.join(output_dir, anchor_name)
            
        if self.folder_name_time:
            output_dir = os.path.join(output_dir, now)
            
        if self.folder_name_title and stream_info.title:
            live_title = self._clean_and_truncate_title(stream_info.title)
            if live_title:
                if self.folder_name_time:
                    output_dir = os.path.join(output_dir, live_title)
                else:
                    output_dir = os.path.join(output_dir, f"{now}_{live_title}")
        
        try:
            # 确保创建目录
            os.makedirs(output_dir, exist_ok=True)
            # 测试写入权限
            test_file = os.path.join(output_dir, "test_write.tmp")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
        except Exception as e:
            print(f"创建或写入目录出错: {str(e)}，将使用默认下载目录")
            # 如果目录不可写，使用系统临时目录
            import tempfile
            output_dir = os.path.join(tempfile.gettempdir(), "streamcap_downloads")
            os.makedirs(output_dir, exist_ok=True)
                
        self.recording_dir = output_dir
        return output_dir
    
    def _get_save_path(self, filename: str) -> str:
        """获取保存路径"""
        suffix = self.save_format
        suffix = "_%03d." + suffix if self.segment_record and self.save_format != "flv" else "." + suffix
        save_file_path = os.path.join(self.output_dir, filename + suffix).replace(" ", "_")
        return save_file_path.replace("\\", "/")
    
    def _get_record_url(self, url: str) -> str:
        """处理录制URL"""
        if self.force_https_recording and url.startswith("http://"):
            url = url.replace("http://", "https://")
            
        return url
    
    def _get_headers_params(self, record_url: str) -> str:
        """获取请求头参数"""
        headers = ""
        if "douyin.com" in record_url or "douyincdn.com" in record_url:
            headers = "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36\r\nreferer: https://live.douyin.com/\r\n"
        elif "tiktok.com" in record_url:
            headers = "user-agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36\r\nreferer: https://www.tiktok.com/\r\n"
        return headers
    
    async def fetch_stream(self, live_url: str):
        """获取直播流信息"""
        try:
            print(f"正在获取直播流信息: {live_url}")
            print(f"使用代理: {self.proxy or '无'}")
            
            # 初始化平台处理器
            platform = "douyin"
            
            # 检测URL中的平台类型
            if "douyin.com" in live_url:
                platform = "douyin"
                live_stream = streamget.DouyinLiveStream(proxy_addr=self.proxy, cookies=self.cookies)
            elif "tiktok.com" in live_url:
                platform = "tiktok"
                live_stream = streamget.TikTokLiveStream(proxy_addr=self.proxy, cookies=self.cookies)
            elif "bilibili.com" in live_url:
                platform = "bilibili"
                live_stream = streamget.BilibiliLiveStream(proxy_addr=self.proxy, cookies=self.cookies)
            else:
                platform = "douyin"  # 默认使用抖音
                live_stream = streamget.DouyinLiveStream(proxy_addr=self.proxy, cookies=self.cookies)
            
            # 获取流信息
            if platform == "douyin":
                if "v.douyin.com" in live_url:
                    json_data = await live_stream.fetch_app_stream_data(url=live_url)
                else:
                    json_data = await live_stream.fetch_web_stream_data(url=live_url)
            elif platform == "tiktok":
                json_data = await live_stream.fetch_web_stream_data(url=live_url)
            elif platform == "bilibili":
                json_data = await live_stream.fetch_web_stream_data(url=live_url)
            else:
                # 默认使用抖音的方法
                if "v.douyin.com" in live_url:
                    json_data = await live_stream.fetch_app_stream_data(url=live_url)
                else:
                    json_data = await live_stream.fetch_web_stream_data(url=live_url)
            
            stream_info = await live_stream.fetch_stream_url(json_data, self.record_quality)
            
            if stream_info and stream_info.is_live:
                print(f"主播: {stream_info.anchor_name}, 标题: {stream_info.title}")
                print(f"直播状态: {'在线' if stream_info.is_live else '离线'}")
                return stream_info
            else:
                print("直播未开始或获取流信息失败")
                return None
                
        except Exception as e:
            print(f"获取直播流信息失败: {str(e)}")
            import traceback
            traceback.print_exc()
            return None
    
    async def start_recording(self, live_url: str) -> str:
        """开始录制直播"""
        save_path = None
        try:
            # 启动状态检查任务
            if self.status_check_task is None or self.status_check_task.done():
                self.status_check_task = asyncio.create_task(self._check_status_file())
            
            # 获取流信息
            stream_info = await self.fetch_stream(live_url)
            
            if not stream_info or not stream_info.is_live:
                print("直播未开始或获取流信息失败，无法录制")
                return None
            
            # 生成文件名和保存路径
            filename = self._get_filename(stream_info)
            self.output_dir = self._get_output_dir(stream_info)
            save_path = self._get_save_path(filename)
            print(f"录制文件将保存至: {save_path}")
            
            # 处理录制URL
            record_url = self._get_record_url(stream_info.record_url)
            
            # 获取请求头
            headers = self._get_headers_params(record_url)
            
            # 构建ffmpeg命令
            ffmpeg_builder = create_builder(
                self.save_format,
                record_url=record_url,
                proxy=self.proxy,
                segment_record=self.segment_record,
                segment_time=self.segment_time,
                full_path=save_path,
                headers=headers
            )
            
            ffmpeg_command = ffmpeg_builder.build_command()
            
            print("开始录制直播...")
            print(f"录制URL: {record_url}")
            print(f"FFmpeg命令: {' '.join(ffmpeg_command)}")
            
            # 启动ffmpeg进程
            self.ffmpeg_process = await asyncio.create_subprocess_exec(
                *ffmpeg_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            self.is_recording = True
            # 更新状态文件
            self._update_status_file()
            
            # 等待进程完成
            print("录制进行中，按Ctrl+C停止...")
            try:
                # 保持进程活动状态，用于手动中断
                await self.ffmpeg_process.wait()
                
                # 检查返回码
                safe_return_codes = [0, 255]  # 正常退出和中断的返回码
                if self.ffmpeg_process.returncode in safe_return_codes:
                    print("录制已成功完成")
                else:
                    print(f"录制异常结束，返回码: {self.ffmpeg_process.returncode}")
                    
                    # 获取错误输出
                    stderr_data = await self.ffmpeg_process.stderr.read()
                    print(f"FFmpeg错误: {stderr_data.decode('utf-8', errors='ignore')}")
                    
            except asyncio.CancelledError:
                # 手动终止进程
                print("接收到停止信号，正在停止录制...")
                await self.stop_recording()
                print("录制已手动停止")
            except Exception as e:
                print(f"录制过程中发生异常: {str(e)}")
                await self.stop_recording()
            finally:
                self.is_recording = False
                # 更新状态文件
                self._update_status_file()
            
            # 如果有自定义脚本，运行它
            if self.custom_script_command:
                await self.run_custom_script(self.custom_script_command, save_path)
            
            # 如果需要转换为MP4且原格式不是MP4，则进行转换
            if self.save_format != "mp4" and self.segment_record:
                # 对于分段录制，处理所有分段文件
                import glob
                segment_pattern = save_path.replace("_%03d", "_*").rsplit(".", 1)[0] + f".{self.save_format}"
                segment_files = glob.glob(segment_pattern)
                print(f"找到 {len(segment_files)} 个分段文件需要转换")
                
                for segment_file in segment_files:
                    await self.converts_mp4(segment_file, delete_original=True)
            elif self.save_format != "mp4":
                # 单个文件的转换
                await self.converts_mp4(save_path, delete_original=True)
            
            return save_path
            
        except Exception as e:
            print(f"录制过程中发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
            self.is_recording = False
            # 更新状态文件
            self._update_status_file()
            
            # 尝试清理未完成的进程
            if self.ffmpeg_process:
                try:
                    self.ffmpeg_process.terminate()
                    await asyncio.wait_for(self.ffmpeg_process.wait(), timeout=5.0)
                except (asyncio.TimeoutError, Exception) as term_err:
                    print(f"终止FFmpeg进程时出错: {str(term_err)}")
                    try:
                        self.ffmpeg_process.kill()
                    except Exception:
                        pass
            
            return save_path  # 即使发生错误也返回路径
    
    async def stop_recording(self):
        """停止录制"""
        if not self.is_recording or not self.ffmpeg_process:
            return False
            
        print("正在停止录制...")
        # 在Windows上用q来优雅地关闭ffmpeg
        if os.name == "nt" and self.ffmpeg_process.stdin:
            try:
                self.ffmpeg_process.stdin.write(b"q")
                await self.ffmpeg_process.stdin.drain()
                print("已发送退出命令")
                # 给一点时间让FFmpeg处理q命令
                try:
                    await asyncio.wait_for(self.ffmpeg_process.wait(), timeout=10.0)  # 延长超时时间
                    print("FFmpeg进程已正常退出")
                    self.is_recording = False
                    self.ffmpeg_process = None
                    # 更新状态文件
                    self._update_status_file()
                    print("录制文件已保存")
                    return True
                except asyncio.TimeoutError:
                    print("FFmpeg进程在接收到q命令后没有及时退出，将强制终止")
            except Exception as e:
                print(f"发送退出命令时出错: {str(e)}")
        
        # 其他平台或当stdin失败时，尝试终止进程
        try:
            print("正在终止FFmpeg进程...")
            self.ffmpeg_process.terminate()
            # 等待进程结束，超时后强制终止
            try:
                await asyncio.wait_for(self.ffmpeg_process.wait(), timeout=10.0)  # 延长超时时间
                print("FFmpeg进程已成功终止")
            except asyncio.TimeoutError:
                print("FFmpeg进程没有及时退出，强制终止")
                self.ffmpeg_process.kill()
                await self.ffmpeg_process.wait()
                print("FFmpeg进程已被强制终止")
        except Exception as e:
            print(f"终止录制过程时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            try:
                self.ffmpeg_process.kill()
                await self.ffmpeg_process.wait()
                print("FFmpeg进程已被强制终止")
            except Exception:
                pass
        
        self.is_recording = False
        self.ffmpeg_process = None
        # 更新状态文件
        self._update_status_file()
        print("录制文件已保存")
        return True
    
    async def run_custom_script(self, script_command: str, save_path: str):
        """运行自定义脚本"""
        try:
            if not script_command:
                return
                
            print(f"执行自定义脚本: {script_command}")
            
            # 替换变量
            script_command = script_command.replace("{file}", save_path)
            script_command = script_command.replace("{dir}", os.path.dirname(save_path))
            
            # 创建进程
            process = await asyncio.create_subprocess_shell(
                script_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # 等待进程完成
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                print("自定义脚本执行成功")
                if stdout:
                    print(f"脚本输出: {stdout.decode('utf-8', errors='ignore')}")
            else:
                print(f"自定义脚本执行失败，返回码: {process.returncode}")
                if stderr:
                    print(f"脚本错误: {stderr.decode('utf-8', errors='ignore')}")
                    
        except Exception as e:
            print(f"执行自定义脚本时出错: {str(e)}")
            
    async def start_monitoring(self, live_url: str, interval: int = 60) -> bool:
        """
        启动监控功能 - API接口1
        
        参数:
            live_url: 直播URL
            interval: 检查间隔(秒)
            
        返回:
            是否成功启动监控
        """
        # 如果已经在监控，直接返回
        if self.is_monitoring:
            print(f"已经在监控直播: {self.monitor_url}")
            return False
            
        # 启动状态检查任务
        if self.status_check_task is None or self.status_check_task.done():
            self.status_check_task = asyncio.create_task(self._check_status_file())
            
        self.monitor_interval = interval
        self.monitor_url = live_url
        self.is_monitoring = True
        
        # 创建监控任务
        self.monitor_task = asyncio.create_task(self._monitor_loop())
        
        # 更新状态文件
        self._update_status_file()
        
        print(f"开始监控直播: {live_url}")
        print(f"监控间隔: {interval}秒")
        return True
        
    async def stop_monitoring(self) -> bool:
        """
        停止监控功能 - API接口2
        
        返回:
            是否成功停止监控
        """
        if not self.is_monitoring:
            print("当前没有正在进行的监控")
            return False
            
        self.is_monitoring = False
        
        # 取消监控任务
        if self.monitor_task and not self.monitor_task.done():
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
                
        self.monitor_task = None
        print(f"已停止监控: {self.monitor_url}")
        self.monitor_url = None
        
        # 更新状态文件
        self._update_status_file()
        
        return True
        
    async def _monitor_loop(self) -> None:
        """监控循环"""
        try:
            while self.is_monitoring:
                # 如果当前正在录制，则跳过检查
                if self.is_recording:
                    await asyncio.sleep(self.monitor_interval)
                    continue
                    
                try:
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    print(f"[{now}] 检查直播状态: {self.monitor_url}")
                    
                    # 获取流信息
                    stream_info = await self.fetch_stream(self.monitor_url)
                    
                    if stream_info and stream_info.is_live:
                        print(f"[{now}] 检测到直播开始！")
                        
                        # 开始录制
                        asyncio.create_task(self.start_recording(self.monitor_url))
                    else:
                        print(f"[{now}] 直播未开始，继续监控...")
                        
                except Exception as e:
                    print(f"监控过程中出错: {str(e)}")
                    import traceback
                    traceback.print_exc()
                    
                # 等待下一次检查
                await asyncio.sleep(self.monitor_interval)
                
        except asyncio.CancelledError:
            print("监控任务已取消")
        except Exception as e:
            print(f"监控循环出错: {str(e)}")
            import traceback
            traceback.print_exc()
            self.is_monitoring = False
    
    async def get_monitoring_status(self) -> dict:
        """获取监控状态"""
        status = {
            "is_monitoring": self.is_monitoring if hasattr(self, 'is_monitoring') else False,
            "is_recording": self.is_recording if hasattr(self, 'is_recording') else False,
            "monitor_url": getattr(self, 'monitor_url', None),
            "monitor_interval": getattr(self, 'monitor_interval', 0)
        }
        return status
    
    async def converts_mp4(self, file_path: str, delete_original: bool = True) -> str:
        """将录制文件转换为MP4格式"""
        if self.save_format == "mp4" and not file_path.endswith(".ts"):
            print("文件已经是MP4格式，无需转换")
            return file_path
            
        try:
            original_path = file_path
            output_path = os.path.splitext(original_path)[0] + ".mp4"
            
            print(f"正在将 {original_path} 转换为 {output_path}")
            
            # 构建ffmpeg命令
            ffmpeg_command = [
                "ffmpeg", "-y",
                "-i", original_path,
                "-c", "copy",
                "-movflags", "+faststart",  # 添加此标志确保MP4文件可以流式播放
                output_path
            ]
            
            # 创建进程
            process = await asyncio.create_subprocess_exec(
                *ffmpeg_command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            # 等待进程完成
            stdout, stderr = await process.communicate()
            
            if process.returncode == 0:
                print(f"转换成功: {output_path}")
                if delete_original and os.path.exists(output_path):
                    try:
                        os.remove(original_path)
                        print(f"已删除原始文件: {original_path}")
                    except Exception as e:
                        print(f"删除原始文件失败: {str(e)}")
                return output_path
            else:
                print(f"转换失败，返回码: {process.returncode}")
                if stderr:
                    error_msg = stderr.decode('utf-8', errors='ignore')
                    print(f"FFmpeg错误: {error_msg[:200]}..." if len(error_msg) > 200 else error_msg)
                return original_path
                
        except Exception as e:
            print(f"转换文件时出错: {str(e)}")
            import traceback
            traceback.print_exc()
            return file_path

    def __del__(self):
        """析构函数，用于清理资源"""
        # 清理状态文件
        if hasattr(self, 'status_file_path') and self.status_file_path and os.path.exists(self.status_file_path):
            try:
                os.remove(self.status_file_path)
            except:
                pass

if __name__ == "__main__":
    import argparse
    
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description="StreamCap - 直播流录制工具")
    
    # 添加参数
    # 必选参数
    parser.add_argument('url', type=str, help='直播URL')
    
    # 运行模式
    parser.add_argument('-m', '--mode', choices=['record', 'monitor'], default='monitor',
                        help='运行模式: record(直接录制) 或 monitor(监控直播并自动录制)')
    
    # 输出设置
    parser.add_argument('-o', '--output-dir', type=str, default='downloads',
                        help='输出目录路径')
    parser.add_argument('-f', '--format', type=str, choices=['mp4', 'flv', 'ts'], default='mp4',
                        help='录制格式')
    parser.add_argument('-q', '--quality', type=str, choices=['原画', '高清', '标清', '流畅'], default='原画',
                        help='录制画质')
    
    # 分段录制设置
    parser.add_argument('--segment', action='store_true', default=True,
                        help='启用分段录制（推荐开启，防止单个文件过大或录制中断导致文件损坏）')
    parser.add_argument('--no-segment', action='store_false', dest='segment',
                        help='禁用分段录制')
    parser.add_argument('--segment-time', type=int, default=1800,
                        help='分段时长(秒), 默认30分钟')
    
    # 代理和网络设置
    parser.add_argument('-p', '--proxy', type=str, help='代理地址, 例如: http://127.0.0.1:7890')
    parser.add_argument('-c', '--cookies', type=str, help='Cookies文件路径(JSON格式)')
    parser.add_argument('--force-https', action='store_true',
                        help='强制使用HTTPS录制')
    
    # 文件夹和文件名设置
    parser.add_argument('--include-title', action='store_true', default=True,
                        help='文件名包含直播标题')
    parser.add_argument('--no-include-title', action='store_false', dest='include_title',
                        help='文件名不包含直播标题')
    parser.add_argument('--platform-folder', action='store_true', default=True,
                        help='按平台创建文件夹')
    parser.add_argument('--no-platform-folder', action='store_false', dest='platform_folder',
                        help='不按平台创建文件夹')
    parser.add_argument('--author-folder', action='store_true', default=True,
                        help='按主播创建文件夹')
    parser.add_argument('--no-author-folder', action='store_false', dest='author_folder',
                        help='不按主播创建文件夹')
    parser.add_argument('--time-folder', action='store_true', default=True,
                        help='按日期创建文件夹')
    parser.add_argument('--no-time-folder', action='store_false', dest='time_folder',
                        help='不按日期创建文件夹')
    parser.add_argument('--title-folder', action='store_true', default=False,
                        help='按标题创建文件夹')
    parser.add_argument('--no-title-folder', action='store_false', dest='title_folder',
                        help='不按标题创建文件夹')
    
    # 监控设置
    parser.add_argument('-i', '--interval', type=int, default=60,
                        help='检查直播状态的间隔时间(秒), 仅当模式为monitor时有效')
    
    # 其他设置
    parser.add_argument('--script', type=str, help='录制完成后运行的自定义脚本')
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 提取参数值
    live_url = args.url
    mode = args.mode
    output_dir = args.output_dir
    save_format = args.format
    record_quality = args.quality
    segment_record = args.segment
    segment_time = args.segment_time
    proxy = args.proxy
    cookies_file = args.cookies
    force_https = args.force_https
    include_title = args.include_title
    platform_folder = args.platform_folder
    author_folder = args.author_folder
    time_folder = args.time_folder
    title_folder = args.title_folder
    check_interval = args.interval
    custom_script = args.script
    
    # 加载cookies
    cookies = None
    if cookies_file and os.path.exists(cookies_file):
        try:
            with open(cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            print(f"已加载Cookies: {cookies_file}")
        except Exception as e:
            print(f"加载Cookies失败: {str(e)}")
    
    # 创建API对象
    stream_cap = StreamCapAPI(
        output_dir=output_dir,
        proxy=proxy,
        cookies=cookies,
        record_quality=record_quality,
        save_format=save_format,
        segment_record=segment_record,
        segment_time=segment_time,
        filename_includes_title=include_title,
        folder_name_platform=platform_folder,
        folder_name_author=author_folder,
        folder_name_time=time_folder,
        folder_name_title=title_folder,
        force_https_recording=force_https,
        custom_script_command=custom_script
    )
    
    # 创建一个变量来帮助处理优雅退出
    recording_or_monitoring = False
    
    try:
        if mode == "record":
            print(f"开始录制直播: {live_url}")
            recording_or_monitoring = True
            
            async def run_record():
                global exit_requested
                await stream_cap.start_recording(live_url)
                
                # 如果是收到外部停止请求而不是正常完成，则需要显式退出
                if exit_requested:
                    print("收到退出请求，程序即将退出...")
                    # 确保清理所有资源
                    if stream_cap.status_file_path and os.path.exists(stream_cap.status_file_path):
                        try:
                            os.remove(stream_cap.status_file_path)
                            print("已清理状态文件")
                        except Exception as e:
                            print(f"清理状态文件失败: {str(e)}")
                    sys.exit(0)
                    
            asyncio.run(run_record())
        elif mode == "monitor":
            print(f"开始监控直播: {live_url}，检查间隔: {check_interval}秒")
            recording_or_monitoring = True
            async def run_monitor():
                global exit_requested
                success = await stream_cap.start_monitoring(live_url, check_interval)
                if success:
                    print(f"监控已启动，按Ctrl+C停止...")
                    # 保持进程运行直到用户中断或收到退出请求
                    while not exit_requested:
                        await asyncio.sleep(1)
                    
                    # 如果是收到退出请求，则正常退出程序
                    if exit_requested:
                        print("收到退出请求，程序即将退出...")
                        # 确保清理所有资源
                        if stream_cap.status_file_path and os.path.exists(stream_cap.status_file_path):
                            try:
                                os.remove(stream_cap.status_file_path)
                                print("已清理状态文件")
                            except Exception as e:
                                print(f"清理状态文件失败: {str(e)}")
                        sys.exit(0)
                else:
                    print("启动监控失败")
            
            asyncio.run(run_monitor())
        else:
            print(f"不支持的模式: {mode}，请使用 'record' 或 'monitor'")
    except KeyboardInterrupt:
        print("\n用户中断，程序退出")
        
        # 尝试优雅地停止录制或监控
        if recording_or_monitoring:
            try:
                # 创建一个新的事件循环以执行清理操作
                cleanup_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(cleanup_loop)
                
                async def cleanup():
                    try:
                        if stream_cap.is_recording:
                            print("正在停止录制...")
                            await stream_cap.stop_recording()
                        
                        if stream_cap.is_monitoring:
                            print("正在停止监控...")
                            await stream_cap.stop_monitoring()
                    except Exception as e:
                        print(f"清理资源时出错: {str(e)}")
                
                cleanup_loop.run_until_complete(cleanup())
                cleanup_loop.close()
                print("已完成资源清理")
            except Exception as e:
                print(f"程序退出时出错: {str(e)}")
        
        sys.exit(0)
    except Exception as e:
        print(f"程序执行出错: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1) 