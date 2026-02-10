import json
import os
import glob
import re
import sys
import ctypes
import shutil
from ctypes import wintypes

# Windows API 常量
OFN_FILEMUSTEXIST = 0x00001000
OFN_NOCHANGEDIR = 0x00000008

# 定义 OPENFILENAME 结构
class OPENFILENAME(ctypes.Structure):
    _fields_ = [
        ("lStructSize", wintypes.DWORD),
        ("hwndOwner", wintypes.HWND),
        ("hInstance", wintypes.HINSTANCE),
        ("lpstrFilter", wintypes.LPCWSTR),
        ("lpstrCustomFilter", wintypes.LPWSTR),
        ("nMaxCustFilter", wintypes.DWORD),
        ("nFilterIndex", wintypes.DWORD),
        ("lpstrFile", wintypes.LPWSTR),
        ("nMaxFile", wintypes.DWORD),
        ("lpstrFileTitle", wintypes.LPWSTR),
        ("nMaxFileTitle", wintypes.DWORD),
        ("lpstrInitialDir", wintypes.LPCWSTR),
        ("lpstrTitle", wintypes.LPCWSTR),
        ("Flags", wintypes.DWORD),
        ("nFileOffset", wintypes.WORD),
        ("nFileExtension", wintypes.WORD),
        ("lpstrDefExt", wintypes.LPCWSTR),
        ("lCustData", wintypes.LPARAM),
        ("lpfnHook", wintypes.LPVOID),
        ("lpTemplateName", wintypes.LPCWSTR),
        ("pvReserved", wintypes.LPVOID),
        ("dwReserved", wintypes.DWORD),
        ("FlagsEx", wintypes.DWORD),
    ]

def select_file_dialog(title="选择 drg.json 配置文件", filter_text="JSON文件\0*.json\0所有文件\0*.*\0"):
    """使用 Windows API 弹出文件选择对话框"""
    buffer_size = 260
    file_buffer = ctypes.create_unicode_buffer(buffer_size)
    
    ofn = OPENFILENAME()
    ofn.lStructSize = ctypes.sizeof(OPENFILENAME)
    ofn.hwndOwner = None
    ofn.lpstrFilter = filter_text
    ofn.lpstrFile = ctypes.cast(file_buffer, wintypes.LPWSTR)
    ofn.nMaxFile = buffer_size
    ofn.lpstrTitle = title
    ofn.Flags = OFN_FILEMUSTEXIST | OFN_NOCHANGEDIR
    
    comdlg32 = ctypes.windll.comdlg32
    result = comdlg32.GetOpenFileNameW(ctypes.byref(ofn))
    
    if result:
        return file_buffer.value
    return None


def get_exe_dir():
    """获取 exe/脚本所在目录（兼容开发和打包环境）"""
    if getattr(sys, 'frozen', False):
        # PyInstaller 打包后，sys.executable 是 exe 文件本身
        return os.path.dirname(sys.executable)
    else:
        # 开发环境，使用脚本所在目录
        return os.path.dirname(os.path.abspath(__file__))


EXE_DIR = get_exe_dir()


def load_config(filename="drg.json"):
    """从 exe 所在目录加载配置，找不到则提示选择或恢复备份"""
    config_path = os.path.join(EXE_DIR, filename)
    
    if not os.path.exists(config_path):
        print(f"\n未找到默认配置文件: {config_path}")
        print("按 1 选择配置文件，按 3 恢复备份，或其他键退出...")
        
        try:
            choice = input("> ").strip()
        except:
            choice = ""
        
        if choice == "1":
            selected = select_file_dialog()
            if selected and os.path.exists(selected):
                config_path = selected
                print(f"已选择: {config_path}")
            else:
                raise FileNotFoundError("未选择有效文件")
        elif choice == "3":
            return None, None, True  # 第三个值标记进入恢复模式
        else:
            raise FileNotFoundError("用户取消选择")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    settings = config.pop("settings", {})
    save_path = settings.get("save_path", "./")
    
    if not os.path.isabs(save_path):
        save_path = os.path.join(EXE_DIR, save_path)
    
    save_path = os.path.normpath(save_path)
    
    return config, save_path, False


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


def find_backup_files(save_path):
    """查找所有备份文件"""
    pattern = os.path.join(save_path, "*.backup")
    return glob.glob(pattern)


def backup_file(file_path, save_path):
    """创建备份（覆盖旧备份）"""
    full_path = os.path.join(save_path, file_path)
    backup_path = f"{full_path}.backup"
    
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(content)
    
    print(f"  已备份: {os.path.basename(backup_path)}")
    return backup_path


def restore_backup(file_path, save_path):
    """从备份恢复"""
    full_path = os.path.join(save_path, file_path)
    backup_path = f"{full_path}.backup"
    
    if not os.path.exists(backup_path):
        print(f"  警告: 无备份文件 {os.path.basename(backup_path)}")
        return False
    
    # 恢复前保存当前状态到临时文件
    if os.path.exists(full_path):
        temp_backup = f"{full_path}.temp"
        shutil.copy2(full_path, temp_backup)
    
    # 执行恢复
    shutil.copy2(backup_path, full_path)
    
    # 删除临时备份
    if os.path.exists(temp_backup):
        os.remove(temp_backup)
    
    print(f"  已恢复: {file_path}")
    return True


def modify_line(content, line_number, new_value):
    """修改指定行的数字"""
    lines = content.split('\n')
    target_index = line_number - 1
    
    if target_index < 0 or target_index >= len(lines):
        print(f"  警告: 行号 {line_number} 超出范围 (共 {len(lines)} 行)")
        return content
    
    original_line = lines[target_index]
    modified_line = re.sub(r'\d+\.?\d*', str(new_value), original_line, count=1)
    lines[target_index] = modified_line
    
    return '\n'.join(lines)


def process_file(file_path, modifications, save_path):
    """处理单个存档文件（修改模式）"""
    print(f"\n处理: {file_path}")
    full_path = os.path.join(save_path, file_path)
    
    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    backup_file(file_path, save_path)
    
    modified_content = content
    for line_str, new_value in modifications.items():
        line_number = int(line_str)
        modified_content = modify_line(modified_content, line_number, new_value)
        print(f"  第 {line_number} 行 -> {new_value}")
    
    with open(full_path, 'w', encoding='utf-8') as f:
        f.write(modified_content)
    
    print(f"  完成")


def restore_all_backups(save_path):
    """恢复所有备份"""
    print(f"\n{'='*50}")
    print("恢复备份模式")
    print(f"存档目录: {save_path}")
    print(f"{'='*50}")
    
    # 查找所有备份文件
    backup_files = find_backup_files(save_path)
    
    if not backup_files:
        print(f"未找到任何备份文件")
        return False
    
    print(f"找到 {len(backup_files)} 个备份文件:")
    for bf in backup_files:
        print(f"  - {os.path.basename(bf)}")
    
    print(f"\n确认恢复所有备份? (输入 yes 确认)")
    try:
        confirm = input("> ").strip().lower()
    except:
        confirm = ""
    
    if confirm != "yes":
        print("取消恢复")
        return False
    
    # 执行恢复
    restored_count = 0
    for backup_path in backup_files:
        original_name = os.path.basename(backup_path).replace(".backup", "")
        
        try:
            if restore_backup(original_name, save_path):
                restored_count += 1
        except Exception as e:
            print(f"  错误恢复 {original_name}: {e}")
    
    print(f"\n成功恢复 {restored_count}/{len(backup_files)} 个文件")
    return True


def main():
    print("=" * 50)
    print("Deltarune 存档修改器 v2.0")
    print("=" * 50)
    print(f"程序目录: {EXE_DIR}")
    
    if getattr(sys, 'frozen', False):
        print(f"运行模式: PyInstaller 打包 exe")
        print(f"原 exe 路径: {sys.executable}")
    else:
        print(f"运行模式: Python 开发环境")
    
    # 加载配置
    try:
        config, save_path, is_restore_mode = load_config()
        
        # 触发恢复模式
        if is_restore_mode:
            # 直接使用 EXE_DIR 作为存档目录，无需用户输入
            save_path = EXE_DIR
            
            if not os.path.exists(save_path):
                print(f"程序目录不存在: {save_path}")
                input("\n按回车退出...")
                return
            
            restore_all_backups(save_path)
            input("\n按回车退出...")
            return
        
        print(f"存档目录: {save_path}")
        print(f"配置章节: {len(config)} 个")
        
    except Exception as e:
        print(f"\n错误: {e}")
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
    print("提示: 删除 drg.json 后启动，按 3 可恢复备份")
    input("按回车退出...")


if __name__ == "__main__":
    main()
