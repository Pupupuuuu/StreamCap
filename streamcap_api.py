import asyncio
import os
import time
import json
from datetime import datetime
import sys
import streamget
from typing import Optional, Dict, Any, List, Union

# 视频质量枚举
class VideoQuality:
    OD = "原画"
    HD = "高清"
    SD = "标清"
    LD = "流畅"

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
        self.save_format = save_format.lower()
        self.segment_record = segment_record
        self.segment_time = str(segment_time)
        
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
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
    
    def clean_name(self, name: str, default: str = None) -> str:
        """清理名称，移除不允许的字符"""
        if not name:
            return default or ""
            
        # 移除特殊字符
        for char in ['\\', '/', ':', '*', '?', '"', '<', '>', '|']:
            name = name.replace(char, '')
        
        # 移除前后空格
        name = name.strip()
        
        return name or default or ""
    
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
        
        now = datetime.today().strftime("%Y-%m-%d_%H-%M-%S")
        output_dir = self.output_dir.rstrip("/").rstrip("\\")
        
        if self.folder_name_platform:
            output_dir = os.path.join(output_dir, stream_info.platform)
            
        if self.folder_name_author:
            output_dir = os.path.join(output_dir, stream_info.anchor_name)
            
        if self.folder_name_time:
            output_dir = os.path.join(output_dir, now[:10])
            
        if self.folder_name_title and stream_info.title:
            live_title = self._clean_and_truncate_title(stream_info.title)
            if self.folder_name_time:
                output_dir = os.path.join(output_dir, f"{live_title}_{stream_info.anchor_name}")
            else:
                output_dir = os.path.join(output_dir, f"{now[:10]}_{live_title}")
                
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
    
    def _build_ffmpeg_command(self, record_url: str, save_path: str) -> List[str]:
        """构建FFmpeg命令"""
        ffmpeg_command = ["ffmpeg", "-y"]
        
        # 添加用户代理
        headers = {}
        if "douyin.com" in record_url:
            headers["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"
            headers["referer"] = "https://live.douyin.com/"
        elif "tiktok.com" in record_url:
            headers["user-agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/107.0.0.0 Safari/537.36"
            headers["referer"] = "https://www.tiktok.com/"
        
        if headers:
            for key, value in headers.items():
                ffmpeg_command.extend(["-headers", f"{key}: {value}"])
        
        # 添加代理
        if self.proxy:
            if self.proxy.startswith("http"):
                ffmpeg_command.extend(["-http_proxy", self.proxy])
            elif self.proxy.startswith("socks"):
                ffmpeg_command.extend(["-socks", self.proxy])
        
        # 添加输入
        ffmpeg_command.extend(["-i", record_url])
        
        # 添加分段参数
        if self.segment_record and self.save_format != "flv":
            ffmpeg_command.extend([
                "-f", "segment",
                "-segment_time", self.segment_time,
                "-reset_timestamps", "1"
            ])
        
        # 添加编码参数
        ffmpeg_command.extend([
            "-c", "copy",
            "-bsf:a", "aac_adtstoasc"
        ])
        
        # 添加输出路径
        ffmpeg_command.append(save_path)
        
        return ffmpeg_command
    
    async def start_recording(self, live_url: str) -> str:
        """开始录制直播"""
        try:
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
            
            # 构建ffmpeg命令
            ffmpeg_command = self._build_ffmpeg_command(record_url, save_path)
            
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
            
            # 等待进程完成
            print("录制进行中，按Ctrl+C停止...")
            try:
                await self.ffmpeg_process.wait()
                
                # 检查返回码
                if self.ffmpeg_process.returncode == 0:
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
            finally:
                self.is_recording = False
            
            # 如果有自定义脚本，运行它
            if self.custom_script_command:
                await self.run_custom_script(self.custom_script_command, save_path)
            
            return save_path
            
        except Exception as e:
            print(f"录制过程中发生错误: {str(e)}")
            import traceback
            traceback.print_exc()
            self.is_recording = False
            return None
    
    async def stop_recording(self):
        """停止录制"""
        if not self.is_recording or not self.ffmpeg_process:
            return
            
        # 在Windows上用q来优雅地关闭ffmpeg
        if os.name == "nt" and self.ffmpeg_process.stdin:
            try:
                self.ffmpeg_process.stdin.write(b"q")
                await self.ffmpeg_process.stdin.drain()
            except Exception as e:
                print(f"发送退出命令时出错: {str(e)}")
        
        # 其他平台或当stdin失败时，尝试终止进程
        try:
            self.ffmpeg_process.terminate()
            # 等待进程结束，超时后强制终止
            try:
                await asyncio.wait_for(self.ffmpeg_process.wait(), timeout=5.0)
            except asyncio.TimeoutError:
                print("FFmpeg进程没有及时退出，强制终止")
                self.ffmpeg_process.kill()
                await self.ffmpeg_process.wait()
        except Exception as e:
            print(f"终止录制过程时出错: {str(e)}")
        
        self.is_recording = False
        self.ffmpeg_process = None
    
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
    
    async def converts_mp4(self, file_path: str, delete_original: bool = True) -> str:
        """将录制文件转换为MP4格式"""
        if self.save_format == "mp4":
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
                print("转换成功")
                if delete_original and os.path.exists(output_path):
                    os.remove(original_path)
                    print(f"已删除原始文件: {original_path}")
                return output_path
            else:
                print(f"转换失败，返回码: {process.returncode}")
                if stderr:
                    print(f"FFmpeg错误: {stderr.decode('utf-8', errors='ignore')}")
                return original_path
                
        except Exception as e:
            print(f"转换文件时出错: {str(e)}")
            return file_path

async def main():
    # 创建命令行参数解析器
    parser = argparse.ArgumentParser(description="StreamCap API - 直播录制工具")
    
    # 必需参数
    parser.add_argument("--url", type=str, required=True, help="直播间URL地址")
    
    # 输出相关参数
    parser.add_argument("--output", type=str, default="downloads", help="输出目录")
    parser.add_argument("--format", type=str, default="mp4", choices=["mp4", "flv", "ts"], help="录制格式")
    
    # 录制选项
    parser.add_argument("--quality", type=str, default="原画", choices=["原画", "高清", "标清", "流畅"], help="录制画质")
    parser.add_argument("--segment", action="store_true", help="启用分段录制")
    parser.add_argument("--segment-time", type=int, default=1800, help="分段时间(秒)")
    
    # 代理和网络选项
    parser.add_argument("--proxy", type=str, help="代理地址, 例如: http://127.0.0.1:7890")
    parser.add_argument("--cookies", type=str, help="Cookies文件路径(JSON格式)")
    parser.add_argument("--force-https", action="store_true", help="强制使用HTTPS录制")
    
    # 文件名选项
    parser.add_argument("--include-title", action="store_true", default=True, help="文件名包含标题")
    parser.add_argument("--platform-folder", action="store_true", default=True, help="创建平台文件夹")
    parser.add_argument("--author-folder", action="store_true", default=True, help="创建主播文件夹")
    parser.add_argument("--time-folder", action="store_true", default=True, help="创建日期文件夹")
    parser.add_argument("--title-folder", action="store_true", help="创建标题文件夹")
    
    # 后处理选项
    parser.add_argument("--script", type=str, help="录制完成后运行的自定义脚本")
    parser.add_argument("--convert-mp4", action="store_true", help="非MP4格式录制完成后转换为MP4")
    
    # 解析命令行参数
    args = parser.parse_args()
    
    # 加载cookies
    cookies = None
    if args.cookies and os.path.exists(args.cookies):
        try:
            with open(args.cookies, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            print(f"已加载Cookies: {args.cookies}")
        except Exception as e:
            print(f"加载Cookies失败: {str(e)}")
    
    # 创建API对象
    stream_cap = StreamCapAPI(
        output_dir=args.output,
        proxy=args.proxy,
        cookies=cookies,
        record_quality=args.quality,
        save_format=args.format,
        segment_record=args.segment,
        segment_time=args.segment_time,
        filename_includes_title=args.include_title,
        folder_name_platform=args.platform_folder,
        folder_name_author=args.author_folder,
        folder_name_time=args.time_folder,
        folder_name_title=args.title_folder,
        force_https_recording=args.force_https,
        custom_script_command=args.script
    )
    
    # 开始录制
    save_path = await stream_cap.start_recording(args.url)
    
    # 转换为MP4
    if save_path and args.convert_mp4 and args.format != "mp4":
        save_path = await stream_cap.converts_mp4(save_path)
        
    if save_path:
        print(f"录制完成: {save_path}")

if __name__ == "__main__":
    import argparse
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n用户中断，程序退出")
        sys.exit(0) 