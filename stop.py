#!/usr/bin/env python3
import os
import sys
import json
import glob
import tempfile
import argparse

def list_running_recordings():
    """列出所有正在运行的录制进程"""
    # 查找所有的状态文件
    temp_dir = tempfile.gettempdir()
    status_file_pattern = os.path.join(temp_dir, "streamcap_*.status")
    status_files = glob.glob(status_file_pattern)
    
    if not status_files:
        print("当前没有运行的录制进程")
        return []
    
    print("发现以下正在运行的录制进程:")
    print("-" * 60)
    
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
                
                status = []
                if is_recording:
                    status.append("录制中")
                if is_monitoring:
                    status.append("监控中")
                
                print(f"[{idx}] PID: {pid}, 状态: {', '.join(status)}, URL: {monitor_url}")
        except Exception as e:
            print(f"读取状态文件 {status_file} 时出错: {str(e)}")
    
    print("-" * 60)
    return recordings

def stop_recording_by_id(recording_id, recordings):
    """根据ID停止特定的录制进程"""
    if not recordings:
        print("没有找到正在运行的录制进程")
        return False
    
    # 检查ID是否有效
    if recording_id < 1 or recording_id > len(recordings):
        print(f"无效的录制ID: {recording_id}，有效范围: 1-{len(recordings)}")
        return False
    
    # 获取对应的录制信息
    recording = recordings[recording_id - 1]
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
        
        print(f"已发送停止信号到进程 {recording['pid']}")
        print(f"正在停止{'录制' if recording['is_recording'] else ''}{' 和 ' if recording['is_recording'] and recording['is_monitoring'] else ''}{'监控' if recording['is_monitoring'] else ''}: {recording['url']}")
        return True
    except Exception as e:
        print(f"停止录制时出错: {str(e)}")
        return False

def stop_recording_by_url(url, recordings):
    """根据URL停止特定的录制进程"""
    if not recordings:
        print("没有找到正在运行的录制进程")
        return False
    
    # 查找匹配URL的录制
    matching_recordings = [r for r in recordings if url in r['url']]
    
    if not matching_recordings:
        print(f"没有找到URL包含 '{url}' 的录制进程")
        return False
    
    success = False
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
            
            print(f"已发送停止信号到进程 {recording['pid']}")
            print(f"正在停止{'录制' if recording['is_recording'] else ''}{' 和 ' if recording['is_recording'] and recording['is_monitoring'] else ''}{'监控' if recording['is_monitoring'] else ''}: {recording['url']}")
            success = True
        except Exception as e:
            print(f"停止录制时出错: {str(e)}")
    
    return success

def stop_all_recordings(recordings):
    """停止所有录制进程"""
    if not recordings:
        print("没有找到正在运行的录制进程")
        return False
    
    success = False
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
            
            print(f"已发送停止信号到进程 {recording['pid']}")
            print(f"正在停止{'录制' if recording['is_recording'] else ''}{' 和 ' if recording['is_recording'] and recording['is_monitoring'] else ''}{'监控' if recording['is_monitoring'] else ''}: {recording['url']}")
            success = True
        except Exception as e:
            print(f"停止录制时出错: {str(e)}")
    
    return success

def main():
    parser = argparse.ArgumentParser(description="StreamCap停止工具 - 停止指定的录制或监控")
    
    # 命令行参数
    parser.add_argument("-l", "--list", action="store_true", help="列出所有正在运行的录制进程")
    parser.add_argument("-i", "--id", type=int, help="根据ID停止录制")
    parser.add_argument("-u", "--url", type=str, help="根据URL停止录制")
    parser.add_argument("-a", "--all", action="store_true", help="停止所有录制")
    
    args = parser.parse_args()
    
    # 如果没有指定参数，显示帮助
    if not (args.list or args.id or args.url or args.all):
        parser.print_help()
        sys.exit(0)
    
    # 列出所有录制进程
    recordings = list_running_recordings()
    
    # 如果只是列出，直接返回
    if args.list:
        if not recordings:
            print("没有找到正在运行的录制进程")
        sys.exit(0)
    
    # 按ID停止
    if args.id:
        if stop_recording_by_id(args.id, recordings):
            print(f"已成功发送停止信号到录制ID: {args.id}")
        else:
            print(f"停止录制ID: {args.id} 失败")
    
    # 按URL停止
    if args.url:
        if stop_recording_by_url(args.url, recordings):
            print(f"已成功发送停止信号到包含URL: {args.url} 的录制进程")
        else:
            print(f"停止包含URL: {args.url} 的录制进程失败")
    
    # 停止所有
    if args.all:
        if stop_all_recordings(recordings):
            print("已成功发送停止信号到所有录制进程")
        else:
            print("停止所有录制进程失败")

if __name__ == "__main__":
    main() 