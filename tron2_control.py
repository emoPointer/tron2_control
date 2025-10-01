import sys
import threading
import time
import numpy
from dataclasses import dataclass
import logging
from multiprocessing.connection import Client

import limxsdk.robot.Rate as Rate
import limxsdk.robot.Robot as Robot
import limxsdk.robot.RobotType as RobotType
import limxsdk.datatypes as datatypes

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [CLIENT] - %(levelname)s - %(message)s')

SERVER_ADDRESS = ('localhost', 6001)
SERVER_AUTH_KEY = b'tron2_secret_key'

@dataclass
class RobotConfig:
    ip_address: str = "10.192.1.2"
    motor_number: int = 16
    control_rate: int = 500
    motor_mode: int = 0
    motor_Kp: float = 1.0
    motor_Kd: float = 1.0
    motor_dp: float = 0.1
    motor_tau: float = 1.0
    action_dim: int = 14
    control_horizon: int = 10

class DoubleArmMsg:
    def __init__(self, config: RobotConfig, policy_inference_result: numpy.ndarray):
        self.config = config
        self.policy_inference_result = policy_inference_result
        self.current_step = 0
        expected_shape = (config.control_horizon, config.action_dim)
        if policy_inference_result.shape != expected_shape:
            raise ValueError(f"Expected policy_inference_result shape {expected_shape}, but got {policy_inference_result.shape}")

    def __iter__(self):
        self.current_step = 0
        return self

    def __next__(self):
        if self.current_step >= self.policy_inference_result.shape[0]:
            raise StopIteration
        
        # 为了代码复用，让 __next__ 调用 get_single_cmd
        cmd_msg = self.get_single_cmd(self.current_step)
        self.current_step += 1
        return cmd_msg

    # --- 修正：将 get_single_cmd 方法加回来 ---
    def get_single_cmd(self, step: int = 0):
        if step >= self.policy_inference_result.shape[0]:
            raise IndexError(f"Step {step} exceeds action horizon {self.policy_inference_result.shape[0]}")
            
        cmd_msg = datatypes.RobotCmd()
        cmd_msg.stamp = time.time_ns()
        cmd_msg.mode = [self.config.motor_mode for _ in range(self.config.motor_number)]
        cmd_msg.Kp = [self.config.motor_Kp for _ in range(self.config.motor_number)]
        cmd_msg.Kd = [self.config.motor_Kd for _ in range(self.config.motor_number)]
        cmd_msg.dq = [self.config.motor_dp for _ in range(self.config.motor_number)]
        cmd_msg.tau = [self.config.motor_tau for _ in range(self.config.motor_number)]
        cmd_msg.motor_names = [f"motor_{i}" for i in range(self.config.motor_number)]
        current_action = self.policy_inference_result[step]
        joint_positions = [0.0, 0.0] + current_action.tolist()
        if len(joint_positions) != self.config.motor_number:
            raise ValueError(f"Expected {self.config.motor_number} motor values, but got {len(joint_positions)}")
        cmd_msg.q = joint_positions
        
        return cmd_msg

class Tron2:
    def __init__(self, config: RobotConfig):
        self.config = config
        self.robot = Robot(RobotType.Tron2)
        try:
            self.robot.init(config.ip_address)
            logging.info(f"机器人控制端口已连接 at {config.ip_address}")
        except Exception as e:
            logging.error(f"机器人控制端口连接失败: {e}")
            sys.exit(1)
            
        self.motor_number = 16 
        self.control_rate = Rate(config.control_rate)
        logging.info("机器人控制实例创建成功！")
        
    def get_state(self) -> datatypes.RobotState | None:
        try:
            with Client(SERVER_ADDRESS, authkey=SERVER_AUTH_KEY) as conn:
                if conn.poll(timeout=1.0):
                    state = conn.recv()
                    return state
                else:
                    logging.warning("连接到数据服务器超时，未收到数据。")
                    return None
        except Exception as e:
            logging.error(f"从数据服务器获取状态失败: {e}")
            return None
    
    def control(self, double_arm_msg: DoubleArmMsg):
        try:
            for cmd_msg in double_arm_msg:
                self.robot.publishRobotCmd(cmd_msg)
                self.control_rate.sleep()
        except Exception as e:
            logging.error(f"发送控制指令失败: {e}")
    
    def control_single_step(self, double_arm_msg: DoubleArmMsg, step: int = 0):
        try:
            cmd_msg = double_arm_msg.get_single_cmd(step)
            self.robot.publishRobotCmd(cmd_msg)
            # 在单步控制中也加入一个小的延时，确保指令有时间发送
            time.sleep(1.0 / self.config.control_rate)
        except Exception as e:
            logging.error(f"发送单步控制指令失败: {e}")


    def set_robot_light(self, light_effect: datatypes.LightEffect):
        self.robot.setRobotLightEffect(light_effect)