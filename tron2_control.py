import sys
import time
import numpy
import pyrallis
from dataclasses import dataclass, field
import logging
import limxsdk.robot.Rate as Rate
import limxsdk.robot.Robot as Robot
import limxsdk.robot.RobotType as RobotType
import limxsdk.datatypes as datatypes

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class RobotConfig:
    ip_address: str = "10.192.1.2"
    motor_number: int = 16  # 2+7+7
    control_rate: int = 500
    motor_Kp: float = 1.0
    motor_Kd: float = 1.0
    motor_dp: float = 0.1
    motor_tau: float = 10

class DoubleArmMsg(datatypes.RobotCmd):
    def __init__(self, config: RobotConfig, policy_inference_result: numpy.ndarray):  # shape of policy_inference_result: (action_horizon, action_dim)
        super().__init__()
        self.stamp = time.time_ns()
        self.mode = [1.0 for _ in range(config.motor_number)]
        self.Kp = [config.motor_Kp for _ in range(config.motor_number)]
        self.Kd = [config.motor_Kd for _ in range(config.motor_number)]
        self.dq = [config.motor_dp for _ in range(config.motor_number)]    # velocity
        self.tau = [config.motor_tau for _ in range(config.motor_number)]   # torque
        self.q = policy_inference_result.tolist()  # joint position TODO: consider action_horizon and front 2 dim

class Tron2:
    def __init__(self, config: RobotConfig):
        self.robot = Robot(RobotType.Tron2)
        try:
            self.robot.init(config.ip_address)
            logging.info(f"Connected to robot at {config.ip_address}")
        except Exception as e:
            logging.error(f"Failed to connect to robot at {config.ip_address}: {e}")
            sys.exit(1)
        self.motor_number = self.robot.getMotorNumber()
        if self.motor_number != config.motor_number:
            logging.error(f"Motor number mismatch: expected {config.motor_number}, got {self.motor_number}")
            sys.exit(1)
        self.joint_limit = self.robot.getJointLimit()
        self.joint_offset = self.robot.getJointOffset()
        self.control_rate = Rate(config.control_rate)

    def control(self, DoubleArmMsg: DoubleArmMsg):
        """
        Send control commands to the robot.
        :param DoubleArmMsg: An instance of DoubleArmMsg containing control commands.
        """
        try:
            self.robot.publishRobotCmd(DoubleArmMsg)    # TODO: not right RobotCmd
            self.control_rate.sleep()
        except Exception as e:
            logging.error(f"Failed to send control command: {e}")

    def robotStateCallback(self, robot_state: datatypes.RobotState):
        print("\n------\nrobot_state:" + \
              "\n  stamp: " + str(robot_state.stamp) + \
              "\n  tau: " + str(robot_state.tau) + \
              "\n  q: " + str(robot_state.q) + \
              "\n  dq: " + str(robot_state.dq))
        
    def get_state(self):
        """
        Subscribe to robot state updates.
        """
        try:
            self.robot.subscribeRobotState(self.robotStateCallback) # TODO: partial?
            # logging.info("Subscribed to robot state updates.")
        except Exception as e:
            logging.error(f"Failed to subscribe to robot state updates: {e}")

    def diagnosticValueCallback(self, diagnostic_value: datatypes.DiagnosticValue):
        print("\n------\ndiagnostic_value:" + \
              "\n  stamp: " + str(diagnostic_value.stamp) + \
              "\n  name: " + diagnostic_value.name + \
              "\n  level: " + str(diagnostic_value.level) + \
              "\n  code: " + str(diagnostic_value.code) + \
              "\n  message: " + diagnostic_value.message)

    def get_diagnostic_value(self):
        """
        Get the diagnostic value from the robot.
        """
        try:
            return self.robot.subscribeDiagnosticValue(self.diagnosticValueCallback)
        except Exception as e:
            logging.error(f"Failed to get diagnostic value: {e}")

    def set_robot_light(self, light_effect: datatypes.LightEffect):
        self.robot.setRobotLightEffect(light_effect)

