import sys
import threading
import time
import json
import uuid
import logging
from dataclasses import dataclass
from typing import Dict, Any, Iterator

import numpy
import websocket
import limxsdk.datatypes as datatypes

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [CLIENT] - %(levelname)s - %(message)s')

@dataclass
class RobotConfig:
    ip_address: str = "10.192.1.2" 
    accid: str = "DACH_TRON2A_003" #TODO: 替换为您机器人的真实序列号
    control_rate: int = 50
    action_dim: int = 14
    control_horizon: int = 10
    left_wrist_camera_serial: str = "230322270826"  # TODO: 替换为左手腕相机的真实序列号
    right_wrist_camera_serial: str = "230422272089" # TODO: 替换为右手腕相机的真实序列号
    head_camera_serial: str = "343622300603"        # TODO: 替换为头部相机
    left_wrist_camera: bool = False
    right_wrist_camera: bool = False
    head_camera: bool = True


class WebSocketManager:
    def __init__(self, ip_address: str):
        self.ws_url = f"ws://{ip_address}:5000"
        self.ws_client = None
        self.latest_state: Dict[str, Any] = {}
        self.is_connected = False
        
        self.thread = threading.Thread(target=self._run_forever, daemon=True)
        self.thread.start()

    def _on_open(self, ws):
        logging.info(f"成功连接到机器人 WebSocket 服务器 at {self.ws_url}")
        self.is_connected = True

    def _on_message(self, ws, message: str):
        try:
            data = json.loads(message)
            title = data.get("title", "")
            
            if title == "notify_robot_info": # 机器人基本信息每秒上报一次
                self.latest_state = data.get("data", {})
            else:
                logging.info(f"收到消息: {message}")
        except json.JSONDecodeError:
            logging.error(f"解析JSON失败: {message}")

    def _on_close(self, ws, close_status_code, close_msg):
        logging.warning(f"连接已关闭: {close_status_code} {close_msg}")
        self.is_connected = False

    def _on_error(self, ws, error):
        logging.error(f"WebSocket 错误: {error}")

    def _run_forever(self):
        """保持 WebSocket 连接"""
        logging.info("正在尝试连接机器人...")
        self.ws_client = websocket.WebSocketApp(
            self.ws_url,
            on_open=self._on_open,
            on_message=self._on_message,
            on_close=self._on_close,
            on_error=self._on_error
        )
        self.ws_client.run_forever()

    def send_command(self, command: Dict[str, Any]):
        """向机器人发送 JSON 指令"""
        if self.is_connected and self.ws_client:
            try:
                self.ws_client.send(json.dumps(command))
            except Exception as e:
                logging.error(f"发送指令失败: {e}")
        else:
            logging.error("无法发送指令：机器人未连接。")
            
    def get_latest_state(self) -> Dict[str, Any]:
        return self.latest_state

class MoveJSequence:
    def __init__(self, config: RobotConfig, policy_inference_result: numpy.ndarray):    # shape (T, 14)
        self.config = config
        self.policy_inference_result = policy_inference_result
        self.current_step = 0
        
        expected_shape = (config.control_horizon, config.action_dim)
        if policy_inference_result.shape != expected_shape:
            raise ValueError(f"期望 policy_inference_result 的形状为 {expected_shape}, 但得到 {policy_inference_result.shape}")

    def __iter__(self) -> Iterator[Dict[str, Any]]:
        self.current_step = 0
        return self

    def __next__(self) -> Dict[str, Any]:
        if self.current_step >= self.policy_inference_result.shape[0]:
            raise StopIteration
        
        cmd = self.get_single_cmd(self.current_step)
        self.current_step += 1
        return cmd

    def get_single_cmd(self, step: int = 0) -> Dict[str, Any]:
        """为单个步骤生成 movej JSON 指令"""
        if step >= self.policy_inference_result.shape[0]:
            raise IndexError(f"步骤 {step} 超出动作范围 {self.policy_inference_result.shape[0]}")
            
        current_action = self.policy_inference_result[step]
        
        command = {
            "accid": self.config.accid,
            "title": "request_movej",
            "timestamp": int(time.time() * 1000),
            "guid": str(uuid.uuid4()),
            "data": {
                # "time": 1.0 / self.config.control_rate,
                "time": 3,  # 逻辑有问题，但是直接使用控制频率太快会很危险
                "joint": current_action.tolist() # 14 joint values in radians
            }
        }
        return command

class Tron2:
    def __init__(self, config: RobotConfig):
        self.config = config
        self.ws_manager = WebSocketManager(config.ip_address)
        
        while not self.ws_manager.is_connected:
            time.sleep(0.5)
        
        logging.info("机器人控制实例创建成功！")

    def get_state(self) -> Dict[str, Any]:
        return self.ws_manager.get_latest_state()
    
    def control(self, movej_sequence: MoveJSequence):
        try:
            for cmd in movej_sequence:
                self.ws_manager.send_command(cmd)
                time.sleep(1.0 / self.config.control_rate)
        except Exception as e:
            logging.error(f"发送控制序列失败: {e}")
    
    def control_single_step(self, movej_sequence: MoveJSequence, step: int = 0):
        try:
            cmd = movej_sequence.get_single_cmd(step)
            self.ws_manager.send_command(cmd)
        except Exception as e:
            logging.error(f"发送单步控制指令失败: {e}")

    def set_robot_light(self, light_effect: datatypes.LightEffect):
        effect_id = light_effect.value + 1
        
        command = {
            "accid": self.config.accid,
            "title": "request_light_effect",
            "timestamp": int(time.time() * 1000),
            "guid": str(uuid.uuid4()),
            "data": {
                "effect": effect_id
            }
        }
        self.ws_manager.send_command(command)


# 流程就是首先实例化Tron2，通过策略获取动作序列，然后执行MoveJSequence，然后执行control方法
if __name__ == '__main__':
    robot_config = RobotConfig()
    tron2_controller = Tron2(robot_config)
    logging.info("设置灯效为静态绿光...")
    tron2_controller.set_robot_light(datatypes.LightEffect.STATIC_GREEN)
    time.sleep(2)

    logging.info("准备执行一个动作序列...")
    dummy_policy_output = numpy.random.uniform(low=-0.2, high=0.2, size=(robot_config.control_horizon, robot_config.action_dim))
    
    action_sequence = MoveJSequence(robot_config, dummy_policy_output)
    print(action_sequence)
    logging.info("开始执行控制序列...")
    tron2_controller.control(action_sequence)
    logging.info("控制序列执行完毕。")
    
    time.sleep(2)

    logging.info("获取机器人当前状态...")
    current_state = tron2_controller.get_state()
    if current_state:
        logging.info(f"获取到机器人状态: {current_state}")
    else:
        logging.warning("未能获取到机器人状态。")
        
    logging.info("设置灯效为慢闪红色...")
    tron2_controller.set_robot_light(datatypes.LightEffect.LOW_FLASH_RED)
    
    logging.info("示例程序结束。")