import math

import rclpy
from geographiclib.geodesic import Geodesic
from mavros_msgs.msg import HilGPS
from nav_msgs.msg import Odometry
from rclpy.executors import ExternalShutdownException
from rclpy.node import Node


def enu_to_lla(lat0, lon0, alt0, east, north, up):
    geod = Geodesic.WGS84
    g1 = geod.Direct(lat0, lon0, 0.0, north)
    g2 = geod.Direct(g1['lat2'], g1['lon2'], 90.0, east)
    return g2['lat2'], g2['lon2'], alt0 + up


def encode_velocity(value, signed=False):
    encoded = int(round(value * 100.0))
    lower, upper = (-32768, 32767) if signed else (0, 65534)
    if not lower <= encoded <= upper:
        raise ValueError(f'Velocity {value} m/s is outside the HIL_GPS range')
    return encoded


class VinsToHilGps(Node):
    def __init__(self):
        super().__init__('vins_to_hil_gps')

        defaults = {
            'input_topic': '/odometry',
            'output_topic': '/mavros/hil/gps',
            'origin_lat_deg': 56.097385,
            'origin_lon_deg': 35.887286,
            'origin_alt_m': 157.0,
            'yaw_offset_rad': 0.0,
            'fix_type': 3,
            'satellites_visible': 15,
            'eph': 30,
            'epv': 60,
            'gps_id': 0,
            'min_speed_for_cog_mps': 0.1,
        }
        self.params = {
            name: self.declare_parameter(name, value).value
            for name, value in defaults.items()
        }
        p = self.params

        numeric = (
            'origin_lat_deg', 'origin_lon_deg', 'origin_alt_m',
            'yaw_offset_rad', 'min_speed_for_cog_mps',
        )
        if not all(math.isfinite(p[name]) for name in numeric):
            raise ValueError('Origin, yaw offset and speed threshold must be finite')
        if not -90.0 <= p['origin_lat_deg'] <= 90.0:
            raise ValueError('origin_lat_deg must be in [-90, 90]')
        if not -180.0 <= p['origin_lon_deg'] <= 180.0:
            raise ValueError('origin_lon_deg must be in [-180, 180]')
        if p['min_speed_for_cog_mps'] < 0.0:
            raise ValueError('min_speed_for_cog_mps must be non-negative')

        limits = {
            'fix_type': 255, 'satellites_visible': 255,
            'eph': 65535, 'epv': 65535, 'gps_id': 255,
        }
        for name, upper in limits.items():
            if not 0 <= p[name] <= upper:
                raise ValueError(f'{name} must be in [0, {upper}]')

        self.cos_yaw = math.cos(p['yaw_offset_rad'])
        self.sin_yaw = math.sin(p['yaw_offset_rad'])

        self.publisher = self.create_publisher(HilGPS, p['output_topic'], 20)
        self.subscription = self.create_subscription(
            Odometry, p['input_topic'], self.on_odometry, 50
        )
        self.get_logger().info(
            f'Forwarding {self.subscription.topic_name} -> '
            f'{self.publisher.topic_name}'
        )

    def on_odometry(self, odom):
        position = odom.pose.pose.position
        velocity = odom.twist.twist.linear
        values = (
            position.x, position.y, position.z,
            velocity.x, velocity.y, velocity.z,
        )
        if not all(math.isfinite(value) for value in values):
            self.get_logger().error('Dropping odometry with non-finite values')
            return

        east = self.cos_yaw * position.x - self.sin_yaw * position.y
        north = self.sin_yaw * position.x + self.cos_yaw * position.y
        ve = self.cos_yaw * velocity.x - self.sin_yaw * velocity.y
        vn = self.sin_yaw * velocity.x + self.cos_yaw * velocity.y
        vd = -velocity.z
        ground_speed = math.hypot(vn, ve)
        p = self.params

        lat, lon, alt = enu_to_lla(
            p['origin_lat_deg'], p['origin_lon_deg'], p['origin_alt_m'],
            east, north, position.z,
        )

        out = HilGPS()
        out.header.stamp = odom.header.stamp
        out.geo.latitude = lat
        out.geo.longitude = lon
        out.geo.altitude = alt
        out.fix_type = p['fix_type']
        out.eph = p['eph']
        out.epv = p['epv']
        out.satellites_visible = p['satellites_visible']
        out.id = p['gps_id']
        out.yaw = 0

        try:
            out.vn = encode_velocity(vn, signed=True)
            out.ve = encode_velocity(ve, signed=True)
            out.vd = encode_velocity(vd, signed=True)
            out.vel = encode_velocity(ground_speed)
        except (ValueError, OverflowError) as error:
            self.get_logger().error(f'Dropping odometry: {error}')
            return

        if ground_speed > p['min_speed_for_cog_mps']:
            course_deg = math.degrees(math.atan2(ve, vn)) % 360.0
            out.cog = int(round(course_deg * 100.0)) % 36000
        else:
            out.cog = 65535

        self.publisher.publish(out)


def main(args=None):
    rclpy.init(args=args)
    node = VinsToHilGps()

    try:
        rclpy.spin(node)
    except (KeyboardInterrupt, ExternalShutdownException):
        pass
    finally:
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()


if __name__ == '__main__':
    main()