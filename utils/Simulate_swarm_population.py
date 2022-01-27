"""
Loading and testing
"""
import copy
import itertools
import multiprocessing
from functools import partial
import signal
import sys
from multiprocessing import shared_memory, Process
from typing import AnyStr
from isaacgym import gymapi
from isaacgym import gymutil
from scipy.spatial.transform import Rotation as R

import numpy as np
from numpy.random import default_rng

from .calculate_fitness import FitnessCalculator  # Fitness calculator class, all functions are implemented as different
# methods of this class
from .sensors import Sensors  # Sensor class, all types of sensors are are implemented as different
# methods of this class
from .plot_swarm import swarm_plotter  # Plotter class, to plot positions and headings of the swarm agents on the
# gradient map

from .Individual import Individual
import time


def calc_vel_targets(controllers, states):
    velocity_target = controllers.velocity_commands(np.array(states))  # assumed to be in format of [u,w]
    n_l = ((velocity_target[0]+0.025) - (velocity_target[1] / 2) * 0.085) / 0.021
    n_r = ((velocity_target[0]+0.025) + (velocity_target[1] / 2) * 0.085) / 0.021
    return [n_l, n_r]


def simulate_swarm_population(life_timeout: float, individuals: list, headless: bool, objectives: list) -> np.array:
    """
    Simulate the robot in isaac gym
    :param individuals: list of robot phenotypes for every member of the swarm
    :param life_timeout: how long should the robot live
    :param headless: Start UI for debugging
    :return: fitness of the individual
    """
    # DEVICE = 'cuda' if torch.cuda.is_available() else 'cpu'
    # print(DEVICE)

    if_random_start = True  # omni, k_nearest, 4dir

    # %% Initialize gym
    global gym
    gym = gymapi.acquire_gym()

    # Parse arguments
    args = gymutil.parse_arguments(description="Loading and testing")

    # configure sim
    sim_params = gymapi.SimParams()
    sim_params.dt = 0.1
    sim_params.substeps = 2

    # defining axis of rotation!
    sim_params.up_axis = gymapi.UP_AXIS_Z
    sim_params.gravity = gymapi.Vec3(0.0, 0.0, -9.81)

    if args.physics_engine == gymapi.SIM_FLEX:
        sim_params.flex.solver_type = 5
        sim_params.flex.num_outer_iterations = 4
        sim_params.flex.num_inner_iterations = 15
        sim_params.flex.relaxation = 0.75
        sim_params.flex.warm_start = 0.8
    elif args.physics_engine == gymapi.SIM_PHYSX:
        sim_params.physx.solver_type = 1
        sim_params.physx.num_position_iterations = 4
        sim_params.physx.num_velocity_iterations = 1
        sim_params.physx.num_threads = args.num_threads
        sim_params.physx.use_gpu = True

    sim = gym.create_sim(args.compute_device_id, args.graphics_device_id, args.physics_engine, sim_params)

    if sim is None:
        print("*** Failed to create sim")
        quit()

    # %% Initialize environment
    # print("Initialize environment")
    # Add ground plane
    plane_params = gymapi.PlaneParams()
    plane_params.normal = gymapi.Vec3(0, 0, 1)  # z-up!
    plane_params.distance = 0
    plane_params.static_friction = 0
    plane_params.dynamic_friction = 0
    gym.add_ground(sim, plane_params)

    asset_options = gymapi.AssetOptions()
    asset_options.fix_base_link = False
    asset_options.flip_visual_attachments = True
    asset_options.armature = 0.0001

    # Set up the env grid
    num_envs = len(individuals)
    spacing = 30.0
    env_lower = gymapi.Vec3(0.0, 0.0, 0.0)
    env_upper = gymapi.Vec3(spacing, spacing, spacing)

    # Some common handles for later use
    desired_movement = 10  # This values is required for the "movement" metric
    env_list = []
    robot_handles_list = []
    fitness_list = []
    sensor_list = []
    controllers = []
    num_robots = 14
    pool_obj = multiprocessing.Pool(num_robots)
    controller_list = []
    # calc_vel_targets_partial = partial(calc_vel_targets, controller)
    print("Creating %d environments" % num_envs)
    for i_env in range(num_envs):
        individual = individuals[i_env]
        controller_list.append(individual.controller)
        controller_type = individual.controller.controller_type
        # create env
        env = gym.create_env(sim, env_lower, env_upper, num_envs)
        env_list.append(env)
        # %% Initialize robot: Robobo
        # print("Initialize Robot")
        # Load robot asset
        asset_root = "./"
        robot_asset_file = individual.body

        robot_handles = []
        initial_positions = np.zeros((2, num_robots))  # Allocation to save initial positions of robots

        if if_random_start:
            flag = 0
            init_area = 3.0
            init_flag = 0
            init_failure_1 = 1
            rng = default_rng()
            iangle = 6.28 * rng.random()
            iy = 15 + 12 * (np.cos(iangle))
            ix = 15 + 12 * (np.sin(iangle))
            a_x = ix + (init_area / 2)
            b_x = ix - (init_area / 2)
            a_y = iy + (init_area / 2)
            b_y = iy - (init_area / 2)

            while init_failure_1 == 1 and init_flag == 0:
                ixs = a_x + (b_x - a_x) * rng.random(num_robots)
                iys = a_y + (b_y - a_y) * rng.random(num_robots)
                flag = 0

                for i in range(num_robots):
                    for j in range(num_robots):
                        if i != j and np.sqrt(np.square(ixs[i] - ixs[j]) + np.square(iys[i] - iys[j])) < 0.4:
                            init_failure_1 = 1
                            flag = 1
                        elif flag == 0:
                            init_failure_1 = 0

            ihs = 6.28 * rng.random(num_robots)

            pose = gymapi.Transform()
            pose.p = gymapi.Vec3(0, 0, 0.032)
            pose.r = gymapi.Quat(0, 0.0, 0.0, 0.707107)

            for i in range(num_robots):
                pose.p = gymapi.Vec3(ixs[i], iys[i], 0.033)
                initial_positions[0][i] = pose.p.x  # Save initial position x of i'th robot
                initial_positions[1][i] = pose.p.y  # Save initial position y of i'th robot

                ihs_i = R.from_euler('zyx', [ihs[i], 0.0, 0.0])
                ihs_i = ihs_i.as_quat()
                pose.r.x = ihs_i[0]
                pose.r.y = ihs_i[1]
                pose.r.z = ihs_i[2]
                pose.r.w = ihs_i[3]

                # print("Loading asset '%s' from '%s', #%i" % (robot_asset_file, asset_root, i))
                robot_asset = gym.load_asset(
                    sim, asset_root, robot_asset_file, asset_options)

                # add robot
                robot_handle = gym.create_actor(env, robot_asset, pose, f"robot_{i}", 0, 0)
                robot_handles.append(robot_handle)
        else:
            distance = 0.5
            rows = 4

            # place robots
            pose = gymapi.Transform()
            pose.p = gymapi.Vec3(0, 0, 0.032)
            pose.r = gymapi.Quat(0, 0.0, 0.0, 0.707107)
            for i in range(num_robots):
                pose.p = gymapi.Vec3(
                    (((i + 9) // 12 + i) % rows) * distance - (rows - 1) / 2 * distance,
                    (((i + 9) // 12 + i) // rows) * distance - (rows - 1) / 2 * distance,
                    0.033)
                initial_positions[0][i] = pose.p.x  # Save initial position x of i'th robot
                initial_positions[1][i] = pose.p.y  # Save initial position y of i'th robot

                # print("Loading asset '%s' from '%s', #%i" % (robot_asset_file, asset_root, i))
                robot_asset = gym.load_asset(
                    sim, asset_root, robot_asset_file, asset_options)

                # add robot
                robot_handle = gym.create_actor(env, robot_asset, pose, f"robot_{i}", 0, 0)
                robot_handles.append(robot_handle)
        robot_handles_list.append(robot_handles)

        # get joint limits and ranges for robot
        props = gym.get_actor_dof_properties(env, robot_handle)

        # Give a desired velocity to drive
        props["driveMode"].fill(gymapi.DOF_MODE_VEL)
        props["stiffness"].fill(0)
        props["damping"].fill(10)
        velocity_limits = props["velocity"]
        for i in range(num_robots):
            robot_handle = robot_handles[i]
            shape_props = gym.get_actor_rigid_shape_properties(env, robot_handle)
            shape_props[2].friction = 0
            shape_props[2].restitution = 1
            gym.set_actor_dof_properties(env, robot_handle, props)
            gym.set_actor_rigid_shape_properties(env, robot_handle, shape_props)

        positions = np.full([3, num_robots], 0.01)  # Allocation to save positions of all robots in a single matrix
        fitness_list.append(
            FitnessCalculator(num_robots, initial_positions, desired_movement))  # Fitness calculator init
        sensor_list.append(Sensors())  # Sensors init
    calc_vel_targets_partial = partial(calc_vel_targets, controllers)

    def update_robot(env, i_env , robot_handles, sensor_input_distance, sensor_input_heading, sensor_input_bearing=None,
                     own_headings=None,
                     sensor_input_grad=None):
        states = np.hstack(
            (sensor_input_distance, sensor_input_heading, sensor_input_grad.reshape((num_robots, 1)))).tolist()
        velocity_commands = pool_obj.starmap(calc_vel_targets,  zip(itertools.repeat(controller_list[i_env]), states))
        for ii in range(num_robots):
            gym.set_actor_dof_velocity_targets(env, robot_handles[ii], velocity_commands[ii])

    def get_pos_and_headings(env, robot_handles):
        headings = np.zeros((num_robots,))
        positions_x = np.zeros_like(headings)
        positions_y = np.zeros_like(headings)

        for i in range(num_robots):
            body_pose = gym.get_actor_rigid_body_states(env, robot_handles[i], gymapi.STATE_POS)["pose"][0]
            body_angle_mat = np.array(body_pose[1].tolist())
            r = R.from_quat(body_angle_mat)
            headings[i] = r.as_euler('zyx')[0]

            positions_x[i] = body_pose[0][0]
            positions_y[i] = body_pose[0][1]

        return (headings, positions_x, positions_y)

    t = 0
    timestep = 0  # Counter to save total time steps, required for final step of fitness value calculation
    fitness_mat = np.zeros((len(objectives), len(individuals)))
    # Create viewer
    viewer = None
    plot = False
    if not headless:
        viewer = gym.create_viewer(sim, gymapi.CameraProperties())
        cam_pos = gymapi.Vec3(-2 + ix, iy, 2)
        cam_target = gymapi.Vec3(ix, iy, 0.0)
        gym.viewer_camera_look_at(viewer, None, cam_pos, cam_target)

        if len(individuals) == 1:
            plotter = swarm_plotter()  # Plotter init
            plot = True

    # %% Simulate
    start = gym.get_sim_time(sim)
    while t <= life_timeout:
        # Every 0.01 seconds the velocity of the joints is set
        t = gym.get_sim_time(sim)

        if (gym.get_sim_time(sim) - start) > 0.095:
            timestep += 1  # Time step counter
            for i_env in range(num_envs):
                env = env_list[i_env]
                robot_handles = robot_handles_list[i_env]
                headings, positions[0], positions[1] = get_pos_and_headings(env,
                                                                            robot_handles)  # Update positions and headings of all robots
                if controller_type == "omni":
                    distance_sensor_outputs, bearing_sensor_outputs = sensor_list[i_env].omni_dir_sensor(positions,
                                                                                                         headings)  # The values recorded by on-board
                    heading_sensor_outputs = sensor_list[i_env].heading_sensor_ae(positions,
                                                                                  headings)  # The values recorded by on-board
                    update_robot(env, i_env, robot_handles, distance_sensor_outputs, heading_sensor_outputs,
                                 bearing_sensor_outputs, headings)
                elif controller_type == "k_nearest":
                    distance_sensor_outputs, bearing_sensor_outputs = sensor_list[i_env].k_nearest_sensor(positions,
                                                                                                          headings)  # The values recorded by on-board
                    heading_sensor_outputs = sensor_list[i_env].heading_sensor_ae(positions,
                                                                                  headings)  # The values recorded by on-board
                    update_robot(env, i_env, robot_handles, distance_sensor_outputs, heading_sensor_outputs,
                                 bearing_sensor_outputs, headings)
                elif controller_type == "4dir":
                    distance_sensor_outputs = sensor_list[i_env].four_dir_sensor(positions, headings)
                    heading_sensor_outputs = sensor_list[i_env].heading_sensor_ae(positions,
                                                                                  headings)  # The values recorded by on-board
                    grad_sensor_outputs = sensor_list[i_env].grad_sensor(positions)
                    update_robot(env, i_env, robot_handles, distance_sensor_outputs, heading_sensor_outputs,
                                 own_headings=headings,
                                 sensor_input_grad=grad_sensor_outputs)
                elif controller_type == "NN":
                    distance_sensor_outputs = sensor_list[i_env].four_dir_sensor(positions, headings)
                    heading_sensor_outputs = sensor_list[i_env].heading_sensor_4dir(
                        headings)  # The values recorded by on-board
                    grad_sensor_outputs = sensor_list[i_env].grad_sensor(positions)
                    update_robot(env, i_env, robot_handles, distance_sensor_outputs, heading_sensor_outputs,
                                 own_headings=headings,
                                 sensor_input_grad=grad_sensor_outputs)
                elif controller_type == "default":
                    distance_sensor_outputs = sensor_list[i_env].four_dir_sensor(positions, headings)
                    heading_sensor_outputs = sensor_list[i_env].heading_sensor_ae(positions,
                                                                                  headings)  # The values recorded by on-board
                    update_robot(env, i_env, robot_handles, distance_sensor_outputs, heading_sensor_outputs,
                                 own_headings=headings)
                else:
                    raise ValueError("Controller type not found")

                fitness_mat[:2, i_env] = fitness_list[i_env].calculate_cohesion_and_separation(
                    positions) / timestep  # Update fitness val
                fitness_mat[2, i_env] = fitness_list[i_env].calculate_alignment(
                    headings) / timestep  # Update fitness val
                fitness_mat[3, i_env] = fitness_list[i_env].calculate_movement(positions)  # Update fitness val
                fitness_mat[4, i_env] = fitness_list[i_env].calculate_grad(positions) / timestep
            if plot and round(t%1,2)==0:
                plotter.plot_swarm_quiver(positions, headings)
            start = gym.get_sim_time(sim)

        # Step the physics
        gym.simulate(sim)
        gym.fetch_results(sim, True)
        gym.step_graphics(sim)
        gym.draw_viewer(viewer, sim, False)

    gym.destroy_viewer(viewer)
    gym.destroy_sim(sim)

    # print("Cohesion is: ", fitness_coh_and_sep[0] / timestep)
    # print("Separation is: ", - fitness_coh_and_sep[1] / timestep)
    # print("Alignment is: ", fitness_alignment / timestep)
    # print("Movement is: ", fitness_movement)
    # fitnesses = np.array([fitness_coh_and_sep[0] / timestep,
    #                       fitness_coh_and_sep[1] / timestep,
    #                       fitness_alignment[0] / timestep,
    #                       fitness_movement[0],
    #                       fitness_gradient / timestep]).T

    binary_vector = objectives
    gen_fitnesses = np.dot(binary_vector, fitness_mat)

    # experiment_fitness = fitness_coh_and_sep[0] / timestep - fitness_coh_and_sep[
    #     1] / timestep + fitness_alignment / timestep + fitness_movement  # For the time average, divide by time step

    # Gradient only fitness??
    # experiment_fitness = fitness_gradient
    pool_obj.close()
    return gen_fitnesses


def simulate_swarm_with_restart_population(life_timeout: float, individuals: list, headless: bool,
                                           objectives: list) -> np.array:
    """
    Obtains the results for simulate_swarm() with forced gpu memory clearance for restarts.
    :param individuals: robot phenotype for every member of the swarm
    :param life_timeout: how long should the robot live
    :param headless: Start UI for debugging
    :return: fitness of the individual
    """
    result = np.array([0.0] * len(individuals), dtype=float)
    shared_mem = shared_memory.SharedMemory(create=True, size=result.nbytes)
    process = Process(target=_inner_simulator_multiple_process_population,
                      args=(life_timeout, individuals, headless, objectives, shared_mem.name))
    process.start()
    process.join()
    remote_result = np.ndarray((len(individuals),), dtype=float, buffer=shared_mem.buf)
    result[:] = remote_result[:]
    shared_mem.close()
    shared_mem.unlink()
    return result


def _inner_simulator_multiple_process_population(life_timeout: float, individuals: list, headless: bool,
                                                 objectives: list,
                                                 shared_mem_name: AnyStr) -> int:
    existing_shared_mem = shared_memory.SharedMemory(name=shared_mem_name)
    remote_result = np.ndarray((len(individuals),), dtype=float, buffer=existing_shared_mem.buf)
    try:
        fitness: np.array = simulate_swarm_population(life_timeout, individuals, headless, objectives)
        remote_result[:] = fitness
        existing_shared_mem.close()
        return 0
    except Exception as e:
        print(e)
        remote_result[:] = -np.inf
        existing_shared_mem.close()
        return -1
