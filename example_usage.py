import time
import numpy as np
from tron2_control import RobotConfig, DoubleArmMsg, Tron2 
import logging

def test_double_arm_msg():
    """测试DoubleArmMsg类的功能，并打印更多信息"""
    print("\n=== 测试 DoubleArmMsg 类 ===")
    config = RobotConfig(motor_number=16, action_dim=14, control_horizon=10)
    policy_inference_result = np.arange(140).reshape(10, 14) / 10.0
    
    print(f"策略推理结果 shape: {policy_inference_result.shape}")
    
    try:
        double_arm_msg = DoubleArmMsg(config, policy_inference_result)
        print("✅ DoubleArmMsg 创建成功")
        
        # 打印一个生成的消息样本
        sample_cmd = double_arm_msg.get_single_cmd(0)
        print("\n--- 生成的指令样本 (Step 0) ---")
        print(f"  stamp: {sample_cmd.stamp}")
        print(f"  mode: {sample_cmd.mode[:4]}...")
        print(f"  q (前4个关节): {[f'{x:.2f}' for x in sample_cmd.q[:4]]}...")
        print(f"  dq (前4个关节): {sample_cmd.dq[:4]}...")
        print(f"  tau (前4个关节): {sample_cmd.tau[:4]}...")
        print("✅ 样本生成成功")
            
    except Exception as e:
        print(f"❌ DoubleArmMsg测试失败: {e}")
        import traceback
        traceback.print_exc()

def test_robot_connection():
    """测试机器人连接和状态读取"""
    print("\n=== 测试机器人连接 ===")
    config = RobotConfig()
    
    try:
        print("正在尝试连接机器人...")
        robot = Tron2(config)
        print("✅ 机器人连接成功!")
        
        print(f"\n--- 机器人信息 ---")
        print(f"IP地址: {config.ip_address}")
        print(f"配置电机数量: {config.motor_number}")
        # 在新的IPC模式下，Tron2类可能不知道实际电机数，这里可以注释掉或硬编码
        # print(f"实际电机数量: {robot.motor_number}")
        
        return robot
        
    except Exception as e:
        print(f"❌ 机器人连接失败: {e}")
        return None

def test_robot_state_monitoring(robot, duration=3):
    """测试机器人状态监控，打印更详细的信息"""
    if robot is None:
        return
    print(f"\n=== 测试状态监控 (持续获取 {duration} 秒) ===")
    try:
        print("将在循环中主动获取并打印详细状态...")
        start_time = time.time()
        while (time.time() - start_time) < duration:
            current_state = robot.get_state()
            if current_state:
                print("\n--- 收到新的机器人状态 ---")
                print(f"  时间戳 (stamp): {current_state.stamp}")
                # 使用 numpy 格式化输出，更美观
                np.set_printoptions(precision=3, suppress=True)
                print(f"  关节角度 q (前4): {np.array(current_state.q[:4])}")
                print(f"  关节速度 dq (前4): {np.array(current_state.dq[:4])}")
                print(f"  关节力矩 tau (前4): {np.array(current_state.tau[:4])}")
            else:
                print("正在等待第一个状态数据...")
            
            time.sleep(0.1) # 每秒获取一次，避免刷屏
        
        print("\n✅ 状态监控测试完成")
        
    except Exception as e:
        print(f"\n❌ 状态监控测试失败: {e}")

def test_safe_control_simulation(robot):
    """测试安全的控制模拟，并预览指令"""
    if robot is None:
        return
        
    print(f"\n=== 测试安全控制模拟 ===")
    config = RobotConfig(action_dim=14, control_horizon=2)
    small_actions = np.array([[0.01] * 14, [0.02] * 14])
    
    try:
        double_arm_msg = DoubleArmMsg(config, small_actions)
        print("✅ DoubleArmMsg 创建成功")
        
        # 预览将要发送的第一条指令
        cmd_to_send = double_arm_msg.get_single_cmd(0)
        print("\n--- 将要发送的指令预览 (Step 0) ---")
        np.set_printoptions(precision=3, suppress=True)
        print(f"  q (关节角度): {np.array(cmd_to_send.q)}")
        print(f"  Kp: {cmd_to_send.Kp[0]}")
        print(f"  Kd: {cmd_to_send.Kd[0]}")
        
        user_input = input("\n是否发送安全测试命令到机器人？(y/N): ")
        if user_input.lower() == 'y':
            print("发送测试命令...")
            robot.control(double_arm_msg)
            print("✅ 控制命令发送成功！")
        else:
            print("⚠️ 跳过实际控制发送")
        
    except Exception as e:
        print(f"❌ 控制模拟测试失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    """主执行函数，采用稳定的对象生命周期管理"""
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
    
    print("🤖 Tron2 控制系统功能测试")
    print("=" * 50)
    
    try:
        test_double_arm_msg()
        robot = test_robot_connection()
        
        if robot is not None:
            test_robot_state_monitoring(robot, duration=3)
            test_safe_control_simulation(robot)
            
            print("\n=== 进入持续状态监控模式 ===")
            print("按 Ctrl+C 退出程序")
            
            while True:
                state = robot.get_state()
                
                if state:
                    print("\n--- 收到新的机器人状态 ---")
                    print(f"  时间戳 (stamp): {state.stamp}")
                    np.set_printoptions(precision=3, suppress=True)
                    print(f"  关节角度 q (前4): {np.array(state.q[:4])}")
                    print(f"  关节速度 dq (前4): {np.array(state.dq[:4])}")
                    print(f"  关节力矩 tau (前4): {np.array(state.tau[:4])}")
                else:
                    print(f"\r正在等待数据服务器响应...", end="")

                time.sleep(0.5)
        else:
            print("\n❌ 无法连接到机器人，只完成了离线测试")
            
    except KeyboardInterrupt:
        print("\n\n程序被用户中断")
    except Exception as e:
        logging.error(f"测试过程中发生错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        print("\n✅ 所有测试完成")

if __name__ == "__main__":
    main()