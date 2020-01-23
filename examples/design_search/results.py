from PIL import Image
import argparse
import ast
from design_search import *
import mcts
import numpy as np
import pandas as pd
import pyrobotdesign as rd
import tasks
from viewer import *

def make_robot_from_rule_sequence(rule_sequence, rules):
  graph = make_initial_graph()
  for r in rule_sequence:
    matches = rd.find_matches(rules[r].lhs, graph)
    if matches:
      graph = rd.apply_rule(rules[r], graph, matches[0])

  return build_normalized_robot(graph)

def get_robot_image(robot, task):
  sim = rd.BulletSimulation(task.time_step)
  task.add_terrain(sim)
  viewer = rd.GLFWViewer()
  if robot is not None:
    robot_init_pos, _ = presimulate(robot)
    # Rotate 180 degrees around the y axis, so the base points to the right
    sim.add_robot(robot, robot_init_pos, rd.Quaterniond(0.0, 0.0, 1.0, 0.0))
    robot_idx = sim.find_robot_index(robot)

    # Get robot position and bounds
    base_tf = np.zeros((4, 4), order='f')
    lower = np.zeros(3)
    upper = np.zeros(3)
    sim.get_link_transform(robot_idx, 0, base_tf)
    sim.get_robot_world_aabb(robot_idx, lower, upper)
    viewer.camera_params.position = base_tf[:3,3]
    viewer.camera_params.yaw = np.pi / 3
    viewer.camera_params.pitch = -np.pi / 6
    viewer.camera_params.distance = 2.0 * np.linalg.norm(upper - lower)
  else:
    viewer.camera_params.position = [1.0, 0.0, 0.0]
    viewer.camera_params.yaw = -np.pi / 3
    viewer.camera_params.pitch = -np.pi / 6
    viewer.camera_params.distance = 5.0

  viewer.update(task.time_step)
  viewer.render(sim)
  viewer.render(sim) # Necessary to avoid occasional blank images
  return viewer.get_image()

def main():
  parser = argparse.ArgumentParser(description="Process robot design search results.")
  parser.add_argument("task", type=str, help="Task (Python class name)")
  parser.add_argument("grammar_file", type=str, help="Grammar file (.dot)")
  parser.add_argument("-j", "--jobs", type=int, required=True,
                      help="Number of jobs/threads")
  parser.add_argument("-f", "--log_file", type=str, required=True,
                      help="MCTS log file")
  parser.add_argument("-t", "--type", type=str)
  parser.add_argument("-s", "--save_image_dir", type=str)
  args = parser.parse_args()

  task_class = getattr(tasks, args.task)
  task = task_class()
  graphs = rd.load_graphs(args.grammar_file)
  rules = [rd.create_rule_from_graph(g) for g in graphs]

  iteration_df = pd.read_csv(args.log_file, index_col=0)

  if args.type == "iterations":
    os.makedirs(args.save_image_dir, exist_ok=True)
    mid_indices = np.arange(0, len(iteration_df) + 1, 1000)
    offset = 10
    for mid_index in mid_indices:
      start_index = max(mid_index - offset, 0)
      end_index = min(mid_index + offset, len(iteration_df))
      for index in range(start_index, end_index):
        rule_seq = ast.literal_eval(iteration_df['rule_seq'][index])
        robot = make_robot_from_rule_sequence(rule_seq, rules)
        im_data = get_robot_image(robot, task)[::-1,:,:]
        im = Image.fromarray(im_data)
        im.save(os.path.join(args.save_image_dir,
                             f"iteration_{index:05}.png"))

  if args.type == "iterations_top":
    os.makedirs(args.save_image_dir, exist_ok=True)
    block_size = 1000
    count = 10
    for start_index in range(0, len(iteration_df), block_size):
      end_index = min(start_index + block_size, len(iteration_df))
      block = iteration_df[start_index:end_index].copy()
      block = block.sort_values(by='result', ascending=False).reset_index()
      for i in range(count):
        row = block.ix[i]
        rule_seq = ast.literal_eval(row['rule_seq'])
        robot = make_robot_from_rule_sequence(rule_seq, rules)
        im_data = get_robot_image(robot, task)[::-1,:,:]
        im = Image.fromarray(im_data)
        block_index = start_index // block_size
        im.save(os.path.join(args.save_image_dir,
                             f"iteration_{row['iteration']:05}.png"))

  elif args.type == "percentiles":
    os.makedirs(args.save_image_dir, exist_ok=True)
    percentiles = np.linspace(0.0, 1.0, 11)
    offset = 10
    iteration_df.sort_values(by='result')
    for percentile in percentiles:
      mid_index = int(round(percentile * (len(iteration_df) - 1)))
      start_index = max(mid_index - offset, 0)
      end_index = min(mid_index + offset, len(iteration_df))
      for index in range(start_index, end_index):
        rule_seq = ast.literal_eval(iteration_df['rule_seq'][index])
        robot = make_robot_from_rule_sequence(rule_seq, rules)
        im_data = get_robot_image(robot, task)[::-1,:,:]
        im = Image.fromarray(im_data)
        im.save(os.path.join(args.save_image_dir,
                             f"sorted_{index:05}.png"))

  elif args.type == "terrain":
    # Take a screenshot of the terrain alone
    os.makedirs(args.save_image_dir, exist_ok=True)
    im_data = get_robot_image(None, task)[::-1,:,:]
    im = Image.fromarray(im_data)
    im.save(os.path.join(args.save_image_dir,
                         f"terrain_{args.task}.png"))

if __name__ == '__main__':
  main()
