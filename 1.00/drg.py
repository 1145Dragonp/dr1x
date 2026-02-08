import json
import os
import glob
import re
import sys


def get_exe_dir():
    """获取 exe/脚本所在目录（兼容开发和打包环境）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后：sys.executable 指向原 exe 位置
        return os.path.dirname(sys.executable)
    else:
        # 开发环境：脚本所在目录
        return os.path.dirname(os.path.abspath(__file__))


EXE_DIR = get_exe_dir()


def load_config(filename="drg.json"):
    """从 exe 所在目录加载配置"""
    config_path = os.path.join(EXE_DIR, filename)
    
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"找不到配置文件: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    # 获取存档路径设置
    settings = config.pop("settings", {})
    save_path = settings.get("save_path", "./")
    
    # 相对路径基于 exe 目录解析
    if not os.path.isabs(save_path):
        save_path = os.path.join(EXE_DIR, save_path)
    
    save_path = os.path.normpath(save_path)
    
    return config, save_path


def find_save_files(base_name, save_path):
    """在指定目录查找存档文件"""
    pattern = os.path.join(save_path, f"{base_name}_*")
    files = glob.glob(pattern)
    
    valid_files = []
    for f in files:
        fname = os.path.basename(f)
        if re.match(rf"^{base_name}_\d+$", fname):
            valid_files.append(fname)
    
    return valid_files, save_path


def modify_line(content, line_number, new_value):
    """修改指定行的数字"""
    lines = content.split('\n')
    target_index = line_number - 1  # 转为 0-based
    
    if target_index < 0 or target_index >= len(lines):
        print(f"  警告: 行号 {line_number} 超出范围 (共 {len(lines)} 行)")
        return content
    
    original_line = lines[target_index]
    # 只替换第一个出现的数字
    modified_line = re.sub(r'\d+\.?\d*', str(new_value), original_line, count=1)
    lines[target_index] = modified_line
    
    return '\n'.join(lines)


def backup_file(file_path, save_path):
    """创建备份"""
    full_path = os.path.join(save_path, file_path)
    
    # 生成唯一备份名
    backup_path = f"{full_path}.backup"
    counter = 1
    while os.path.exists(backup_path):
        backup_path = f"{full_path}.backup{counter}"
        counter += 1
    
    # 复制内容
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  已备份: {os.path.basename(backup_path)}")
    return backup_path


def process_file(file_path, modifications, save_path):
    """处理单个存档文件"""
    print(f"\n处理: {file_path}")
    full_path = os.path.join(save_path, file_path)
    
    # 读取
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # 备份
    backup_file(file_path, save_path)
    
    # 修改
    modified_content = content
    for line_str, new_value in modifications.items():
        line_number = int(line_str)
        modified_content = modify_line(modified_content, line_number, new_value)
        print(f"  第 {line_number} 行 -> {new_value}")
    
    # 写入
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(modified_content)
    
    print(f"  完成")


def main():
    print("=" * 50)
    print("Deltarune 存档修改器")
    print("=" * 50)
    print(f"程序目录: {EXE_DIR}")
    
    # 调试信息
    if getattr(sys, 'frozen', False):
        print(f"运行模式: PyInstaller 打包 exe")
        print(f"原 exe 路径: {sys.executable}")
    else:
        print(f"运行模式: Python 开发环境")
    
    # 加载配置
    try:
        config, save_path = load_config()
        print(f"存档目录: {save_path}")
        print(f"配置章节: {len(config)} 个")
    except Exception as e:
        print(f"\n错误: 无法加载 drg.json - {e}")
        print(f"\n请确保 drg.json 与程序在同一目录:")
        print(f"  {EXE_DIR}")
        input("\n按回车退出...")
        return
    
    # 处理每个章节
    for chapter_key, modifications in config.items():
        print(f"\n{'='*50}")
        print(f"章节: {chapter_key}")
        
        save_files, actual_path = find_save_files(chapter_key, save_path)
        
        if not save_files:
            print(f"  未找到 {chapter_key}_* 存档文件")
            continue
        
        print(f"  找到 {len(save_files)} 个: {', '.join(save_files)}")
        
        for save_file in save_files:
            try:
                process_file(save_file, modifications, actual_path)
            except Exception as e:
                print(f"  错误: {e}")
    
    print(f"\n{'='*50}")
    print("所有修改完成！")
    input("按回车退出...")


if __name__ == "__main__":
    main()
