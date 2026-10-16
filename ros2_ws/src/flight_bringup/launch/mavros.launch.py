from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.substitutions import LaunchConfiguration, PathJoinSubstitution
from launch_ros.substitutions import FindPackageShare
from launch_xml.launch_description_sources import XMLLaunchDescriptionSource


def generate_launch_description():
    mavros_launch = PathJoinSubstitution([
        FindPackageShare('mavros'), 'launch', 'px4.launch',
    ])

    return LaunchDescription([
        DeclareLaunchArgument(
            'fcu_url',
            default_value='udp://0.0.0.0:14541@',
            description='MAVLink connection to the flight controller',
        ),
        DeclareLaunchArgument(
            'gcs_url',
            default_value='',
            description='Optional MAVLink connection to a ground station',
        ),
        DeclareLaunchArgument('tgt_system', default_value='1'),
        DeclareLaunchArgument('tgt_component', default_value='1'),

        IncludeLaunchDescription(
            XMLLaunchDescriptionSource(mavros_launch),
            launch_arguments={
                'fcu_url': LaunchConfiguration('fcu_url'),
                'gcs_url': LaunchConfiguration('gcs_url'),
                'tgt_system': LaunchConfiguration('tgt_system'),
                'tgt_component': LaunchConfiguration('tgt_component'),
                'namespace': '',
            }.items(),
        ),
    ])