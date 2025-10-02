import pyrealsense2 as rs
import numpy as np
import cv2
from tron2_control import RobotConfig # 假设这个导入是有效的

class RealSenseMultiCamManager:
    def __init__(self, config: RobotConfig):
        self.left_wrist_camera_serial = config.left_wrist_camera_serial
        self.right_wrist_camera_serial = config.right_wrist_camera_serial
        self.head_camera_serial = config.head_camera_serial
        self.all_serials = [
            self.left_wrist_camera_serial, 
            self.right_wrist_camera_serial, 
            self.head_camera_serial
        ]

        self.pipelines = {}
        self.aligners = {}
        self.profiles = {}

        self._initialize_cameras()

    def _initialize_cameras(self):
        """
        根据提供的序列号查找、配置并启动所有摄像头。
        """
        ctx = rs.context()
        devices = ctx.query_devices()
        
        connected_serials = [dev.get_info(rs.camera_info.serial_number) for dev in devices]
        print(f"已连接的设备: {connected_serials}")

        for serial in self.all_serials:
            if serial not in connected_serials:
                raise Exception(f"错误: 序列号为 {serial} 的相机未连接!")

        for serial in self.all_serials:
            pipe = rs.pipeline()
            rsconfig = rs.config()
            rsconfig.enable_device(serial)

            # 建议根据相机型号进行不同配置，以获得更佳性能
            if serial == self.head_camera_serial:
                cam_id = f"head_{serial}"
                rsconfig.enable_stream(rs.stream.depth, 848, 480, rs.format.z16, 30)
                rsconfig.enable_stream(rs.stream.color, 848, 480, rs.format.bgr8, 30)
            elif serial == self.left_wrist_camera_serial:
                cam_id = f"left_wrist_{serial}"
                rsconfig.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
                rsconfig.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
            elif serial == self.right_wrist_camera_serial:
                cam_id = f"right_wrist_{serial}"
                rsconfig.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 30)
                rsconfig.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 30)
            
            print(f"正在启动相机: {cam_id}...")
            profile = pipe.start(rsconfig)
            self.pipelines[cam_id] = pipe
            self.profiles[cam_id] = profile
            self.aligners[cam_id] = rs.align(rs.stream.color)
            
        print("\n所有相机初始化成功！")

    def get_frames(self, get_depth: bool = False):
        """
        从所有相机获取帧数据。
        :param get_depth: True则获取深度图，False则不获取。
        :return: 一个字典，键是相机ID，值是包含'color' (BGR) 和 'depth' 图像的字典。
        """
        all_frames_data = {}
        
        for cam_id, pipe in self.pipelines.items():
            try:
                frames = pipe.wait_for_frames(timeout_ms=2000)
            except RuntimeError:
                print(f"警告: 从相机 {cam_id} 获取帧超时。")
                all_frames_data[cam_id] = {'color': None, 'depth': None}
                continue

            aligned_frames = self.aligners[cam_id].process(frames)
            color_frame = aligned_frames.get_color_frame()
            color_image = np.asanyarray(color_frame.get_data()) if color_frame else None
            depth_image = None
            
            if get_depth:
                depth_frame = aligned_frames.get_depth_frame()
                if depth_frame:
                    # 获取原始深度数据 (uint16)
                    depth_image = np.asanyarray(depth_frame.get_data())
            
            all_frames_data[cam_id] = {
                'color': color_image,
                'depth': depth_image,
            }
            
        return all_frames_data

    def stop(self):
        print("\n正在停止所有相机...")
        for pipe in self.pipelines.values():
            pipe.stop()
        print("所有相机已停止。")


# --- 为了让此文件能独立运行，我们创建一个模拟的RobotConfig类 ---
class MockRobotConfig:
    """一个用于测试的模拟RobotConfig类。"""
    def __init__(self):
        # ！！！请务必将这里的序列号替换为您自己的相机序列号！！！
        self.head_camera_serial = "215122254363"  # <-- 替换成你的D455/头部相机序列号
        self.left_wrist_camera_serial = "213622252433" # <-- 替换成你的左腕D405序列号
        self.right_wrist_camera_serial = "213622250553"  # <-- 替换成你的右腕D405序列号

if __name__ == "__main__":
    # 使用模拟的Config类进行测试。在您的实际项目中，您会导入并使用真实的RobotConfig。
    robotconfig = MockRobotConfig() 
    
    cam_manager = None # 在try块外部定义，以便finally块可以访问
    try:
        # 1. 初始化相机管理器
        cam_manager = RealSenseMultiCamManager(config=robotconfig)
        print("相机初始化成功!")
        
        # 控制是否“获取”深度数据，默认为False
        get_depth_enabled = False 
        print("\n相机已就绪。按 'D' 键切换深度数据获取，按 'Q' 键退出。")

        while True:
            # 2. 调用方法获取所有图像
            frames_data = cam_manager.get_frames(get_depth=get_depth_enabled)
            
            all_color_images = []

            # 3. 处理并显示彩色图像
            for cam_id, data in frames_data.items():
                color_img = data['color']

                if color_img is not None:
                    cv2.putText(color_img, cam_id, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    all_color_images.append(color_img)
            
            # 将所有彩色图像拼接起来显示
            if all_color_images:
                # 为了防止窗口过大，我们可以在拼接前缩放图像
                resized_images = [cv2.resize(img, (int(img.shape[1] * 0.75), int(img.shape[0] * 0.75))) for img in all_color_images]
                display_color = cv2.hconcat(resized_images)
                cv2.imshow('All Color Images', display_color)

            key = cv2.waitKey(1) & 0xFF
            
            # 按 'q' 退出
            if key == ord('q'):
                break
            
            # 按 'd' 切换深度数据的获取
            if key == ord('d'):
                get_depth_enabled = not get_depth_enabled
                status = "开启" if get_depth_enabled else "关闭"
                print(f"深度数据获取已 {status}")
                # 示例：如果开启了深度获取，打印头部相机的中心点深度
                if get_depth_enabled:
                    head_cam_id = f"head_{robotconfig.head_camera_serial}"
                    if frames_data.get(head_cam_id) and frames_data[head_cam_id]['depth'] is not None:
                        depth_data = frames_data[head_cam_id]['depth']
                        h, w = depth_data.shape
                        center_depth = depth_data[h//2, w//2]
                        print(f"头部相机中心点深度: {center_depth} mm")


    except Exception as e:
        print(f"发生错误: {e}")
    
    finally:
        # 4. 确保在程序结束时停止相机
        if cam_manager:
            cam_manager.stop()
        cv2.destroyAllWindows()
        print("程序已退出。")