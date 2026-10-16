from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.conditions import IfCondition
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    params_file = LaunchConfiguration('params_file')
    default_params = PathJoinSubstitution([
        FindPackageShare('flight_bringup'), 'config', 'bridges.yaml',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'params_file',
            default_value=default_params,
            description='YAML file with bridge node parameters',
        ),
        DeclareLaunchArgument('start_vision_pose', default_value='true'),
        DeclareLaunchArgument('start_hil_gps', default_value='true'),
        DeclareLaunchArgument('configure_streams', default_value='false'),

        Node(
            package='flight_bridge',
            executable='vins_to_vision_pose',
            name='vins_to_vision_pose',
            output='screen',
            parameters=[params_file],
            condition=IfCondition(LaunchConfiguration('start_vision_pose')),
        ),
        Node(
            package='flight_bridge',
            executable='send_gps_odometry',
            name='vins_to_hil_gps',
            output='screen',
            parameters=[params_file],
            condition=IfCondition(LaunchConfiguration('start_hil_gps')),
        ),
        Node(
            package='flight_bridge',
            executable='set_message_interval',
            name='set_message_interval',
            output='screen',
            parameters=[params_file],
            condition=IfCondition(LaunchConfiguration('configure_streams')),
        ),
    ])