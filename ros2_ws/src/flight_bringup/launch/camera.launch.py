from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.actions import Node
from launch_ros.substitutions import FindPackageShare


def generate_launch_description():
    camera_params = LaunchConfiguration('camera_params_file')

    return LaunchDescription([
        DeclareLaunchArgument(
            'camera_params_file',
            default_value=PathJoinSubstitution([
                FindPackageShare('flight_bringup'), 'config', 'camera.yaml',
            ]),
            description='USB camera parameters',
        ),
        DeclareLaunchArgument('start_camera', default_value='true'),
        DeclareLaunchArgument('start_image_proc', default_value='false'),

        Node(
            package='usb_cam',
            executable='usb_cam_node_exe',
            namespace='usb_cam',
            name='camera',
            parameters=[camera_params],
            output='screen',
            condition=IfCondition(LaunchConfiguration('start_camera')),
        ),

        IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                PathJoinSubstitution([
                    FindPackageShare('image_proc'),
                    'launch',
                    'image_proc.launch.py',
                ])
            ),
            launch_arguments={'namespace': 'usb_cam'}.items(),
            condition=IfCondition(LaunchConfiguration('start_image_proc')),
        ),
    ])