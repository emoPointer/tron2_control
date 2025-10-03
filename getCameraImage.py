import pyrealsense2 as rs
import numpy as np
import cv2
from tron2_control import RobotConfig 

class MultiCamManager:
    def __init__(self, config):
        self.config = config
        self.pipelines = {}
        self.aligners = {}
        self.profiles = {}
        self.active_serials = []

        print("根据配置检查需要启动的相机...")
        if self.config.head_camera:
            self.active_serials.append(self.config.head_camera_serial)
            print(f" - [启用] 头部相机 (Serial: {self.config.head_camera_serial})")
        
        if self.config.left_wrist_camera:
            self.active_serials.append(self.config.left_wrist_camera_serial)
            print(f" - [启用] 左手腕相机 (Serial: {self.config.left_wrist_camera_serial})")

        if self.config.right_wrist_camera:
            self.active_serials.append(self.config.right_wrist_camera_serial)
            print(f" - [启用] 右手腕相机 (Serial: {self.config.right_wrist_camera_serial})")

        if not self.active_serials:
            print("\n警告: 配置文件中没有启用任何相机。")
            return

        self._initialize_cameras()

    def _initialize_cameras(self):
        ctx = rs.context()
        devices = ctx.query_devices()
        
        connected_serials = [dev.get_info(rs.camera_info.serial_number) for dev in devices]
        print(f"\n已连接的设备: {connected_serials}")

        for serial in self.active_serials:
            if serial not in connected_serials:
                raise Exception(f"错误: 配置中启用的相机 (序列号: {serial}) 未连接!")

        for serial in self.active_serials:
            pipe = rs.pipeline()
            rsconfig = rs.config()
            rsconfig.enable_device(serial)

            cam_id = ""
            if serial == self.config.head_camera_serial:
                cam_id = f"head_{serial}"
                rsconfig.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 15)
                rsconfig.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 15)
            elif serial == self.config.left_wrist_camera_serial:
                cam_id = f"left_wrist_{serial}"
                rsconfig.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 15)
                rsconfig.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 15)
            elif serial == self.config.right_wrist_camera_serial:
                cam_id = f"right_wrist_{serial}"
                rsconfig.enable_stream(rs.stream.depth, 640, 480, rs.format.z16, 15)
                rsconfig.enable_stream(rs.stream.color, 640, 480, rs.format.bgr8, 15)
            
            if not cam_id: continue

            print(f"正在启动相机: {cam_id}...")
            profile = pipe.start(rsconfig)
            self.pipelines[cam_id] = pipe
            self.profiles[cam_id] = profile
            self.aligners[cam_id] = rs.align(rs.stream.color)
            
        print(f"\n共 {len(self.pipelines)} 个相机初始化成功！")

    def get_frames(self, get_depth: bool = False):
        all_frames_data = {}
        for cam_id, pipe in self.pipelines.items():
            try:
                frames = pipe.wait_for_frames(timeout_ms=2000)
                aligned_frames = self.aligners[cam_id].process(frames)
                color_frame = aligned_frames.get_color_frame()
                
                color_image = np.asanyarray(color_frame.get_data()) if color_frame else None
                depth_image = None
                
                if get_depth:
                    depth_frame = aligned_frames.get_depth_frame()
                    if depth_frame:
                        depth_image = np.asanyarray(depth_frame.get_data())
                
                all_frames_data[cam_id] = {'color': color_image, 'depth': depth_image}

            except RuntimeError:
                print(f"警告: 从相机 {cam_id} 获取帧超时，检查是否插入3.0接口。")
                all_frames_data[cam_id] = {'color': None, 'depth': None}
                continue
            
        return all_frames_data

    def stop(self):
        if not self.pipelines: return
        print(f"\n正在停止 {len(self.pipelines)} 个相机...")
        for pipe in self.pipelines.values():
            pipe.stop()
        print("所有相机已停止。")


# 流程就是实例化 MultiCamManager，然后不断调用 get_frames() 获取图像，get_frames返回一个字典，key是相机ID，value是包含color和depth图像的字典，字典处理见下方
if __name__ == "__main__":
    robotconfig = RobotConfig() 
    cam_manager = None
    try:
        cam_manager = MultiCamManager(config=robotconfig)
        
        # if not cam_manager.pipelines:
        #      print("没有相机被启动，程序退出。")
        #      exit()

        while True:
            frames_data = cam_manager.get_frames()
            if not frames_data: continue

            all_color_images = []
            for cam_id, data in frames_data.items():
                color_img = data['color']
                if color_img is not None:
                    cv2.putText(color_img, cam_id.split('_')[0], (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                    all_color_images.append(color_img)
            
            if all_color_images:
                display_color = cv2.hconcat(all_color_images)
                cv2.imshow('Active Cameras Color View', display_color)
            key = cv2.waitKey(1) & 0xFF


    except Exception as e:
        print(f"发生错误: {e}")
    
    finally:
        if cam_manager:
            cam_manager.stop()
        cv2.destroyAllWindows()
        print("程序已退出。")