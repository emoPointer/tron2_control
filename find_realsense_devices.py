import pyrealsense2 as rs

def list_devices():
    """
    列出所有连接的Intel RealSense设备及其序列号。
    """
    ctx = rs.context()
    devices = ctx.query_devices()
    
    if not devices:
        print("未找到任何RealSense设备。请检查USB连接。")
        return

    print(f"找到 {len(devices)} 个RealSense设备:")
    print("-" * 50)
    for i, dev in enumerate(devices):
        serial_number = dev.get_info(rs.camera_info.serial_number)
        product_line = dev.get_info(rs.camera_info.product_line)
        name = dev.get_info(rs.camera_info.name)
        
        print(f"  设备 #{i+1}:")
        print(f"    - 名称 (Name)    : {name}")
        print(f"    - 型号 (Product) : {product_line}")
        print(f"    - 序列号 (Serial) : {serial_number}")
        print("-" * 50)

if __name__ == "__main__":
    list_devices()