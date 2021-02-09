#!/usr/bin/env python 
import rospy
import math
import matplotlib.pyplot as plt
from rospy.rostime import Duration
from tf.transformations import euler_from_quaternion, quaternion_from_euler
from geometry_msgs.msg import Twist
from nav_msgs.msg import Odometry
from formation.msg import arrive

class go_to_Goal:
    def __init__(self):
        #initialization
        self.follow = Twist()
        self.follower1 = Twist()
        self.follower2 = Twist()
        self.arrive = arrive()
        self.rate = rospy.Rate(10)
        self.sleeper = rospy.Rate(5)
        self.x, self.y, self.z, self.a1 = 0, 0, 0, 0
        self.vel_1_linear, self.vel_1_angular, self.vel_2_linear, self.vel_2_angular = 0, 0, 0, 0

        #All the parameter
        self.name = rospy.get_param('~turtle')
        self.others1 = rospy.get_param('~other_turtle1')
        self.others2 = rospy.get_param('~other_turtle2')
        self.offset = rospy.get_param('~offset')

        #All the publisher
        self.pub_vel = rospy.Publisher('/%s/cmd_vel' % self.name, Twist, queue_size=1)
        self.pub_arrive = rospy.Publisher('%s_arrive' % self.name, arrive, queue_size=1)

        #All the subscriber
        self.turtle = rospy.Subscriber('/%s/odom' % self.name, Odometry, self.turtle_odom)
        self.other_turtle1 = rospy.Subscriber('/%s/cmd_vel' % self.others1, Twist, self.turtle_vel_1)
        self.other_turtle2 = rospy.Subscriber('/%s/cmd_vel' % self.others2, Twist, self.turtle_vel_2)
        
        #generate trajectory
        self.traj = self.traj_trans(3, self.offset, 5)
        self.log = []

        while not rospy.is_shutdown():
            for i in range(len(self.traj)):
                point = self.traj[i]
                if self.go_to_goal(point[0], point[1]):
                    
                    #wait until all the robots arrive at the waypoints
                    while (self.vel_1_linear != 0) or (self.vel_2_linear != 0) or (self.vel_1_angular != 0) or (self.vel_2_angular != 0):
                        self.follow.linear.x = 0
                        self.follow.angular.z = 0
                        self.pub_vel.publish(self.follow)
                        self.rate.sleep()

                    #plot the error    
                    plt.plot(self.log[1:])
                    plt.legend(['e_distance','e_angle'])
                    plt.savefig('/home/jack/catkin_ws/src/formation/error_plot/%spath_data.png' % self.name)
                    continue

                else:
                    #go back to the last waypoint if the robot fail to arrive at this waypoint
                    print ('invalid goal, return to last point')
                    if self.go_to_goal(self.traj[i-1][0],self.traj[i-1][1]):
                        continue

            self.follow.linear.x = 0
            self.follow.angular.z = 0
            self.pub = rospy.Publisher('/%s/cmd_vel' % self.name, Twist, queue_size=1)
            self.pub_vel.publish(self.follow)
            break  

    def turtle_odom(self, msg):
        self.msg1 = msg
        turtle1_position = self.msg1.pose.pose.position
        turtle1_orientation = self.msg1.pose.pose.orientation
        self.x = turtle1_position.x
        self.y = turtle1_position.y
        self.z = turtle1_position.z
        turtle1_orientation_list = [turtle1_orientation.x, turtle1_orientation.y, turtle1_orientation.z, turtle1_orientation.w]
        (roll, pitch, yaw) = euler_from_quaternion(turtle1_orientation_list)
        self.a1 = yaw

    def traj_trans(self, length, offset, num):
        dir = 1
        ans = [[0, offset]]
        for i in range(1, num):
            x = ans[-1][0]
            y = ans[-1][1]
            ans.pop(-1)
            ans.append([x - offset + dir*length, y])
            ans.append([x - offset + dir*length, y - 2 * dir * offset + 3])
            ans.append([0, ans[-1][1]])
            dir *= -1
        return ans

    def turtle_vel_1(self, msg):
        self.msg111 = msg
        self.vel_1_linear = self.msg111.linear.x
        self.vel_1_angular = self.msg111.angular.z
    
    def turtle_vel_2(self, msg):
        self.msg222 = msg
        self.vel_2_linear = self.msg222.linear.x
        self.vel_2_angular = self.msg222.angular.z

    def angle_trans(self, angle):
        #calculate the correct difference between two angles
        self.angle = angle
        while self.angle > math.pi:
            self.angle -= 2*math.pi
        while self.angle < -math.pi:
            self.angle += 2*math.pi
        return self.angle

    def go_to_goal(self, x_goal, y_goal):
        mission_time_begin = rospy.Time.now()
        self.arrive = False
        self.pub_arrive.publish(self.arrive)

        #PID parameters
        K_angular = [4, 1, 4]
        K_linear = [4, 0.1, 3]
        I = 0 

        desired_angle_goal, angle = 0, 0
                
        I_linear = 0
        I_angular = 0

        while not (self.arrive):

            desired_angle_goal = math.atan2(y_goal - self.y, x_goal - self.x)
            angle_0 = desired_angle_goal - self.a1
            angle_0 = self.angle_trans(angle_0)
            distance_0 = abs(math.sqrt(((x_goal - self.x) ** 2) + ((y_goal - self.y) ** 2)))
            time_begin = rospy.Time.now()
            self.rate.sleep()
            time_end = rospy.Time.now()
            duration = (time_end - time_begin).to_sec()
            if duration == 0:
                continue
            desired_angle_goal = math.atan2(y_goal - self.y, x_goal - self.x)
            angle = desired_angle_goal - self.a1
            angle = self.angle_trans(angle)
            distance = abs(math.sqrt(((x_goal - self.x) ** 2) + ((y_goal - self.y) ** 2)))

            #angular PID and linear PID
            I_angular =  I_angular + K_angular[1] * duration * (angle+angle_0)/2

            I_linear = I_linear + K_linear[1] * duration * (distance+distance_0)/2

            angular_speed =  (angle * K_angular[0] + I_angular + K_angular[2] * (angle-angle_0)/duration)
           
            linear_speed = distance * K_linear[0] + I_linear + K_linear[2] * (distance-distance_0)/duration

            #angular speed and linear speed limitation
            if linear_speed > 0.3:
                linear_speed = 0.3
            if angular_speed > 0.1:
                angular_speed = 0.1
            if angular_speed < -0.1:
                angular_speed = -0.1

            self.follow.linear.x = linear_speed
            self.follow.angular.z = angular_speed
            self.pub_vel.publish(self.follow)
            self.log.append([distance,angle])
        
            if (distance < 0.1):
                self.follow.linear.x = 0
                self.follow.angular.z = 0
                self.pub_vel.publish(self.follow)
                self.rate.sleep()
                desired_angle_goal = math.atan2(y_goal - self.y, x_goal - self.x)
                self.arrive = True
                self.pub_arrive.publish(self.arrive)
                print(self.name)
                print(self.arrive)
                print('   ')

        #After arriving at a waypoint, turn the robot until it faces the next waypoint       
        while (abs(angle) > 0.01):
            print(self.name)
            print('fuck')
            print('   ')
            desired_angle_goal = math.atan2(y_goal - self.y, x_goal - self.x)
            angle_0 = desired_angle_goal - self.a1
            time_begin = rospy.Time.now()
            self.rate.sleep()
            time_end = rospy.Time.now()
            duration = (time_end - time_begin).to_sec()
            desired_angle_goal = math.atan2(y_goal - self.y, x_goal - self.x)
            angle = desired_angle_goal - self.a1
            angle = self.angle_trans(angle)
            if duration == 0:
                continue
            
            I = I + K_angular[1] * duration * (angle+angle_0)/2

            angular_speed = (angle * K_angular[0] + I + K_angular[2] * (angle-angle_0)/duration)
            
            linear_speed = 0
            if angular_speed > 0.2:
                angular_speed = 0.2
            if angular_speed < -0.2:
                angular_speed = -0.2

            self.follow.linear.x = linear_speed
            self.follow.angular.z = angular_speed
            self.pub_vel.publish(self.follow) 

        if (rospy.Time.now() - mission_time_begin).to_sec() > 60:
            return False

        return True

if __name__ == '__main__':

    rospy.init_node('turtlesim_motion_pose', anonymous=True)
    try:
        f = go_to_Goal()

    except rospy.ROSInterruptException:
        rospy.loginfo("node terminated.")