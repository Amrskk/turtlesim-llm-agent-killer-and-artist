import rclpy
from rclpy.node import Node
from turtlesim.msg import Pose
from turtlesim.srv import TeleportAbsolute, SetPen, Kill
from geometry_msgs.msg import Twist
from std_msgs.msg import String
import math

try:
    from langchain_ollama import ChatOllama
except ImportError:
    ChatOllama = None

class TurtleAgent(Node):
    def __init__(self):
        super().__init__('turtle_agent_node')
        if ChatOllama is not None:
            self.llm = ChatOllama(model="qwen3", temperature=0)
        else:
            self.llm = None
            self.get_logger().warn('langchain_ollama not installed; using direct SHOOT fallback')
        self.player_pose = None
        self.enemies = {}
        self.subscribers = {}
        self.draw_state = None

        self.create_subscription(Pose, 'turtle1/pose', self.player_cb, 10)
        self.create_subscription(String, '/turtle1/llm_request', self.llm_request_cb, 10)
        self.cmd_pub = self.create_publisher(Twist, '/turtle1/cmd_vel', 10)
        
        self.kill_srv = self.create_client(Kill, 'kill')
        self.tele_srv = self.create_client(TeleportAbsolute, '/turtle1/teleport_absolute')
        self.pen_srv = self.create_client(SetPen, '/turtle1/set_pen')
        self._wait_for_services()

        self.create_timer(1.5, self.discover_enemies)
        self.create_timer(0.1, self.draw_loop)
        self.create_timer(0.1, self.motion_loop)
        self.create_timer(1.0, self.tactical_loop)

    def player_cb(self, msg):
        self.player_pose = msg

    def _wait_for_services(self):
        while not self.kill_srv.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('waiting for kill service...')
        while not self.tele_srv.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('waiting for teleport service...')
        while not self.pen_srv.wait_for_service(timeout_sec=1.0):
            self.get_logger().info('waiting for set_pen service...')

    def _normalize_angle(self, angle):
        return math.atan2(math.sin(angle), math.cos(angle))

    def _stop_motion(self):
        self.cmd_pub.publish(Twist())

    def _start_shape_drawing(self, shape):
        self.pen_srv.call_async(SetPen.Request(r=0, g=200, b=255, width=2, off=0))
        if shape == 'circle':
            self.draw_state = {
                'shape': 'circle',
                'ticks_left': 110,
                'linear_x': 1.3,
                'angular_z': 1.3,
            }
        else:
            sides = 4 if shape == 'square' else 3
            self.draw_state = {
                'shape': 'polygon',
                'side_count': sides,
                'side_index': 0,
                'forward_ticks': 14,
                'turn_ticks': 10,
                'phase': 'forward',
                'phase_ticks_left': 14,
                'linear_x': 1.6,
                'turn_rate': (2.0 * math.pi / sides) / (10 * 0.1),
            }

    def _shape_from_llm_request(self, user_text):
        if self.llm is None:
            lower = user_text.lower()
            if 'circle' in lower:
                return 'circle'
            if 'square' in lower:
                return 'square'
            if 'triangle' in lower:
                return 'triangle'
            if 'stop' in lower or 'cancel' in lower:
                return 'stop'
            return 'none'

        prompt = (
            'You are controlling turtlesim. '
            'Read the user request and answer with exactly one token: '
            'CIRCLE, SQUARE, TRIANGLE, STOP, or NONE.\n'
            f'User request: {user_text}'
        )
        try:
            response = self.llm.invoke(prompt)
            answer = str(getattr(response, 'content', response)).strip().upper()
        except Exception as exc:
            self.get_logger().warn(f'LLM request parse failed ({exc}); treating as NONE')
            return 'none'

        if 'CIRCLE' in answer:
            return 'circle'
        if 'SQUARE' in answer:
            return 'square'
        if 'TRIANGLE' in answer:
            return 'triangle'
        if 'STOP' in answer:
            return 'stop'
        return 'none'

    def llm_request_cb(self, msg):
        request_text = msg.data.strip()
        if not request_text:
            return

        shape = self._shape_from_llm_request(request_text)
        if shape == 'stop':
            self.draw_state = None
            self.pen_srv.call_async(SetPen.Request(r=0, g=0, b=0, width=1, off=1))
            self._stop_motion()
            self.get_logger().info('drawing canceled by request')
            return

        if shape in ('circle', 'square', 'triangle'):
            self._start_shape_drawing(shape)
            self.get_logger().info(f'LLM selected drawing: {shape}')
            return

        self.get_logger().info('LLM request did not map to a drawing action')

    def draw_loop(self):
        if not self.draw_state:
            return

        cmd = Twist()
        shape = self.draw_state['shape']
        if shape == 'circle':
            cmd.linear.x = self.draw_state['linear_x']
            cmd.angular.z = self.draw_state['angular_z']
            self.draw_state['ticks_left'] -= 1
            if self.draw_state['ticks_left'] <= 0:
                self.draw_state = None
                self.pen_srv.call_async(SetPen.Request(r=0, g=0, b=0, width=1, off=1))
                self._stop_motion()
                self.get_logger().info('circle drawing complete')
                return
        else:
            if self.draw_state['phase'] == 'forward':
                cmd.linear.x = self.draw_state['linear_x']
                cmd.angular.z = 0.0
            else:
                cmd.linear.x = 0.0
                cmd.angular.z = self.draw_state['turn_rate']

            self.draw_state['phase_ticks_left'] -= 1
            if self.draw_state['phase_ticks_left'] <= 0:
                if self.draw_state['phase'] == 'forward':
                    self.draw_state['phase'] = 'turn'
                    self.draw_state['phase_ticks_left'] = self.draw_state['turn_ticks']
                else:
                    self.draw_state['side_index'] += 1
                    if self.draw_state['side_index'] >= self.draw_state['side_count']:
                        finished_shape = 'square' if self.draw_state['side_count'] == 4 else 'triangle'
                        self.draw_state = None
                        self.pen_srv.call_async(SetPen.Request(r=0, g=0, b=0, width=1, off=1))
                        self._stop_motion()
                        self.get_logger().info(f'{finished_shape} drawing complete')
                        return
                    self.draw_state['phase'] = 'forward'
                    self.draw_state['phase_ticks_left'] = self.draw_state['forward_ticks']

        self.cmd_pub.publish(cmd)

    def _closest_enemy(self):
        if not self.player_pose or not self.enemies:
            return None, None, float('inf')

        closest_name = None
        closest_pose = None
        min_dist = float('inf')
        for name, pose in list(self.enemies.items()):
            dist = math.hypot(self.player_pose.x - pose.x, self.player_pose.y - pose.y)
            if dist < min_dist:
                min_dist = dist
                closest_name = name
                closest_pose = pose

        return closest_name, closest_pose, min_dist

    def discover_enemies(self):
        topic_list = self.get_topic_names_and_types()
        for name, _types in topic_list:
            if '/pose' in name and '/turtle1' not in name:
                turtle_name = name.split('/')[1]
                if turtle_name not in self.subscribers:
                    self.get_logger().info(f'new enemy detected: {turtle_name}')
                    self.subscribers[turtle_name] = self.create_subscription(
                        Pose, name, lambda msg, tn=turtle_name: self.enemy_cb(msg, tn), 10
                        )

    def enemy_cb(self, msg, name):
        self.enemies[name] = msg

    def motion_loop(self):
        if not self.player_pose:
            return

        if self.draw_state:
            return

        cmd = Twist()
        x, y, theta = self.player_pose.x, self.player_pose.y, self.player_pose.theta
        at_edge = x < 1.0 or x > 10.0 or y < 1.0 or y > 10.0

        target_name, target_pose, target_dist = self._closest_enemy()
        if target_name and target_pose:
            desired = math.atan2(target_pose.y - y, target_pose.x - x)
            err = self._normalize_angle(desired - theta)
            cmd.angular.z = max(-2.5, min(2.5, 4.0 * err))
            cmd.linear.x = 1.8 if abs(err) < 0.5 and target_dist > 2.5 else 0.6
        else:
            # Patrol in arcs; turn harder when near the arena boundary.
            cmd.linear.x = 1.8
            cmd.angular.z = 2.4 if at_edge else 0.8

        self.cmd_pub.publish(cmd)

    def tactical_loop(self):
        if not self.player_pose or not self.enemies:
            return

        if self.draw_state:
            return

        closest_name, closest_pose, min_dist = self._closest_enemy()
        if not closest_name or not closest_pose:
            return

        if min_dist < 4.0:
            if self.llm is None:
                response_text = 'SHOOT'
            else:
                prompt = f'Target {closest_name} is {min_dist:.2f}m away. Action: SHOOT or WAIT?'
                try:
                    response = self.llm.invoke(prompt)
                    response_text = str(getattr(response, 'content', response)).upper()
                except Exception as exc:
                    self.get_logger().warn(f'LLM unavailable ({exc}); defaulting to SHOOT')
                    response_text = 'SHOOT'
            if 'SHOOT' in response_text:
                self.fire_laser(closest_name, closest_pose)
                self.enemies.pop(closest_name, None)

    def fire_laser(self, name, target_pose):
        ox, oy, ot = self.player_pose.x, self.player_pose.y, self.player_pose.theta
        self.pen_srv.call_async(SetPen.Request(r=255, g=0, b=0, width=3, off=0))
        self.tele_srv.call_async(TeleportAbsolute.Request(x=target_pose.x, y=target_pose.y, theta=ot))
        self.kill_srv.call_async(Kill.Request(name=name))
        self.pen_srv.call_async(SetPen.Request(r=0, g=0, b=0, width=1, off=1))
        self.tele_srv.call_async(TeleportAbsolute.Request(x=ox, y=oy, theta=ot))
        self.get_logger().warn(f'Killed {name}')


def main(args=None):
    rclpy.init(args=args)
    node = TurtleAgent()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    node.destroy_node()
    rclpy.shutdown()

if __name__ == '__main__':
    main()