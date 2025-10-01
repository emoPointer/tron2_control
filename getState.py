# 文件名: getState_server.py
import sys
import time
import threading
from functools import partial
from multiprocessing.connection import Listener

import limxsdk.robot.Robot as Robot
import limxsdk.robot.RobotType as RobotType
import limxsdk.datatypes as datatypes
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - [SERVER] - %(levelname)s - %(message)s')

# --- 全局变量，用于在线程间共享最新状态 ---
LATEST_ROBOT_STATE = None
STATE_LOCK = threading.Lock()
ADDRESS = ('localhost', 6001) # 服务器监听的地址和端口
AUTH_KEY = b'tron2_secret_key' # 一个简单的认证密钥

class RobotReceiver:
    def robotStateCallback(self, robot_state: datatypes.RobotState):
        """回调函数：获取状态并存入全局变量"""
        global LATEST_ROBOT_STATE
        with STATE_LOCK:
            LATEST_ROBOT_STATE = robot_state
        # 为了确认回调在工作，我们可以每秒打印一次时间戳
        # if int(time.time()) % 2 == 0: 
        #    logging.info(f"Callback received state with stamp: {robot_state.stamp}")


def run_robot_subscription(robot_ip):
    """负责连接机器人并订阅状态"""
    robot = Robot(RobotType.Tron2)
    logging.info(f"正在连接机器人 at {robot_ip}...")
    if not robot.init(robot_ip):
        logging.error("机器人初始化失败！")
        sys.exit(1)
    
    logging.info("机器人连接成功！")
    
    receiver = RobotReceiver()
    robotStateCallback = partial(receiver.robotStateCallback)
    robot.subscribeRobotState(robotStateCallback)
    logging.info("状态订阅已启动，服务准备就绪。")
    
    # 让这个线程永远运行下去，以保持订阅活跃
    while True:
        time.sleep(10)

def main():
    robot_ip = "10.192.1.2"
    if len(sys.argv) > 1:
        robot_ip = sys.argv[1]

    # 在一个独立的后台线程中运行机器人订阅逻辑
    # 这样主线程就不会被阻塞，可以专心处理网络请求
    robot_thread = threading.Thread(target=run_robot_subscription, args=(robot_ip,), daemon=True)
    robot_thread.start()

    # 在主线程中运行网络服务器
    logging.info(f"数据服务器正在监听 {ADDRESS}...")
    listener = Listener(ADDRESS, authkey=AUTH_KEY)
    
    while True:
        try:
            conn = listener.accept()
            logging.info(f"接收到来自 {listener.last_accepted} 的连接")
            
            with STATE_LOCK:
                # 发送最新的机器人状态给客户端
                conn.send(LATEST_ROBOT_STATE)
                
            conn.close()
        except Exception as e:
            logging.error(f"服务器遇到错误: {e}")
            break
            
    listener.close()
    logging.info("服务器已关闭。")

if __name__ == '__main__':
    main()