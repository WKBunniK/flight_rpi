from setuptools import find_packages, setup

package_name = 'flight_bridge'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='flight',
    maintainer_email='miu.miu@miu.miu',
    description='TODO: Package description',
    license='TODO: License declaration',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'vins_to_vision_pose = flight_bridge.vins_to_vision_pose:main',
            'send_gps_odometry = flight_bridge.send_gps_odometry:main',
            'set_message_interval = flight_bridge.set_message_interval:main',
        ],
    },
)
